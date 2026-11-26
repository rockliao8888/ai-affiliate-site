"""HTML 版型與各頁面產生（純字串模板，無外部相依）。"""
import hashlib
import re
from html import escape as e
from urllib.parse import quote

NAV = [("index.html", "首頁"), ("stocks.html", "潛力觀察股"), ("etf.html", "ETF 折溢價"),
       ("fx.html", "匯率"), ("music.html", "音樂榜"), ("books.html", "暢銷書"),
       ("movies.html", "電影榜"), ("apps.html", "App/Podcast"), ("news.html", "熱門新聞"),
       ("health.html", "健康小百科"), ("blog/index.html", "專欄")]

CSS = """
:root{--bg:#f6f7fb;--card:#fff;--ink:#1d2433;--mute:#667085;--line:#e6e8ef;--brand:#0f766e;--brand2:#e0f2f1;--up:#d92d20;--down:#039855;--warn:#fff7e6}
@media (prefers-color-scheme:dark){:root{--bg:#0f1419;--card:#171d25;--ink:#e6e9ef;--mute:#98a2b3;--line:#283040;--brand:#2dd4bf;--brand2:#12302d;--warn:#2b2414}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif}
a{color:var(--brand);text-decoration:none}a:hover{text-decoration:underline}
header{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
.top{display:flex;align-items:center;gap:16px;padding:10px 0;flex-wrap:wrap}
.logo{font-weight:800;font-size:20px;color:var(--ink)}.logo span{color:var(--brand)}
nav{display:flex;gap:4px;overflow-x:auto;padding-bottom:8px;scrollbar-width:none}
nav a{white-space:nowrap;padding:4px 10px;border-radius:999px;color:var(--mute);font-size:14px}
nav a.on,nav a:hover{background:var(--brand2);color:var(--brand);text-decoration:none}
main{padding:20px 0 40px}h1{font-size:26px;margin:4px 0 6px}h2{font-size:20px;margin:28px 0 10px}
.sub{color:var(--mute);font-size:14px;margin:0 0 16px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.card h3{margin:0 0 8px;font-size:17px}
.layout{display:grid;grid-template-columns:1fr 300px;gap:20px}@media(max-width:900px){.layout{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px 6px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}th{color:var(--mute);font-weight:600}
.tbl{overflow-x:auto}.up{color:var(--up)}.down{color:var(--down)}
.rank{list-style:none;padding:0;margin:0}.rank li{display:flex;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
.rank b{width:28px;text-align:center;color:var(--brand);font-size:18px}.rank img{width:56px;height:56px;border-radius:8px;object-fit:cover;background:var(--line)}
.rank .t{flex:1;min-width:0}.rank .t div{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rank small{color:var(--mute)}
.btn{display:inline-block;background:var(--brand);color:#fff;padding:6px 14px;border-radius:8px;font-size:14px;font-weight:600}
@media (prefers-color-scheme:dark){.btn{color:#062b27}}.btn:hover{text-decoration:none;opacity:.9}
.aff{border:1px dashed var(--brand);background:var(--brand2)}.aff p{margin:4px 0 10px;font-size:14px;color:var(--mute)}
.tag{font-size:12px;color:var(--mute);border:1px solid var(--line);padding:1px 8px;border-radius:999px}
.note{background:var(--warn);border-radius:10px;padding:10px 14px;font-size:13px;color:var(--mute);margin:16px 0}
.ad{min-height:90px;margin:16px 0}.mini{font-size:13px;color:var(--mute)}
footer{border-top:1px solid var(--line);padding:24px 0;color:var(--mute);font-size:13px;background:var(--card)}
article p{margin:0 0 14px}article ul{padding-left:20px}.tabs a{margin-right:12px}
"""


class Ctx(object):
    def __init__(self, site, products, now):
        self.site, self.products, self.now = site, products, now
        self.aff = site.get("affiliate", {})

    # ---- 聯盟連結 ----
    def apple(self, url):
        tok = self.aff.get("apple_token")
        if not url or not tok:
            return url
        return url + ("&" if "?" in url else "?") + "at=" + quote(tok)

    def book(self, title):
        return self.aff.get("books_link_template", "").replace("{q}", quote(title or ""))

    def shop(self, q):
        return self.aff.get("shop_link_template", "").replace("{q}", quote(q or ""))

    def amazon(self, q):
        tag = self.aff.get("amazon_tag")
        return "https://www.amazon.com/s?k=%s&tag=%s" % (quote(q), quote(tag)) if tag else None

    def pick_products(self, page, n=2, ids=None, exclude=()):
        if ids:
            pool = [p for p in self.products if p["id"] in ids]
        else:
            pool = [p for p in self.products if page in p.get("pages", []) and p["id"] not in exclude] \
                or [p for p in self.products if p["id"] not in exclude]
        # 依日期輪播，讓每天推薦組合不同
        seed = int(hashlib.md5((page + self.now.strftime("%Y%m%d")).encode()).hexdigest(), 16)
        if pool:
            k = seed % len(pool)
            pool = pool[k:] + pool[:k]
        return pool[:n]


