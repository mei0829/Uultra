// 到 Firebase 主控台 → 專案設定 → 一般 → 你的應用程式（網頁），複製 firebaseConfig 貼到這裡。
// 這些值本來就會出現在網頁裡，不是密碼；資料安全由 firestore.rules 保護。
export const firebaseConfig = {
  apiKey: "AIzaSyCy0tO769orJnNmL2yp87WMwOjr2jlNnck",
  authDomain: "ultra-0829.firebaseapp.com",
  projectId: "ultra-0829",
  storageBucket: "ultra-0829.firebasestorage.app",
  messagingSenderId: "487260862381",
  appId: "1:487260862381:web:e06cc3aa82aad10cea9324"
};

// 管理員 Email：可以在「設定」頁管理邀請名單（要和 firestore.rules 裡的一樣）
export const adminEmail = "lee19977889@gmail.com";
