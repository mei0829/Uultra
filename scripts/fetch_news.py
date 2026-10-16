#!/usr/bin/env python3
"""抓國內外新聞、熱門話題、大盤和美股報價，存成 news.json 給 news.html 用。

在 GitHub Actions 每小時跑一次（瀏覽器不能直接抓別人網站的 RSS，所以由伺服器先抓好）。
只用 Python 內建模組；任何一個來源抓不到都會略過，不會讓整個網站部署失敗。
"""
import html
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
KEEP_HOURS = 72      # 只留最近 3 天的新聞
PER_FEED = 15        # 每個來源最多幾則
PER_CAT = 90         # 每個分類最多幾則

CATS = [
    ('hot', '焦點'),
    ('startup', '創業'),
    ('econ', '經濟財經'),
    ('beauty', '美容美妝'),
    ('fashion', '穿搭'),
    ('health', '健康就醫'),
    ('teacher', '教師教育'),
]


def gn(q, lang='tw'):
    """Google 新聞搜尋 RSS：聚合各家媒體，標題後面會帶來源名稱。"""
    loc = 'hl=zh-TW&gl=TW&ceid=TW:zh-Hant' if lang == 'tw' else 'hl=en-US&gl=US&ceid=US:en'
    return f'https://news.google.com/rss/search?q={urllib.parse.quote(q + " when:2d")}&{loc}'


def gn_topic(topic, lang='tw'):
    loc = 'hl=zh-TW&gl=TW&ceid=TW:zh-Hant' if lang == 'tw' else 'hl=en-US&gl=US&ceid=US:en'
    if topic is None:
        return f'https://news.google.com/rss?{loc}'
    return f'https://news.google.com/rss/headlines/section/topic/{topic}?{loc}'


def ptt(board):
    return f'https://www.ptt.cc/atom/{board}.xml'


# (分類, 地區 tw/intl, 平台名稱, 網址)。平台名稱是 None 時，用新聞裡寫的媒體名稱。
FEEDS = [
    # 焦點
    ('hot', 'tw', None, gn_topic(None, 'tw')),
    ('hot', 'tw', None, gn_topic('NATION', 'tw')),
    ('hot', 'intl', 'BBC 中文', 'https://feeds.bbci.co.uk/zhongwen/trad/rss.xml'),
    ('hot', 'intl', None, gn_topic('WORLD', 'tw')),
    ('hot', 'intl', None, gn_topic(None, 'en')),
    ('hot', 'intl', 'Hacker News', 'https://hnrss.org/frontpage?points=200'),
    # 創業
    ('startup', 'tw', None, gn('新創 OR 創業 OR 募資')),
    ('startup', 'tw', None, gn('site:bnext.com.tw OR site:meet.bnext.com.tw')),
    ('startup', 'tw', None, gn('創業家 OR 小資創業 OR 加盟')),
    ('startup', 'intl', None, gn('site:entrepreneur.com OR site:inc.com', 'en')),
    ('startup', 'intl', 'TechCrunch', 'https://techcrunch.com/category/startups/feed/'),
    ('startup', 'intl', None, gn('startup funding OR founders OR small business', 'en')),
    # 經濟財經
    ('econ', 'tw', None, gn_topic('BUSINESS', 'tw')),
    ('econ', 'tw', None, gn('台股 OR 央行 OR 通膨 OR 匯率')),
    ('econ', 'tw', 'PTT 股票板', ptt('Stock')),
    ('econ', 'intl', None, gn_topic('BUSINESS', 'en')),
    ('econ', 'intl', 'CNBC', 'https://www.cnbc.com/id/100003114/device/rss/rss.html'),
    ('econ', 'intl', 'MarketWatch', 'https://feeds.content.dowjones.io/public/rss/mw_topstories'),
    # 美容美妝
    ('beauty', 'tw', None, gn('美妝 OR 保養 OR 彩妝 OR 醫美')),
    ('beauty', 'tw', None, gn('防曬 OR 精華液 OR 敏感肌 OR 新品 美妝')),
    ('beauty', 'tw', 'PTT 美妝板', ptt('MakeUp')),
    ('beauty', 'intl', None, gn('site:byrdie.com OR site:harpersbazaar.com beauty', 'en')),
    ('beauty', 'intl', 'Allure', 'https://www.allure.com/feed/rss'),
    ('beauty', 'intl', None, gn('skincare OR makeup OR beauty trends', 'en')),
    # 穿搭
    ('fashion', 'tw', None, gn('穿搭 OR 時尚 OR 服飾品牌')),
    ('fashion', 'tw', 'PTT 穿搭板', ptt('Mix_Match')),
    ('fashion', 'intl', 'Vogue', 'https://www.vogue.com/feed/rss'),
    ('fashion', 'intl', 'GQ', 'https://www.gq.com/feed/rss'),
    ('fashion', 'intl', None, gn('fashion trends OR outfit OR street style', 'en')),
    # 健康就醫
    ('health', 'tw', None, gn_topic('HEALTH', 'tw')),
    ('health', 'tw', None, gn('疾管署 OR 健保 OR 就醫 OR 門診 OR 流感')),
    ('health', 'tw', None, gn('癌症 OR 糖尿病 OR 失智 OR 疾病 研究')),
    ('health', 'intl', None, gn_topic('HEALTH', 'en')),
    ('health', 'intl', None, gn('site:medicalnewstoday.com OR site:health.harvard.edu', 'en')),
    ('health', 'intl', 'WHO', 'https://www.who.int/rss-feeds/news-english.xml'),
    ('health', 'intl', 'BBC Health', 'https://feeds.bbci.co.uk/news/health/rss.xml'),
    ('health', 'intl', 'NYT Health', 'https://rss.nytimes.com/services/xml/rss/nyt/Health.xml'),
    # 教師教育
    ('teacher', 'tw', None, gn('教師 OR 老師 OR 教甄 OR 代理教師')),
    ('teacher', 'tw', None, gn('教育部 OR 課綱 OR 學校 OR 校園')),
    ('teacher', 'tw', 'PTT 教甄板', ptt('studyteacher')),
    ('teacher', 'tw', 'PTT 教育板', ptt('Education')),
    ('teacher', 'intl', None, gn('site:edweek.org OR site:the74million.org', 'en')),
    ('teacher', 'intl', None, gn('teachers OR teacher shortage OR classroom', 'en')),
]

