# 新人名單與組織

手機優先的單頁網站，用來管理新人名單、追蹤進度與組織架構。

## 檔案

- `index.html` — 新人名單（HTML / CSS / JS 都在這一個檔案）
- `money.html` — 我的記帳（網址加上 `/money.html`），`money.webmanifest`、`money.svg` 讓它可以單獨加入主畫面
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

- 只有被邀請的人可以使用：管理員（`firebase-config.js` 的 `adminEmail`，也要和 `firestore.rules` 裡的一樣）在「設定」頁的「邀請名單」加入 Email。
- 註冊後要先點驗證信裡的連結（防止別人冒用 Email），不在邀請名單上的帳號看不到也存不了任何資料。
- 每個人用自己的 Email 和密碼登入，資料存在 Firestore 的 `data/users/{uid}` 底下，彼此看不到。
- 資料會先存在手機本機，再自動同步到雲端；換手機登入同一個帳號就會帶回來。
- 登出時會清除這支手機上的本機資料；同一支手機換帳號登入也會先清掉上一個帳號的資料。
- 照片只存在這支手機（IndexedDB），不會同步到雲端。
- 「課表 → 匯入 → 選擇課表照片」用 Gemini（Firebase AI Logic，免費方案）讀照片。要先在 Firebase 主控台的「AI 服務 → AI Logic」按「開始使用」並選「Gemini Developer API」。

## 我的記帳（money.html）

- 帳戶分三種：現金、銀行、信用卡。信用卡填好「結帳日」和「繳款日」，每筆刷卡會自動歸到對應那一期帳單。
- 「帳單」放水電、電話、保險、稅、房租、政府停車費自動扣繳等固定費用，也可以放薪水當固定收入；扣款帳戶選信用卡的話，會算進那張卡的下一期帳單。
- 「總覽」用目前現金＋銀行餘額，扣掉未來 30／60／90 天的信用卡帳單、固定帳單和日常花費（依最近 3 個月記錄估算），算出建議預留多少錢、哪一天最緊。
- 「匯入」支援：銀行／信用卡的 CSV 明細（UTF-8 或 Big5）、財政部電子發票載具消費明細 CSV、以及用 Gemini 辨識截圖或貼上的刷卡通知文字。同金額、前後 3 天內的紀錄會標成可能重複。
- 台灣的銀行沒有開放個人直接串接刷卡紀錄，所以是用「下載明細 → 匯入」的方式同步。
- 資料存在 Firestore 的 `data/users/{uid}` 底下（文件名稱以 `m_` 開頭，交易紀錄按月份分開），和新人名單用同一個帳號登入。