def aff_box(ctx, page, n=2, ids=None, exclude=()):
    out = []
    for p in ctx.pick_products(page, n, ids, exclude):
        out.append('<div class="card aff"><span class="tag">贊助推薦</span><h3>%s</h3><p>%s</p>'
                   '<a class="btn" href="%s" rel="sponsored nofollow noopener" target="_blank">%s →</a></div>'
                   % (e(p["name"]), e(p.get("desc", "")), e(p["url"]), e(p.get("cta", "看看"))))
    return "\n".join(out)


def ad_slot(ctx):
    cid = ctx.site.get("adsense_client")
    if not cid:
        return ""
    return ('<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="%s" '
            'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>' % e(cid))


def page(ctx, path, title, body, desc="", side=""):
    depth = path.count("/")
    pre = "../" * depth
    site = ctx.site
    nav = "".join('<a href="%s%s"%s>%s</a>' % (pre, h, ' class="on"' if h == path else "", t) for h, t in NAV)
    head_extra = ""
    if site.get("adsense_client"):
        head_extra += ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=%s" '
                       'crossorigin="anonymous"></script>' % e(site["adsense_client"]))
    if site.get("ga4_id"):
        g = e(site["ga4_id"])
        head_extra += ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script><script>'
                       'window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
                       'gtag("js",new Date());gtag("config","%s");</script>' % (g, g))
    full_title = "%s｜%s" % (title, site["name"]) if title != site["name"] else title
    canonical = site["base_url"].rstrip("/") + "/" + path
    content = ('<div class="layout"><div>%s</div><aside>%s</aside></div>' % (body, side)) if side else body
    return """<!doctype html><html lang="%(lang)s"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%(t)s</title>
<meta name="description" content="%(d)s"><link rel="canonical" href="%(c)s">
<meta property="og:title" content="%(t)s"><meta property="og:description" content="%(d)s"><meta property="og:type" content="website">
<link rel="alternate" type="application/rss+xml" title="RSS" href="%(pre)srss.xml">
<link rel="stylesheet" href="%(pre)sassets/style.css">%(he)s</head><body>
<header><div class="wrap"><div class="top"><a class="logo" href="%(pre)sindex.html">📊 <span>%(name)s</span></a>
<span class="mini">%(tag)s</span></div><nav>%(nav)s</nav></div></header>
<main class="wrap">%(content)s</main>
<footer><div class="wrap">
<p><b>聯盟行銷揭露：</b>本站部分連結為聯盟行銷連結，您透過連結購買或申辦時，本站可能獲得佣金，不影響您的價格。</p>
<p><b>投資免責聲明：</b>本站理財資訊由程式自公開資料彙整並由 AI 輔助撰寫，僅供參考與教育用途，不構成任何投資建議或要約；
投資有風險，請自行判斷並承擔損益。健康內容僅為一般衛教，不能取代專業醫療診斷。</p>
<p>資料來源：臺灣證券交易所 OpenAPI、Apple Marketing Tools RSS、Google 新聞 RSS、ExchangeRate-API。最後更新：%(now)s
｜<a href="%(pre)sabout.html">關於與揭露</a>｜<a href="%(pre)srss.xml">RSS</a></p></div></footer>
</body></html>""" % {
        "lang": site.get("lang", "zh-Hant"), "t": e(full_title), "d": e(desc or site["tagline"]),
        "c": e(canonical), "pre": pre, "he": head_extra, "name": e(site["name"]), "tag": e(site["tagline"]),
        "nav": nav, "content": content, "now": ctx.now.strftime("%Y-%m-%d %H:%M"),
    }


def _pct(v):
    if v is None:
        return "-"
    cls = "up" if v > 0 else ("down" if v < 0 else "")
    return '<span class="%s">%+.2f%%</span>' % (cls, v)


def _rank_list(items, link_fn, sub_fn, limit=25):
    lis = []
    for x in items[:limit]:
        img = '<img loading="lazy" src="%s" alt="">' % e(x["img"]) if x.get("img") else ""
        lis.append('<li><b>%d</b>%s<div class="t"><div><a href="%s" target="_blank" rel="sponsored nofollow noopener">%s</a></div>'
                   '<small>%s</small></div></li>' % (x["rank"], img, e(link_fn(x) or "#"), e(x["name"] or ""), e(sub_fn(x))))
    return '<ol class="rank">%s</ol>' % "".join(lis)


def note_stale(d, key):
    return '<p class="note">⚠️ 今日資料暫時無法取得，顯示上次成功更新的內容。</p>' if d.get("_stale_" + key) else ""