TRENDS = {
    'TW': ['https://trends.google.com/trending/rss?geo=TW',
           'https://trends.google.com/trends/trendingsearches/daily/rss?geo=TW'],
    'US': ['https://trends.google.com/trending/rss?geo=US',
           'https://trends.google.com/trends/trendingsearches/daily/rss?geo=US'],
}

# 大盤與匯率
MARKETS = [
    ('^TWII', '台灣加權'), ('^GSPC', 'S&P 500'), ('^IXIC', 'Nasdaq'),
    ('^DJI', '道瓊'), ('^SOX', '費城半導體'), ('TWD=X', '美元/台幣'),
]
# 常見美股和 ETF（瀏覽器直接抓不到美股報價時，用這裡先抓好的）。
# 自己的美股不在裡面的話，到 GitHub 倉庫 Settings → Secrets and variables → Actions → Variables
# 新增 US_SYMBOLS，例如：VOO,QQQ,PLTR（逗號分隔）。
US_DEFAULT = ('VOO SPY QQQ VTI VT VXUS SCHD BND TLT SOXX SMH DIA IVV QQQM JEPI '
              'AAPL MSFT NVDA GOOGL AMZN META TSLA TSM AVGO AMD INTC NFLX COST KO BRK-B JPM V MA PLTR ASML ARM').split()


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def local(tag):
    return tag.rsplit('}', 1)[-1]


def child(el, name):
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def text(el, name):
    c = child(el, name)
    return (c.text or '').strip() if c is not None and c.text else ''


def clean(s, n=160):
    s = re.sub(r'<[^>]+>', ' ', html.unescape(s or ''))
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n].rstrip() + '…'


