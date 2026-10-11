# 新人名單與組織

手機優先的單頁網站，用來管理新人名單、追蹤進度與組織架構。

## 檔案

- `index.html` — 整個網站（HTML / CSS / JS 都在這一個檔案）
- `manifest.webmanifest`、`icon.svg` — 讓手機可以「加入主畫面」當成 App 使用
- `.github/workflows/pages.yml` — 推送後自動部署到 GitHub Pages

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

- 資料存在瀏覽器本機（localStorage / IndexedDB），換手機或清除瀏覽器資料就不會帶過去。
  建議定期到「設定」按「複製全部備份」，貼到備忘錄保存。
- 原本在 Claude 裡才有的「雲端同步」和「用照片讀取課表」功能，在一般網站上無法使用，
  網站會自動改成只存在本機，其他功能都正常。
