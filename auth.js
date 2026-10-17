// Firebase 帳號登入，並提供 index.html 原本使用的 claude.use('db'/'user') 介面
import { firebaseConfig, adminEmail } from './firebase-config.js';

const V = '12.18.0', CDN = `https://www.gstatic.com/firebasejs/${V}/`;
const box = document.getElementById('auth');
// 離線使用：註冊 service worker，把網頁存在手機裡
if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const LOCAL_KEYS = ['roster-v2', 'roster-t', 'roster-prev', 'money-v1', 'money-t', 'money-prev', 'ph-cloud'];
const TITLE = box.dataset.title || '新人名單與組織';

const ERR = {
  'auth/invalid-credential': 'Email 或密碼錯誤',
  'auth/wrong-password': 'Email 或密碼錯誤',
  'auth/user-not-found': 'Email 或密碼錯誤',
  'auth/invalid-email': 'Email 格式不正確',
  'auth/missing-password': '請輸入密碼',
  'auth/email-already-in-use': '這個 Email 已經註冊過，請直接登入',
  'auth/weak-password': '密碼至少要 6 個字元',
  'auth/too-many-requests': '嘗試太多次，請稍後再試',
  'auth/network-request-failed': '網路連線失敗，請確認網路後再試',
  'auth/operation-not-allowed': 'Firebase 尚未啟用「電子郵件/密碼」登入'
};
const ADMIN = String(adminEmail || '').trim().toLowerCase();
const errMsg = e => ERR[e && e.code] || ('發生錯誤（' + ((e && e.code) || e) + '）');

function shell(inner) {
  box.innerHTML = `<div id="authwrap"><h1>${esc(TITLE)}</h1><div class="card">${inner}</div></div>`;
}
function fatal(msg) { shell(`<div class="sub" style="color:var(--bad)">${esc(msg)}</div>`); }

function clearLocal() {
  try { LOCAL_KEYS.forEach(k => localStorage.removeItem(k)); sessionStorage.removeItem('rl'); sessionStorage.removeItem('mrl'); } catch (e) {}
  try { indexedDB.deleteDatabase('roster-photos'); } catch (e) {}
}

let started = false, FBAPP = null;