def when(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def parse_feed(raw, src_name):
    """解析 RSS 2.0 或 Atom，回傳 [{t,u,s,d,x}]。"""
    root = ET.fromstring(raw)
    out = []
    items = [e for e in root.iter() if local(e.tag) in ('item', 'entry')]
    for it in items[:PER_FEED]:
        title = clean(text(it, 'title'), 200)
        link = text(it, 'link')
        if not link:
            for c in it:
                if local(c.tag) == 'link' and c.get('href') and c.get('rel', 'alternate') == 'alternate':
                    link = c.get('href')
                    break
        if not title or not link:
            continue
        src = src_name
        s_el = child(it, 'source')
        if src is None and s_el is not None and s_el.text:
            src = s_el.text.strip()
        # Google 新聞的標題是「標題 - 媒體名稱」
        if 'news.google.com' in link and ' - ' in title:
            head, tail = title.rsplit(' - ', 1)
            if src is None:
                src = tail.strip()
            if tail.strip() == (src or '').strip():
                title = head.strip()
        a = child(it, 'author')
        if src is None and a is not None:
            src = text(a, 'name') or (a.text or '').strip()
        d = when(text(it, 'pubDate') or text(it, 'published') or text(it, 'updated') or text(it, 'date'))
        desc = '' if 'news.google.com' in link else clean(text(it, 'description') or text(it, 'summary') or text(it, 'content'))
        if desc and desc.startswith(title[:20]):
            desc = ''
        out.append({'t': title, 'u': link, 's': src or '', 'd': d, 'x': desc})
    return out


def fetch_feed(f):
    cat, region, name, url = f
    try:
        items = parse_feed(get(url), name)
        for i in items:
            i['c'] = cat
            i['r'] = region
            if i['s'].startswith('PTT') or name and name.startswith('PTT'):
                i['p'] = 'PTT'
            elif name == 'Hacker News':
                i['p'] = 'HN'
        return items, None
    except Exception as e:  # noqa: BLE001 — 任何來源壞掉都略過
        return [], f'{url} → {type(e).__name__}: {e}'[:200]


def norm(t):
    return re.sub(r'[\W_]+', '', t.lower())[:40]


def fetch_trends(geo):
    for url in TRENDS[geo]:
        try:
            root = ET.fromstring(get(url))
        except Exception:
            continue
        out = []
        for it in [e for e in root.iter() if local(e.tag) == 'item'][:20]:
            t = text(it, 'title')
            if not t:
                continue
            traffic = ''
            news = None
            for c in it.iter():
                n = local(c.tag)
                if n == 'approx_traffic' and c.text:
                    traffic = c.text.strip()
                elif n == 'news_item' and news is None:
                    news = {'t': clean(text(c, 'news_item_title'), 120), 'u': text(c, 'news_item_url'), 's': text(c, 'news_item_source')}
            out.append({'q': t, 'n': traffic, 'news': news if news and news['u'] else None})
        if out:
            return out
    return []


# Yahoo 擋沒有 cookie 的伺服器請求，先拿 cookie 和 crumb
_JAR = http.cookiejar.CookieJar()
_YOP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_JAR))
_CRUMB = [None]


def yget(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    with _YOP.open(req, timeout=timeout) as r:
        return r.read()


def crumb():
    if _CRUMB[0] is None:
        _CRUMB[0] = ''
        for u in ('https://fc.yahoo.com', 'https://finance.yahoo.com/'):
            try:
                yget(u)
            except Exception:
                pass  # fc.yahoo.com 會回 404，但 cookie 已經拿到
        try:
            _CRUMB[0] = yget('https://query2.finance.yahoo.com/v1/test/getcrumb').decode().strip()
        except Exception as e:
            print('  Yahoo crumb 失敗', e)
    return _CRUMB[0]


def yahoo(sym, rng='1mo'):
    c = crumb()
    last = None
    for host in ('query2', 'query1'):
        url = f'https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval=1d' + (f'&crumb={urllib.parse.quote(c)}' if c else '')
        try:
            j = json.loads(yget(url))
            break
        except Exception as e:
            last = e
    else:
        raise last
    r = j['chart']['result'][0]
    m = r['meta']
    closes = [c for c in (r.get('indicators', {}).get('quote', [{}])[0].get('close') or []) if c is not None]
    p = m.get('regularMarketPrice')
    prev = m.get('previousClose')
    if prev is None:
        prev = closes[-2] if len(closes) >= 2 else m.get('chartPreviousClose')
    if not p:
        raise ValueError('no price')
    return {'p': round(p, 4), 'prev': round(prev, 4) if prev else None, 't': m.get('regularMarketTime'),
            'spark': [round(c, 2) for c in closes[-22:]]}


def stooq(sym):
    """備用：stooq 的日線 CSV（Date,Open,High,Low,Close,Volume）。"""
    rows = get(f'https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&i=d').decode().strip().splitlines()[1:]
    closes = [float(r.split(',')[4]) for r in rows[-23:] if r.count(',') >= 4]
    if len(closes) < 2:
        raise ValueError('stooq 沒資料')
    d = rows[-1].split(',')[0]
    t = int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()) + 21 * 3600
    return {'p': closes[-1], 'prev': closes[-2], 't': t, 'spark': closes[-22:]}


STOOQ = {'^TWII': None, '^TWOII': None, '^GSPC': '^spx', '^IXIC': '^ndq', '^DJI': '^dji', '^SOX': '^sox', 'TWD=X': 'usdtwd'}


def twse_index():
    """備用：證交所的加權指數收盤。"""
    js = json.loads(get('https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX'))
    for x in js:
        if str(x.get('指數', '')).strip() == '發行量加權股價指數':
            p = float(str(x['收盤指數']).replace(',', ''))
            ch = float(str(x['漲跌點數']).replace(',', ''))
            if str(x.get('漲跌', '')).strip() == '-':
                ch = -abs(ch)
            return {'p': p, 'prev': p - ch, 't': None, 'spark': []}
    raise ValueError('找不到加權指數')


