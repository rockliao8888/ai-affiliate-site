# 手寫文章放這裡

在這個資料夾新增一個 `.md` 檔案，網站幾分鐘內就會自動重建，文章會出現在「專欄」、首頁「最新專欄」和站內搜尋裡。
健康類文章也會出現在「健康小百科」。

## 檔名

`年-月-日-英文網址.md`，例如 `2026-11-28-etf-for-beginners.md`。

- 檔名會變成文章網址：`https://www.yours-news.com/blog/2026-11-28-etf-for-beginners.html`
- 網址部分只用小寫英文、數字和 `-`。用中文檔名也可以，但網址會變成一串亂碼。
- 文章發布後不要再改檔名，否則舊網址會失效。

## 範本（整段複製後修改）

```markdown
---
title: 月薪族如何用 ETF 建立被動收入
date: 2026-11-28
category: finance
excerpt: 一句話摘要，會顯示在文章列表和 Google 搜尋結果。
products: broker-account, book-investing
---

第一段是開場白，不用加標題。

## 第一個小標題

段落文字。空一行就是新段落。

**粗體字** 這樣寫；連結寫成 [看這裡](https://example.com)。

- 條列重點一
- 條列重點二

![圖片說明](https://圖片網址.jpg)

## 第二個小標題

更多內容……
```

## 欄位說明

| 欄位 | 必填 | 說明 |
|---|---|---|
| `title` | ✅ | 文章標題 |
| `date` | | 發布日期，沒填就用檔名開頭的日期 |
| `category` | | `finance`（理財）、`health`（健康）、`culture`（生活文藝），預設 `culture` |
| `excerpt` | | 摘要，沒填就自動取第一段前 80 字 |
| `products` | | 文中要放的推薦商品，填 `config/affiliates.json` 裡的 `id`，用逗號分隔 |
| `draft` | | 填 `true` 就先不發布 |

## 注意

- 文章內的連結會自動加上 `rel="sponsored nofollow"`，適合放聯盟推廣連結。
- 理財文章不要寫個股買賣建議或目標價；健康文章不要宣稱療效。
- 圖片：把圖片上傳到 `articles/images/` 資料夾（檔名用英文），文章裡寫 `![說明](https://www.yours-news.com/images/檔名.jpg)`。請只用你自己拍的或有授權的圖片。
