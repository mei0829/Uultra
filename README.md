# 新人名單與組織

手機優先的單頁網站，用來管理新人名單、追蹤進度與組織架構。

## 檔案

- `index.html` — 整個網站（HTML / CSS / JS 都在這一個檔案）
- `auth.js` — Firebase 帳號密碼登入與雲端同步
- `firebase-config.js` — 填入你的 Firebase 專案設定
- `firestore.rules` — Firestore 安全規則（每人只能讀寫自己的資料）
- `manifest.webmanifest`、`icon.svg` — 讓手機可以「加入主畫面」當成 App 使用
- `.github/workflows/pages.yml` — 推送後自動部署到 GitHub Pages

## 設定 Firebase（第一次）

1. 到 https://console.firebase.google.com 建立專案。
2. **Authentication → 登入方式**：啟用「電子郵件/密碼」。
3. **Firestore Database**：建立資料庫（正式版模式），到「規則」分頁貼上 `firestore.rules` 的內容後發布。
4. **專案設定 → 一般 → 你的應用程式**：新增「網頁」應用程式，把 `firebaseConfig` 的值填進 `firebase-config.js`。
5. **Authentication → 設定 → 授權網域**：加入網站網域（例如 `<帳號>.github.io`）。

## 本機預覽

```bash
python3 -m http.server 8000
# 打開 http://localhost:8000
```

## 部署到 GitHub Pages

1. 到 GitHub 倉庫 **Settings → Pages**，Source 選 **GitHub Actions**。
2. 推送到 `main`（或目前的開發分支）後會自動部署，網址為
   `https://<帳號>.github.io/<倉庫名>/`。

## 注意

- 每個人用自己的 Email 和密碼登入，資料存在 Firestore 的 `data/users/{uid}` 底下，彼此看不到。
- 資料會先存在手機本機，再自動同步到雲端；換手機登入同一個帳號就會帶回來。
- 登出時會清除這支手機上的本機資料；同一支手機換帳號登入也會先清掉上一個帳號的資料。
- 照片只存在這支手機（IndexedDB），不會同步到雲端。
- 「用照片讀取課表」在這個網站上不能用，請改用「快速匯入」。
