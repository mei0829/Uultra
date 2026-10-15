// 離線用：把網頁和 Firebase 程式存在手機裡，沒有網路也能打開
const CACHE = 'ultra-v1';
const FB = 'https://www.gstatic.com/firebasejs/12.18.0/';
const LOCAL = ['./', 'index.html', 'money.html', 'auth.js', 'firebase-config.js', 'manifest.webmanifest', 'money.webmanifest', 'icon.svg', 'money.svg'];
const SDK = ['firebase-app.js', 'firebase-auth.js', 'firebase-firestore.js'].map(f => FB + f);

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all([...LOCAL, ...SDK].map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

// 自己網站的檔案：先抓網路上最新的（4 秒內），抓不到就用手機裡存的
async function netFirst(req) {
  const c = await caches.open(CACHE);
  try {
    const res = await Promise.race([fetch(req), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 4000))]);
    if (res && res.ok) c.put(req, res.clone());
    return res;
  } catch (e) {
    const hit = await c.match(req, { ignoreSearch: true }) || (req.mode === 'navigate' ? await c.match('index.html') : null);
    if (hit) return hit;
    throw e;
  }
}
// Firebase 程式（有版本號，不會變）：手機裡有就直接用
async function cacheFirst(req) {
  const c = await caches.open(CACHE), hit = await c.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res && res.ok) c.put(req, res.clone());
  return res;
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const u = new URL(req.url);
  if (u.origin === self.location.origin) e.respondWith(netFirst(req));
  else if (u.href.startsWith('https://www.gstatic.com/firebasejs/')) e.respondWith(cacheFirst(req));
});