# ------------------------------------------------------------- 頁面 ----
def stocks_page(ctx, d, brief):
    s = d.get("stocks") or {}
    notes = {n["code"]: n["note"] for n in (brief or {}).get("stock_notes", [])}
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%.2f</td><td>%s</td><td>%.1f%%</td><td>%.1f</td><td>%.2f</td><td>%s</td><td>%.1f</td></tr>%s"
        % (e(p["code"]), e(p["name"]), p["close"], _pct(p["chg_pct"]), p["yield"], p["pe"], p["pb"],
           "{:,}".format(p["value_m"]), p["score"],
           ('<tr><td colspan="9" class="mini" style="text-align:left;white-space:normal">🤖 %s</td></tr>' % e(notes[p["code"]]))
           if p["code"] in notes else "")
        for p in s.get("picks", []))
    body = """<h1>AI 量化潛力觀察股</h1><p class="sub">資料日期 %s｜從 %s 檔上市股票中，依「殖利率 ≥4%%、本益比 ≤18、股價淨值比 ≤2、單日成交值 ≥5000 萬」篩選並評分。</p>
%s<p class="note">此為依公開數據的程式化篩選結果，<b>不是買賣建議</b>。高殖利率可能來自股價下跌或一次性配息，請搭配財報與產業前景自行研究。</p>
<div class="card tbl"><table><tr><th>代號</th><th>名稱</th><th>收盤</th><th>漲跌</th><th>殖利率</th><th>本益比</th><th>淨值比</th><th>成交值(百萬)</th><th>分數</th></tr>%s</table></div>%s""" % (
        e(s.get("date", "")), s.get("universe", "-"), note_stale(d, "stocks"), rows, ad_slot(ctx))
    if brief:
        body = ('<div class="card"><h3>📌 %s</h3><p>%s</p><ul>%s</ul><p class="mini">%s</p></div>'
                % (e(brief["headline"]), e(brief["summary"]), "".join("<li>%s</li>" % e(b) for b in brief["bullets"]),
                   e(brief["risk_note"]))) + body
    return page(ctx, "stocks.html", "AI 量化潛力觀察股", body, "每日台股高殖利率、低本益比量化篩選觀察名單", aff_box(ctx, "stocks", 3))


def etf_page(ctx, d, brief):
    t = d.get("etf") or {}

    def tbl(rows):
        return '<div class="card tbl"><table><tr><th>代號</th><th>名稱</th><th>市價</th><th>預估淨值</th><th>折溢價</th></tr>%s</table></div>' % "".join(
            "<tr><td>%s</td><td>%s</td><td>%.2f</td><td>%.2f</td><td>%s</td></tr>" % (
                e(r["code"]), e((r["name"] or "")[:22]), r["price"], r["nav"], _pct(r["premium"])) for r in rows)

    inflow = "".join("<li><b>%s</b> %s <small>受益權單位 +%s</small></li>" % (
        e(r["code"]), e((r["name"] or "")[:18]), "{:,.0f}".format(r["units_chg"])) for r in t.get("inflow", []))
    body = """<h1>ETF 折溢價排行</h1><p class="sub">更新時間 %s｜共 %s 檔｜資料來源：臺灣證券交易所 ETF 預估淨值</p>%s
%s<h2>🔺 溢價最高（市價 > 淨值，買貴的風險）</h2>%s%s<h2>🔻 折價最深（市價 < 淨值）</h2>%s
<h2>💰 今日申購（受益權單位增加）前十</h2><div class="card"><ul>%s</ul></div>
<p class="note">折溢價 =（市價 − 預估淨值）÷ 預估淨值。溢價過高時買進，日後價格回歸淨值可能產生額外損失。</p>""" % (
        e(t.get("updated", "")), t.get("count", "-"), note_stale(d, "etf"),
        ('<div class="card"><h3>🤖 AI 解讀</h3><p>%s</p></div>' % e(brief["etf_note"])) if brief else "",
        tbl(t.get("top_premium", [])), ad_slot(ctx), tbl(t.get("top_discount", [])), inflow)
    return page(ctx, "etf.html", "ETF 折溢價排行", body, "台股 ETF 每日折溢價排行、申購熱度", aff_box(ctx, "etf", 3))


def fx_page(ctx, d):
    f = d.get("fx") or {}
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(r["cur"]), e(r["name"]), r["twd_per"]) for r in f.get("rates", []))
    body = ('<h1>今日匯率</h1><p class="sub">1 單位外幣可換新台幣（中間價參考）｜%s</p>%s<div class="card tbl"><table>'
            '<tr><th>幣別</th><th>名稱</th><th>新台幣</th></tr>%s</table></div><p class="note">實際換匯請以銀行牌告買賣價為準。</p>'
            % (e(f.get("updated", "")), note_stale(d, "fx"), rows))
    return page(ctx, "fx.html", "今日匯率", body, "主要外幣兌新台幣匯率", aff_box(ctx, "fx", 2))