CNBC = {'^TWII': '.TWII', '^TWOII': None, '^GSPC': '.SPX', '^IXIC': '.IXIC', '^DJI': '.DJI', '^SOX': '.SOX', 'TWD=X': 'TWD='}


def cnbc(symbols):
    """CNBC 公開報價（一次可以查很多檔），回傳 {代號: {p, prev, t}}。"""
    out = {}
    for i in range(0, len(symbols), 40):
        part = symbols[i:i + 40]
        url = ('https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols='
               + urllib.parse.quote('|'.join(part), safe='|') + '&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=0&output=json')
        try:
            j = json.loads(get(url, 20))
        except Exception as e:
            print('  CNBC 失敗', e)
            continue
        qs = j.get('FormattedQuoteResult', {}).get('FormattedQuote', [])
        for q in qs if isinstance(qs, list) else [qs]:
            try:
                p = float(str(q.get('last', '')).replace(',', ''))
                prev = q.get('previous_day_closing')
                prev = float(str(prev).replace(',', '')) if prev not in (None, '') else p - float(str(q.get('change', '0')).replace(',', '').replace('UNCH', '0'))
                t = q.get('last_time')
                try:
                    t = int(datetime.fromisoformat(t).timestamp()) if t else None
                except Exception:
                    t = None
                out[q['symbol']] = {'p': p, 'prev': prev, 't': t}
            except Exception:
                pass
    return out


def fetch_markets():
    out = []
    cq = cnbc([c for c in CNBC.values() if c])
    for sym, name in MARKETS:
        q = None
        try:
            q = yahoo(sym)
        except Exception as e:
            if cq.get(CNBC.get(sym)):
                q = dict(cq[CNBC[sym]], spark=[])
                q.update(sym=sym, name=name)
                out.append(q)
                continue
            print(f'  Yahoo {sym} 失敗：{e}')
            try:
                if STOOQ.get(sym):
                    q = stooq(STOOQ[sym])
                elif sym == '^TWII':
                    q = twse_index()
            except Exception as e2:
                print(f'  備用 {sym} 失敗：{e2}')
        if q:
            q.update(sym=sym, name=name)
            out.append(q)
    return out


def fetch_us():
    extra = [s.strip().upper() for s in re.split(r'[,\s]+', os.environ.get('US_SYMBOLS', '')) if s.strip()]
    syms = list(dict.fromkeys(US_DEFAULT + extra))
    out = {}
    cq = cnbc([x.replace('-', '.') for x in syms])
    for x in syms:
        q = cq.get(x.replace('-', '.'))
        if q:
            out[x] = q
    syms = [x for x in syms if x not in out]

    def one(s):
        try:
            q = yahoo(s, '5d')
        except Exception:
            try:
                q = stooq(s.lower().replace('-', '.') + '.us')
            except Exception:
                return s, None
        q.pop('spark', None)
        return s, q
    with ThreadPoolExecutor(6) as ex:
        for s, q in ex.map(one, syms):
            if q:
                out[s] = q
    return out


def main(path):
    now = int(time.time())
    crumb()  # 先拿好，免得下面同時搶
    with ThreadPoolExecutor(10) as ex:
        results = list(ex.map(fetch_feed, FEEDS))
        trends_f = {g: ex.submit(fetch_trends, g) for g in TRENDS}
        mk_f = ex.submit(fetch_markets)
        us_f = ex.submit(fetch_us)
    errors = [e for _, e in results if e]
    items, seen = [], set()
    for its, _ in results:
        for i in its:
            if i['d'] and now - i['d'] > KEEP_HOURS * 3600:
                continue
            k = (i['c'], norm(i['t']))
            if k in seen:
                continue
            seen.add(k)
            items.append(i)
    items.sort(key=lambda i: i['d'] or 0, reverse=True)
    per = {}
    kept = []
    for i in items:
        per[i['c']] = per.get(i['c'], 0) + 1
        if per[i['c']] <= PER_CAT:
            kept.append(i)
    data = {
        'updated': now,
        'cats': [{'k': k, 'n': n} for k, n in CATS],
        'items': kept,
        'trends': {g: f.result() for g, f in trends_f.items()},
        'markets': mk_f.result(),
        'us': us_f.result(),
        'sources': {'ok': len(FEEDS) - len(errors), 'all': len(FEEDS)},
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'news: {len(kept)} 則，來源 {data["sources"]["ok"]}/{len(FEEDS)}；'
          f'熱搜 TW {len(data["trends"]["TW"])} US {len(data["trends"]["US"])}；'
          f'大盤 {len(data["markets"])}；美股 {len(data["us"])}')
    for e in errors:
        print('  略過', e)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'news.json')