// 用 Gemini（Firebase AI Logic）讀照片或文字；頁面透過 claude.use('sample') 呼叫
const AI_MODELS = ['gemini-3.6-flash', 'gemini-3-flash', 'gemini-2.5-flash'];
async function shrink(file) {
  try {
    const bm = await createImageBitmap(file), k = Math.min(1, 2000 / Math.max(bm.width, bm.height));
    const c = document.createElement('canvas'); c.width = Math.round(bm.width * k); c.height = Math.round(bm.height * k);
    c.getContext('2d').drawImage(bm, 0, 0, c.width, c.height);
    return { mimeType: 'image/jpeg', data: c.toDataURL('image/jpeg', 0.85).split(',')[1] };
  } catch (e) {
    const b = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
    return { mimeType: file.type || 'image/jpeg', data: String(b).split(',')[1] };
  }
}
const sampler = {
  limits: async () => ({ images: true }),
  json: async (prompt, opts) => {
    let aim;
    try { aim = await import(CDN + 'firebase-ai.js'); } catch (e) { throw { code: 'none' }; }
    const ai = aim.getAI(FBAPP, { backend: new aim.GoogleAIBackend() });
    const parts = [prompt];
    if (opts && opts.images) parts.push({ inlineData: await shrink(opts.images) });
    let last;
    for (const name of AI_MODELS) {
      try {
        // search：讓 Gemini 用 Google 搜尋查最新資料（這時不能指定 JSON 格式，改從文字裡取出 JSON）
        const srch = opts && opts.search;
        const m = aim.getGenerativeModel(ai, srch ? { model: name, tools: [{ googleSearch: {} }] } : { model: name, generationConfig: { responseMimeType: 'application/json' } });
        const r = await m.generateContent(parts);
        let t = r.response.text().trim().replace(/^```(?:json)?\s*/i, '').replace(/```$/, '');
        if (srch) { const a = t.indexOf('{'), b = t.lastIndexOf('}'); if (a >= 0 && b > a) t = t.slice(a, b + 1); }
        let o;
        try { o = JSON.parse(t); } catch (x) { throw { code: 'empty' }; }
        if (srch && o && typeof o === 'object') {
          const g = ((r.response.candidates || [])[0] || {}).groundingMetadata || {};
          o._src = (g.groundingChunks || []).map(c => c.web).filter(Boolean).map(w => ({ t: w.title || w.domain || '', u: w.uri }));
          o._entry = (g.searchEntryPoint && g.searchEntryPoint.renderedContent) || '';
        }
        return o;
      } catch (e) {
        last = e;
        if (e && e.code === 'empty') throw e;
        if (!/not.?found|404|not supported/i.test(String(e && e.message))) break;
      }
    }
    const msg = String(last && last.message);
    console.error('AI', last);
    // 分辨是「每分鐘次數太多」還是「今天的額度用完」
    if (/quota|429|RESOURCE_EXHAUSTED|rate/i.test(msg)) throw { code: /per.?day|PerDay|daily/i.test(msg) ? 'quota_day' : /per.?minute|PerMinute/i.test(msg) ? 'quota_min' : 'quota' };
    if (/not been used|disabled|PERMISSION_DENIED|403|api-not-enabled|not enabled/i.test(msg)) throw { code: 'none' };
    throw { code: 'fail' };
  }
};
function startApp(fs, fsm, user) {
  if (started) return;
  started = true;
  // 同一支手機換帳號時，先清掉上一個帳號留在本機的資料
  try {
    const owner = localStorage.getItem('roster-owner');
    if (owner && owner !== user.uid) clearLocal();
    localStorage.setItem('roster-owner', user.uid);
  } catch (e) {}
  const { collection, doc, setDoc, getDocs, getDoc, query, where, documentId } = fsm;
  const col = path => ({
    doc: id => ({ set: o => setDoc(doc(fs, path, id), o) }),
    get: async () => {
      // 照片（p_ 開頭）很大，只在要看的時候才下載；其他資料文件照常讀取
      const c = collection(fs, path), [a, b] = await Promise.all([getDocs(query(c, where(documentId(), '<', 'p_'))), getDocs(query(c, where(documentId(), '>=', 'p`')))]);
      const s = { docs: [...a.docs, ...b.docs] };
      return { docs: s.docs.map(d => ({ id: d.id, data: () => d.data() })) };
    }
  });
  window.claude = { use: async n => n === 'db' ? { collection: col } : n === 'user' ? { id: async () => user.uid } : n === 'sample' ? sampler : null };
  const { getDocs: gd, deleteDoc } = fsm;
  // 照片雲端備份：壓縮後的照片存在 data/users/{uid}/p_{照片id}
  const pcol = 'data/users/' + user.uid;
  window.FBP = {
    put: async (id, blob) => {
      const d = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(blob); });
      if (d.length > 900000) throw new Error('too big');
      await setDoc(doc(fs, pcol, 'p_' + id), { d, at: Date.now() });
    },
    get: async id => {
      const x = await getDoc(doc(fs, pcol, 'p_' + id));
      if (!x.exists()) return null;
      return await (await fetch(x.data().d)).blob();
    },
    del: id => deleteDoc(doc(fs, pcol, 'p_' + id)).catch(() => {})
  };
  const admin = (user.email || '').toLowerCase() === ADMIN;
  window.FBU = { email: user.email, admin };
  if (admin) {
    window.FBA = { list: null };
    const load = async () => {
      try { const s = await gd(collection(fs, 'allow')); FBA.list = s.docs.map(d => d.id).sort(); }
      catch (e) { FBA.list = []; FBA.err = errMsg(e); }
      if (typeof render === 'function') render();
    };
    FBA.add = async em => {
      em = String(em || '').trim().toLowerCase();
      if (!/^[^\s@\/]+@[^\s@\/]+\.[^\s@\/]+$/.test(em)) return 'Email 格式不正確';
      try { await setDoc(doc(fs, 'allow', em), { by: user.email, at: Date.now() }); await load(); return ''; }
      catch (e) { return errMsg(e); }
    };
    FBA.remove = async em => {
      try { await deleteDoc(doc(fs, 'allow', em)); await load(); return ''; }
      catch (e) { return errMsg(e); }
    };
    setTimeout(load, 0);
  }
  box.innerHTML = '';
  const s = document.createElement('script');
  s.textContent = document.getElementById('app-src').textContent;
  document.body.appendChild(s);
}