def music_page(ctx, d):
    m = d.get("music") or {}

    def sub(x):
        return "%s · %s" % (x.get("artist") or "", x.get("genre") or "")
    body = ('<h1>本月熱門歌曲排行</h1><p class="sub">Apple Music 熱門播放榜（台灣／美國），每日更新</p>%s'
            '<div class="grid"><div class="card"><h3>🎤 華語／台灣榜</h3>%s</div><div class="card"><h3>🎧 英文／美國榜</h3>%s</div></div>'
            % (note_stale(d, "music"), _rank_list(m.get("zh", []), lambda x: ctx.apple(x["url"]), sub),
               _rank_list(m.get("en", []), lambda x: ctx.apple(x["url"]), sub)))
    return page(ctx, "music.html", "本月中英文歌曲排行", body, "台灣與美國熱門歌曲排行榜", aff_box(ctx, "music", 2))


def books_page(ctx, d):
    b = d.get("books") or {}
    items = b.get("items", [])
    body = ('<h1>暢銷書排行</h1><p class="sub">%s｜點書名可查詢購買</p>%s<div class="card">%s</div>'
            % (e(b.get("source", "")), note_stale(d, "books"),
               _rank_list(items, lambda x: ctx.book(x["name"]) or ctx.apple(x["url"]), lambda x: x.get("artist") or "")))
    return page(ctx, "books.html", "暢銷書排行", body, "本週暢銷書排行榜", aff_box(ctx, "books", 2))


