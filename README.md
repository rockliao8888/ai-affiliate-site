# 每日榜單研究所：AI 自動更新聯盟行銷網站

用程式抓公開資料、由 Claude 寫摘要和專欄，產生靜態網站。GitHub Actions 定時執行，部署到 GitHub Pages（免費主機）；有新文章時自動推播到 Telegram／Discord。

## 內容與資料來源

| 頁面 | 內容 | 來源 | 更新頻率 |
|---|---|---|---|
| 潛力觀察股 | 高殖利率、低本益比的量化篩選結果，附 AI 解讀 | 證交所 OpenAPI | 平日盤後 |
| ETF 折溢價 | 溢價前 20、折價前 20、申購熱度 | 證交所 ETF 預估淨值 | 平日盤後 |
| 匯率 | 8 種主要外幣 | ExchangeRate-API | 每日 |
| 音樂榜 | 台灣／美國熱門歌曲 | Apple Music RSS | 每日 |
| 暢銷書／電影／App／Podcast | 排行榜 | Apple RSS | 每日 |
| 熱門新聞 | 焦點、財經、科技、健康、娛樂（只列標題和連結） | Google 新聞 RSS | 每日 |
| 健康小百科、專欄 | AI 原創文章，自動放入相關聯盟商品 | Claude | 每日 2 篇 |

某個資料來源失敗時，會沿用上一次的快照，並在頁面上標示「暫時無法取得」。整個網站不會因此建置失敗。

## 營利方式

1. **聯盟連結**：在 `config/affiliates.json` 把每個商品的 `url` 換成你的追蹤連結，例如通路王、聯盟網、博客來 AP、momo、券商推薦開戶、信用卡推薦。商品會依頁面主題和日期輪播；AI 寫文章時也會從清單中挑相關商品。
2. **排行榜深層連結**：在 `config/site.json` 的 `affiliate` 區塊設定：
   - `apple_token`：Apple 聯盟計畫的 token，會加到所有 Apple 連結上
   - `books_link_template`：換成你的博客來或通路王深層連結格式，`{q}` 代表書名
   - `amazon_tag`：Amazon Associates 的追蹤標籤
3. **Google AdSense**：網站通過審核後，把 `adsense_client` 填入 `ca-pub-xxxx`，廣告版位已經預留好。
4. **GA4**：填入 `ga4_id`，就能追蹤流量和點擊。

## 部署步驟（約 15 分鐘）

1. 在 GitHub 建立新的 repo，例如 `ai-affiliate-site`，把這個資料夾的內容推上去。
2. 修改 `config/site.json` 的 `base_url`，改成 `https://<你的帳號>.github.io/ai-affiliate-site`。
3. 到 repo 的 **Settings → Pages**，把 Source 設為 **GitHub Actions**。
4. 到 **Settings → Secrets and variables → Actions**，新增：
   - `ANTHROPIC_API_KEY`（必填，AI 寫文章用）
   - `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`（選填，推播到 Telegram 頻道）
   - `DISCORD_WEBHOOK_URL`（選填）
5. 到 **Actions → Auto update site → Run workflow**，手動執行一次。完成後網站就上線了，之後會依排程自動更新。
6. 到 Google Search Console 提交 `sitemap.xml`。

## 本機測試

```bash
python scripts/build.py --articles 0     # 不呼叫 AI，只抓資料並建置
python scripts/build.py                  # 完整流程（需要 ANTHROPIC_API_KEY 和 pip install anthropic，Python 3.10 以上）
```

產生的網站在 `public/`。

## 成本

- 主機：GitHub Pages 免費；GitHub Actions 公開 repo 免費。
- AI：預設模型 `claude-opus-5-5`。每天約 1 份市場摘要加 2 篇文章，估計每月 10～20 美元。想省錢可在 workflow 加上環境變數 `CLAUDE_MODEL=claude-sonnet-5-5`。

## ⚠️ 上線前請務必注意

- **投顧法規**：在台灣未經許可，不得對個別股票提供買賣建議。本站把選股呈現為「依公開數據的量化篩選」，AI 提示詞也禁止寫出買賣建議和目標價，各頁都附上免責聲明。請不要把文字改成「推薦買進」這類說法。
- **聯盟揭露**：公平會規定業配和聯盟連結必須揭露。頁尾和 `about.html` 已經寫好揭露文字，商品卡片也有「贊助推薦」標示。
- **著作權**：排行榜和新聞只列出標題並連結到原始來源，不轉載內文。Google 新聞 RSS 的條款限制只能個人使用；若流量變大或用於商業用途，建議改用各媒體官方 RSS，或取得授權的新聞 API。
- **SEO 品質**：Google 會降低大量低品質 AI 內容的排名。建議定期看幾篇文章，調整 `config/site.json` 的 `topics` 題目庫，加入自己的觀點，排名才會長久。
- **健康內容**：提示詞已要求內容保守、不做診斷。如果要推薦保健品，請避免宣稱療效（受食品安全衛生管理法規範）。