function loginForm(auth, am, mode, note) {
  const reg = mode === 'reg';
  shell(`<form id="af">
    <div style="font-weight:700;font-size:17px;margin-bottom:10px">${reg ? '註冊新帳號' : '登入'}</div>
    <label class="afl"><span>Email</span><input id="ae" type="email" autocomplete="username" required></label>
    <label class="afl"><span>密碼</span><input id="ap" type="password" autocomplete="${reg ? 'new-password' : 'current-password'}" minlength="6" required></label>
    ${reg ? '<label class="afl"><span>再輸入一次密碼</span><input id="ap2" type="password" autocomplete="new-password" minlength="6" required></label><div class="sub">需要管理員先把你的 Email 加入邀請名單，才能使用。</div>' : ''}
    <div id="amsg" class="sub" style="min-height:20px;margin:4px 0 8px">${note ? esc(note) : ''}</div>
    <button class="go" type="submit" style="width:100%">${reg ? '註冊並登入' : '登入'}</button>
    <div class="row" style="justify-content:space-between;margin-top:12px">
      <a href="#" id="asw">${reg ? '已經有帳號？登入' : '還沒有帳號？註冊'}</a>
      ${reg ? '' : '<a href="#" id="afg">忘記密碼</a>'}
    </div></form>`);
  const $ = id => document.getElementById(id);
  const msg = (t, bad) => { $('amsg').textContent = t; $('amsg').style.color = bad ? 'var(--bad)' : ''; };
  $('asw').onclick = e => { e.preventDefault(); loginForm(auth, am, reg ? 'in' : 'reg'); };
  if (!reg) $('afg').onclick = async e => {
    e.preventDefault();
    const em = $('ae').value.trim();
    if (!em) return msg('請先在上方輸入 Email，再按「忘記密碼」', true);
    try { await am.sendPasswordResetEmail(auth, em); msg('已寄出重設密碼信，請到信箱收信'); } catch (x) { msg(errMsg(x), true); }
  };
  $('af').onsubmit = async e => {
    e.preventDefault();
    const em = $('ae').value.trim(), pw = $('ap').value;
    if (reg && pw !== $('ap2').value) return msg('兩次輸入的密碼不一樣', true);
    const btn = e.target.querySelector('button'); btn.disabled = true; msg(reg ? '註冊中…' : '登入中…');
    try {
      if (reg) {
        const c = await am.createUserWithEmailAndPassword(auth, em, pw);
        try { await am.sendEmailVerification(c.user); } catch (x) {}
      }
      else await am.signInWithEmailAndPassword(auth, em, pw);
    } catch (x) { msg(errMsg(x), true); btn.disabled = false; }
  };
}

function verifyScreen(auth, am, user, note) {
  shell(`<div style="font-weight:700;font-size:17px;margin-bottom:8px">請驗證你的 Email</div>
    <div class="sub" style="margin-bottom:10px">我們寄了一封驗證信到 <b>${esc(user.email)}</b>。<br>請打開信，點裡面的連結，再回來按下面的按鈕。<br>（找不到的話，看看垃圾郵件）</div>
    <div id="amsg" class="sub" style="min-height:20px;margin-bottom:8px">${note ? esc(note) : ''}</div>
    <button class="go" id="avd" style="width:100%">我已經驗證了</button>
    <div class="row" style="justify-content:space-between;margin-top:12px"><a href="#" id="avr">重寄驗證信</a><a href="#" id="avo">登出</a></div>`);
  const $ = id => document.getElementById(id);
  $('avd').onclick = async () => {
    $('amsg').textContent = '確認中…';
    try { await user.reload(); } catch (e) {}
    if (auth.currentUser && auth.currentUser.emailVerified) { await auth.currentUser.getIdToken(true); location.reload(); }
    else { $('amsg').textContent = '還沒驗證成功，請先點信裡的連結。'; $('amsg').style.color = 'var(--bad)'; }
  };
  $('avr').onclick = async e => {
    e.preventDefault();
    try { await am.sendEmailVerification(user); $('amsg').textContent = '已重寄，請到信箱收信'; $('amsg').style.color = ''; }
    catch (x) { $('amsg').textContent = errMsg(x); $('amsg').style.color = 'var(--bad)'; }
  };
  $('avo').onclick = e => { e.preventDefault(); am.signOut(auth); };
}