def movies_page(ctx, d):
    m = d.get("movies") or {}
    body = ('<h1>熱門電影排行</h1><p class="sub">iTunes 台灣電影排行</p>%s<div class="card">%s</div>'
            % (note_stale(d, "movies"), _rank_list(m.get("items", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("genre") or "")))
    return page(ctx, "movies.html", "熱門電影排行", body, "本週熱門電影排行榜", aff_box(ctx, "movies", 2))


def apps_page(ctx, d):
    a = d.get("apps") or {}
    body = ('<h1>熱門 App 與 Podcast</h1><p class="sub">App Store 台灣免費榜、Apple Podcasts 台灣熱門榜</p>%s'
            '<div class="grid"><div class="card"><h3>📱 免費 App</h3>%s</div><div class="card"><h3>🎙️ Podcast</h3>%s</div></div>'
            % (note_stale(d, "apps"), _rank_list(a.get("apps", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("genre") or "", 20),
               _rank_list(a.get("podcasts", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("artist") or "", 20)))
    return page(ctx, "apps.html", "熱門 App 與 Podcast 排行", body, "App 與 Podcast 排行榜", aff_box(ctx, "apps", 2))


def news_page(ctx, d):
    n = d.get("news") or {}
    cards = "".join('<div class="card"><h3>%s</h3><ol>%s</ol></div>' % (
        e(sec), "".join('<li><a href="%s" target="_blank" rel="noopener">%s</a></li>' % (e(x["url"]), e(x["title"]))
                        for x in items)) for sec, items in n.items())
    body = '<h1>熱門新聞排行</h1><p class="sub">各分類焦點新聞標題，點擊前往原始媒體閱讀</p>%s<div class="grid">%s</div>' % (note_stale(d, "news"), cards)
    return page(ctx, "news.html", "熱門新聞排行", body, "今日熱門新聞排行", aff_box(ctx, "news", 2))


def post_card(p, pre=""):
    return ('<div class="card"><span class="tag">%s</span> <span class="mini">%s</span><h3><a href="%sblog/%s.html">%s</a></h3>'
            '<p class="mini">%s</p></div>' % (e(p.get("label", "")), e(p["date"]), pre, e(p["slug"]), e(p["title"]), e(p["excerpt"])))


def health_page(ctx, posts):
    hp = [p for p in posts if p.get("cat") == "health"]
    body = ('<h1>健康小百科</h1><p class="sub">AI 輔助整理的日常保健知識，每日新增</p><div class="grid">%s</div>'
            '<p class="note">本區內容為一般衛教資訊，如有身體不適請諮詢醫師。</p>'
            % ("".join(post_card(p) for p in hp) or '<p class="mini">文章即將上線。</p>'))
    return page(ctx, "health.html", "健康小百科", body, "日常保健、睡眠、飲食與運動小知識", aff_box(ctx, "health", 3))


def blog_index(ctx, posts):
    body = '<h1>專欄文章</h1><p class="sub">理財、健康、生活文藝，AI 每日撰寫</p><div class="grid">%s</div>' % "".join(post_card(p, "../") for p in posts)
    return page(ctx, "blog/index.html", "專欄文章", body, "理財、健康、生活專欄", aff_box(ctx, "blog", 2))


def article_page(ctx, p):
    secs = []
    for s in p["sections"]:
        tips = ("<ul>%s</ul>" % "".join("<li>%s</li>" % e(t) for t in s.get("tips", []))) if s.get("tips") else ""
        secs.append("<h2>%s</h2>%s%s" % (e(s["heading"]), "".join("<p>%s</p>" % e(x) for x in s["paragraphs"]), tips))
    mid = len(secs) // 2
    inline = aff_box(ctx, "blog", 3, p.get("product_ids") or None) if p.get("product_ids") else ""
    body = ('<article><span class="tag">%s</span> <span class="mini">%s</span><h1>%s</h1><p class="sub">%s</p>%s%s%s%s</article>'
            '<p class="note">本文由 AI 輔助撰寫並經程式檢核，僅供參考。%s</p>'
            % (e(p.get("label", "")), e(p["date"]), e(p["title"]), e(p["excerpt"]), "".join(secs[:mid]),
               ad_slot(ctx) + ('<h2>🛒 本文相關推薦</h2><div class="grid">%s</div>' % inline if inline else ""),
               "".join(secs[mid:]), "",
               "內容不構成投資建議。" if p.get("cat") == "finance" else ("如有健康疑慮請諮詢醫師。" if p.get("cat") == "health" else "")))
    side = aff_box(ctx, p.get("cat", "blog"), 2, exclude=p.get("product_ids") or ())
    return page(ctx, "blog/%s.html" % p["slug"], p["title"], body, p["excerpt"], side)


HOME_CSS = """
.portal{max-width:1480px}
.search{display:flex;max-width:760px;margin:6px auto 18px;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 6px 4px 18px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
.search input{flex:1;border:0;background:transparent;color:var(--ink);font-size:16px;outline:none;min-width:0}
.search button{border:0;background:var(--brand);color:#fff;border-radius:999px;padding:8px 18px;font-weight:700;cursor:pointer}
.shortcuts{display:grid;grid-template-columns:repeat(auto-fill,minmax(86px,1fr));gap:6px;max-width:1000px;margin:0 auto 22px}
.sc{display:flex;flex-direction:column;align-items:center;gap:6px;padding:8px 4px;border-radius:12px;color:var(--ink);font-size:13px;text-align:center}
.sc:hover{background:var(--card);text-decoration:none}
.sc i{width:48px;height:48px;border-radius:14px;background:var(--card);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-style:normal;font-size:24px}
.sc img{width:28px;height:28px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:14px}
.ptabs{display:flex;gap:4px;overflow-x:auto;margin-bottom:12px;scrollbar-width:none}
.ptabs a{padding:6px 14px;border-radius:10px;color:var(--ink);font-weight:600;white-space:nowrap}
.ptabs a.on,.ptabs a:hover{background:var(--brand2);color:var(--brand);text-decoration:none}
.pgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:1100px){.pgrid{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.pgrid{grid-template-columns:1fr}}
.span2{grid-column:span 2}@media(max-width:620px){.span2{grid-column:auto}}
.tile{position:relative;border-radius:14px;overflow:hidden;background:var(--bg);border:1px solid var(--line);min-height:300px;display:flex;flex-direction:column}
.tile .pad{padding:14px}.tile h3{margin:0 0 10px;font-size:16px}
.ov{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:18px;color:#fff;background:linear-gradient(transparent 30%,rgba(0,0,0,.82))}
.ov a,.ov h2{color:#fff}.ov .tag{align-self:flex-start}.ov h2{font-size:24px;margin:6px 0;line-height:1.35}.ov small{opacity:.85}
.bgimg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.g1{background:linear-gradient(135deg,#0f766e,#164e63)}.g2{background:linear-gradient(135deg,#7c2d12,#be123c)}
.g3{background:linear-gradient(135deg,#312e81,#6d28d9)}.g4{background:linear-gradient(135deg,#854d0e,#ca8a04)}.g5{background:linear-gradient(135deg,#1e3a8a,#0284c7)}
.car{position:relative;min-height:380px}.slide{position:absolute;inset:0;opacity:0;transition:opacity .6s}.slide.on{opacity:1;z-index:1}
.car .nav{position:absolute;top:50%;z-index:2;border:0;background:rgba(0,0,0,.45);color:#fff;width:34px;height:48px;cursor:pointer;font-size:18px}
.car .prev{left:0;border-radius:0 8px 8px 0}.car .next{right:0;border-radius:8px 0 0 8px}
.dots{position:absolute;bottom:10px;right:16px;z-index:2;display:flex;gap:5px}.dots b{width:7px;height:7px;border-radius:9px;background:rgba(255,255,255,.5);cursor:pointer}.dots b.on{width:20px;background:#fff}
.lst{list-style:none;margin:0;padding:0}.lst li{padding:7px 0;border-bottom:1px solid var(--line);font-size:14px;line-height:1.5}
.lst li:last-child{border:0}.lst small{color:var(--mute);display:block;font-size:12px}
.thumbs li{display:flex;gap:10px;align-items:center}.thumbs img{width:44px;height:44px;border-radius:8px;object-fit:cover;flex:none}
.wx .big{font-size:48px;font-weight:300;display:flex;align-items:center;gap:8px}.wx select{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:3px 6px}
.wx .hrs{display:grid;grid-template-columns:repeat(6,1fr);text-align:center;font-size:12px;gap:4px;margin-top:8px}.wx .hrs b{display:block;font-size:20px;font-weight:400}
.more{margin-top:auto;padding:10px 14px;font-size:13px;border-top:1px solid var(--line)}
.sp{position:absolute;top:10px;left:10px;z-index:2;font-size:11px;background:rgba(0,0,0,.55);color:#fff;padding:1px 8px;border-radius:999px}
"""

WX_JS = """
(function(){var C={"台北":[25.04,121.56],"新北":[25.01,121.46],"基隆":[25.13,121.74],"桃園":[24.99,121.30],"新竹":[24.80,120.97],
"台中":[24.15,120.67],"彰化":[24.08,120.54],"嘉義":[23.48,120.45],"台南":[22.99,120.21],"高雄":[22.63,120.30],"屏東":[22.67,120.49],
"宜蘭":[24.75,121.75],"花蓮":[23.98,121.60],"台東":[22.76,121.14],"澎湖":[23.57,119.58],"金門":[24.43,118.32]};
function ic(c){return c==0?"☀️":c<3?"🌤️":c<4?"☁️":c<50?"🌫️":c<70?"🌧️":c<80?"🌨️":c<95?"🌦️":"⛈️"}
var sel=document.getElementById("wxc"),box=document.getElementById("wxb");if(!sel)return;
Object.keys(C).forEach(function(k){var o=document.createElement("option");o.textContent=k;sel.appendChild(o)});
try{var s=localStorage.getItem("wxcity");if(s&&C[s])sel.value=s}catch(e){}
function load(){var p=C[sel.value];try{localStorage.setItem("wxcity",sel.value)}catch(e){}
fetch("https://api.open-meteo.com/v1/forecast?latitude="+p[0]+"&longitude="+p[1]+"&current=temperature_2m,relative_humidity_2m,weather_code&hourly=temperature_2m,weather_code&forecast_hours=7&timezone=Asia%2FTaipei")
.then(function(r){return r.json()}).then(function(j){var c=j.current,h=j.hourly,hs="";for(var i=1;i<7;i++){hs+="<div>"+h.time[i].slice(11,16)+"<b>"+ic(h.weather_code[i])+"</b>"+Math.round(h.temperature_2m[i])+"°</div>"}
box.innerHTML='<div class="big">'+ic(c.weather_code)+" "+Math.round(c.temperature_2m)+'°C</div><div class="mini">💧 濕度 '+c.relative_humidity_2m+'%</div><div class="hrs">'+hs+"</div>"})
.catch(function(){box.innerHTML='<p class="mini">天氣暫時無法載入</p>'})}
sel.onchange=load;load()})();
(function(){var s=document.querySelectorAll(".slide"),d=document.querySelectorAll(".dots b"),i=0,t;if(!s.length)return;
function go(n){s[i].classList.remove("on");d[i].classList.remove("on");i=(n+s.length)%s.length;s[i].classList.add("on");d[i].classList.add("on")}
function auto(){clearInterval(t);t=setInterval(function(){go(i+1)},6000)}
document.querySelector(".prev").onclick=function(){go(i-1);auto()};document.querySelector(".next").onclick=function(){go(i+1);auto()};
d.forEach(function(b,k){b.onclick=function(){go(k);auto()}});auto()})();
"""


def _shortcuts(ctx):
    out = []
    for s in ctx.site.get("shortcuts", []):
        ico = ('<img loading="lazy" alt="" src="https://www.google.com/s2/favicons?sz=64&domain=%s">' % e(s["domain"])) \
            if s.get("domain") else e(s.get("icon", "🔗"))
        ext = s["url"].startswith("http")
        rel = ' target="_blank" rel="%snoopener"' % ("sponsored nofollow " if s.get("sponsored") else "") if ext else ""
        out.append('<a class="sc" href="%s"%s><i>%s</i>%s</a>' % (e(s["url"]), rel, ico, e(s["name"])))
    return '<div class="shortcuts">%s</div>' % "".join(out)


def _slide(cls, href, tag, title, sub, img=None, ext=False):
    tgt = ' target="_blank" rel="noopener"' if ext else ""
    bg = '<img class="bgimg" alt="" src="%s">' % e(img) if img else ""
    return ('<a class="slide %s" href="%s"%s>%s<div class="ov"><span class="tag" style="color:#fff;border-color:rgba(255,255,255,.5)">%s</span>'
            '<h2>%s</h2><small>%s</small></div></a>' % (cls, e(href), tgt, bg, e(tag), e(title), e(sub)))


def _tile(title, href, inner, cls=""):
    return ('<div class="tile %s"><div class="pad"><h3><a href="%s">%s</a></h3>%s</div><a class="more" href="%s">看更多 →</a></div>'
            % (cls, href, title, inner, href))


def _aff_tile(p, cls):
    return ('<a class="tile %s" href="%s" target="_blank" rel="sponsored nofollow noopener"><span class="sp">贊助</span>'
            '<div class="ov"><h2>%s</h2><small>%s</small><span class="btn" style="margin-top:10px;align-self:flex-start">%s →</span></div></a>'
            % (cls, e(p["url"]), e(p["name"]), e(p.get("desc", "")), e(p.get("cta", "看看"))))


def home_page(ctx, d, brief, posts):
    s, t, m, n, b, mv, ap = (d.get(k) or {} for k in ("stocks", "etf", "music", "news", "books", "movies", "apps"))
    fx = d.get("fx") or {}

    # ---- 輪播大圖 ----
    slides = []
    if brief:
        slides.append(_slide("g1", "stocks.html", "AI 每日市場觀察", brief["headline"], brief["summary"][:80] + "…"))
    for p in posts[:2]:
        slides.append(_slide("g3", "blog/%s.html" % p["slug"], p.get("label", "專欄"), p["title"], p["excerpt"][:80]))
    if t.get("top_premium"):
        x = t["top_premium"][0]
        slides.append(_slide("g2", "etf.html", "ETF 溢價警示", "%s %s 溢價 %+.2f%%" % (x["code"], x["name"][:14], x["premium"]),
                             "買在溢價可能多付錢，看今日完整折溢價排行"))
    if mv.get("items"):
        x = mv["items"][0]
        slides.append(_slide("", ctx.apple(x["url"]), "本週電影冠軍", x["name"], x.get("summary") or x.get("genre", ""),
                             re.sub(r"/\d+x\d+bb\.", "/600x900bb.", x.get("img", "")), True))
    if m.get("zh"):
        x = m["zh"][0]
        slides.append(_slide("", "music.html", "華語熱歌第一名", x["name"], x.get("artist") or "", x["img"].replace("200x200", "600x600")))
    for x in (n.get("焦點") or [])[:2]:
        slides.append(_slide("g5", x["url"], "焦點新聞 · " + (x.get("source") or ""), x["title"].rsplit(" - ", 1)[0], "點擊閱讀全文", ext=True))
    carousel = ('<div class="tile span2 car">%s<button class="nav prev" aria-label="上一則">‹</button><button class="nav next" aria-label="下一則">›</button>'
                '<div class="dots">%s</div></div>' % ("".join(slides), "".join("<b></b>" for _ in slides))) if slides else ""
    carousel = carousel.replace('class="slide ', 'class="slide on ', 1).replace("<b></b>", '<b class="on"></b>', 1)

    def news_li(items, k=6):
        return '<ul class="lst">%s</ul>' % "".join(
            '<li><a href="%s" target="_blank" rel="noopener">%s</a><small>%s</small></li>'
            % (e(x["url"]), e(x["title"].rsplit(" - ", 1)[0]), e(x.get("source") or "")) for x in items[:k])

    def thumbs(items, link, sub, k=5):
        return '<ul class="lst thumbs">%s</ul>' % "".join(
            '<li><img loading="lazy" alt="" src="%s"><div><a href="%s" target="_blank" rel="sponsored nofollow noopener">%d. %s</a><small>%s</small></div></li>'
            % (e(x.get("img") or ""), e(link(x) or "#"), x["rank"], e(x["name"]), e(sub(x))) for x in items[:k])

    stock_li = '<ul class="lst">%s</ul>' % "".join(
        "<li>%s %s <span style=\"float:right\">殖利率 %.1f%%</span><small>本益比 %.1f · 淨值比 %.2f</small></li>"
        % (e(x["code"]), e(x["name"]), x["yield"], x["pe"], x["pb"]) for x in s.get("picks", [])[:6])
    etf_li = '<ul class="lst">%s</ul>' % "".join(
        '<li>%s %s <span style="float:right">%s</span></li>' % (e(x["code"]), e((x["name"] or "")[:12]), _pct(x["premium"]))
        for x in t.get("top_premium", [])[:4] + t.get("top_discount", [])[:3])
    fx_li = '<ul class="lst">%s</ul>' % "".join(
        '<li>%s %s <span style="float:right">%s</span></li>' % (e(x["cur"]), e(x["name"]), x["twd_per"]) for x in fx.get("rates", [])[:6])
    post_li = '<ul class="lst">%s</ul>' % ("".join(
        '<li><a href="blog/%s.html">%s</a><small>%s · %s</small></li>' % (e(p["slug"]), e(p["title"]), e(p.get("label", "")), e(p["date"]))
        for p in posts[:6]) or "<li>文章即將上線</li>")
    affs = ctx.pick_products("home", 3) + ctx.pick_products("health", 1) + ctx.pick_products("movies", 1)
    gcls = ["g4", "g3", "g1", "g2", "g5"]

    tiles = [
        carousel,
        _tile("🔥 熱門故事", "news.html", news_li(n.get("焦點", []))),
        '<div class="tile wx"><div class="pad"><h3>🌤️ 天氣 <select id="wxc" aria-label="選擇城市"></select></h3><div id="wxb" class="mini">載入中…</div></div>'
        '<a class="more" href="https://www.cwa.gov.tw/" target="_blank" rel="noopener">中央氣象署 →</a></div>',
        _tile("📈 AI 潛力觀察股", "stocks.html", stock_li),
        _tile("⚖️ ETF 折溢價", "etf.html", etf_li),
        _aff_tile(affs[0], gcls[0]) if affs else "",
        _tile("💹 財經新聞", "news.html", news_li(n.get("財經", []))),
        _tile("🎤 華語熱歌", "music.html", thumbs(m.get("zh", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("artist") or "")),
        _tile("🎧 英文熱歌", "music.html", thumbs(m.get("en", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("artist") or "")),
        _tile("🎬 熱門電影", "movies.html", thumbs(mv.get("items", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("genre") or "")),
        _aff_tile(affs[1], gcls[1]) if len(affs) > 1 else "",
        _tile("📚 暢銷書", "books.html", thumbs(b.get("items", []), lambda x: ctx.book(x["name"]), lambda x: x.get("artist") or "")),
        _tile("💱 今日匯率", "fx.html", fx_li),
        _tile("🩺 健康新聞", "news.html", news_li(n.get("健康", []))),
        _aff_tile(affs[2], gcls[2]) if len(affs) > 2 else "",
        _tile("🎙️ 熱門 Podcast", "apps.html", thumbs(ap.get("podcasts", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("artist") or "")),
        _tile("📱 熱門 App", "apps.html", thumbs(ap.get("apps", []), lambda x: ctx.apple(x["url"]), lambda x: x.get("genre") or "")),
        _tile("✍️ 最新專欄", "blog/index.html", post_li),
        _tile("💻 科技新聞", "news.html", news_li(n.get("科技", []))),
        _aff_tile(affs[3], gcls[3]) if len(affs) > 3 else "",
        _tile("🎭 娛樂新聞", "news.html", news_li(n.get("娛樂", []))),
    ]
    tabs = [("index.html", "探索"), ("stocks.html", "財經"), ("etf.html", "ETF"), ("music.html", "音樂"), ("movies.html", "影音"),
            ("books.html", "閱讀"), ("news.html", "新聞"), ("health.html", "健康"), ("blog/index.html", "專欄")]
    body = ('<style>%s</style><div class="portal">'
            '<form class="search" action="https://www.google.com/search" target="_blank" role="search">'
            '<input name="q" placeholder="搜尋網路…" aria-label="搜尋"><button>搜尋</button></form>%s'
            '<div class="panel"><div class="ptabs">%s</div><div class="pgrid">%s</div></div>%s</div><script>%s</script>'
            % (HOME_CSS, _shortcuts(ctx), "".join('<a href="%s"%s>%s</a>' % (h, ' class="on"' if h == "index.html" else "", x) for h, x in tabs),
               "".join(tiles), ad_slot(ctx), WX_JS))
    return page(ctx, "index.html", ctx.site["name"], body, ctx.site["tagline"]).replace('<main class="wrap">', '<main class="wrap portal">', 1)


def about_page(ctx):
    body = """<h1>關於本站與揭露</h1><div class="card"><article>
<p>%s 以程式自動彙整公開資料（臺灣證券交易所、Apple 排行榜、Google 新聞、匯率 API），並由 AI 協助撰寫摘要與專欄，每日自動更新。</p>
<h2>聯盟行銷揭露</h2><p>本站部分連結為聯盟行銷連結（標示「贊助推薦」或連往購物平台），若您透過連結消費，本站可能獲得佣金，您的購買價格不會因此提高。商品推薦依主題相關性自動配對。</p>
<h2>投資免責</h2><p>本站所有理財內容為數據整理與教育資訊，非證券投資顧問業務，不提供個別有價證券之買賣建議。投資前請詳閱公開說明書並自行評估風險。</p>
<h2>AI 內容說明</h2><p>專欄由 AI 輔助產生，可能有疏漏；若發現錯誤歡迎來信更正。</p>
<h2>著作權</h2><p>排行榜與新聞僅列標題並連結至原始來源，著作權屬原權利人所有。</p></article></div>""" % e(ctx.site["name"])
    return page(ctx, "about.html", "關於與揭露", body)