function deniedScreen(auth, am, user, msg) {
  shell(`<div style="font-weight:700;font-size:17px;margin-bottom:8px">${msg ? '暫時無法確認' : '還沒有被邀請'}</div>
    <div class="sub" style="margin-bottom:12px">${msg ? esc(msg) : `你的帳號 <b>${esc(user.email)}</b> 還不在邀請名單上。<br>請把這個 Email 告訴管理員，請他幫你加入後，再按「重新檢查」。`}</div>
    <button class="go" id="adr" style="width:100%">重新檢查</button>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><a href="#" id="ado">登出</a></div>`);
  document.getElementById('adr').onclick = () => location.reload();
  document.getElementById('ado').onclick = e => { e.preventDefault(); am.signOut(auth); };
}

async function gate(auth, am, fs, fsm, user) {
  if (!user.emailVerified) return verifyScreen(auth, am, user);
  const em = (user.email || '').toLowerCase();
  if (em === ADMIN) return startApp(fs, fsm, user);
  // 沒有網路：這支手機之前用這個帳號登入過，就直接用本機資料
  try { if (!navigator.onLine && localStorage.getItem('roster-owner') === user.uid) return startApp(fs, fsm, user); } catch (x) {}
  shell('<div class="sub">確認權限中…</div>');
  try {
    const d = await fsm.getDoc(fsm.doc(fs, 'allow', em));
    if (d.exists()) startApp(fs, fsm, user);
    else deniedScreen(auth, am, user);
  } catch (e) {
    // 沒有網路時，這支手機之前已經用這個帳號登入過，就先讓他用本機資料
    let prev = false;
    try { prev = localStorage.getItem('roster-owner') === user.uid; } catch (x) {}
    if (prev && e && e.code !== 'permission-denied') startApp(fs, fsm, user);
    else deniedScreen(auth, am, user, e && e.code === 'permission-denied' ? '' : '無法連線，請確認網路後按「重新檢查」。');
  }
}

(async () => {
  if (!firebaseConfig || !firebaseConfig.apiKey) return fatal('尚未設定 Firebase：請在 firebase-config.js 填入專案設定。');
  let appm, am, fsm;
  try {
    [appm, am, fsm] = await Promise.all([
      import(CDN + 'firebase-app.js'), import(CDN + 'firebase-auth.js'), import(CDN + 'firebase-firestore.js')
    ]);
  } catch (e) { return fatal('無法載入登入元件，請確認網路連線後重新整理。'); }
  const app = FBAPP = appm.initializeApp(firebaseConfig);
  const auth = am.getAuth(app), fs = fsm.getFirestore(app);
  try { await am.setPersistence(auth, am.browserLocalPersistence); } catch (e) {}

  window.fbLogout = async () => {
    // 先把還沒送出的變更推上雲端，再清除本機資料
    try {
      if (typeof CL !== 'undefined' && CL.col) {
        clearTimeout(CL.tm);
        while (CL.busy) await new Promise(r => setTimeout(r, 200));
        await cloudPush();
        if (String(CL.st).startsWith('⚠︎') && !confirm('還有資料沒有同步到雲端，登出後這支手機上的這些資料會消失。確定要登出？')) return;
      }
    } catch (e) {}
    await am.signOut(auth);
    clearLocal();
    try { localStorage.removeItem('roster-owner'); } catch (e) {}
    location.reload();
  };

  shell('<div class="sub">載入中…</div>');
  am.onAuthStateChanged(auth, user => {
    if (user) { if (!started) gate(auth, am, fs, fsm, user); }
    else if (!started) loginForm(auth, am, 'in');
    else location.reload();
  });
})();
