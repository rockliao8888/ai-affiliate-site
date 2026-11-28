"""主流程：抓資料 → AI 撰文 → 產生靜態網站 → 社群推廣。

用法：
  python scripts/build.py                 # 全部（抓資料 + AI + 建置）
  python scripts/build.py --articles 0    # 不寫新文章（只更新排行）
  python scripts/build.py --no-fetch      # 用既有快照重建頁面
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from html import escape as e

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai  # noqa: E402
import fetchers  # noqa: E402
import render as R  # noqa: E402
import social  # noqa: E402
from util import DATA_DIR, PUBLIC_DIR, config, load_json, now_tw, save_json, write_text  # noqa: E402

LATEST = os.path.join(DATA_DIR, "latest")
POSTS = os.path.join(DATA_DIR, "posts")


def gather(do_fetch):
    data = {}
    for key, fn in fetchers.ALL.items():
        path = os.path.join(LATEST, key + ".json")
        val = None
        if do_fetch:
            try:
                val = fn()
                print("[fetch] %-7s ok" % key if val else "[fetch] %-7s empty" % key)
            except Exception as ex:  # noqa: BLE001
                print("[fetch] %-7s FAILED: %s" % (key, ex))
        if val:
            save_json(path, val)
        else:
            val = load_json(path)
            if do_fetch and val:
                data["_stale_" + key] = True
        data[key] = val
    return data


def get_brief(site, d):
    path = os.path.join(LATEST, "brief.json")
    old = load_json(path)
    stamp = "%s|%s" % ((d.get("stocks") or {}).get("date"), (d.get("etf") or {}).get("updated", "")[:8])
    if old and old.get("_stamp") == stamp:
        return old  # 資料沒變就不重複花 AI 費用
    new = ai.market_brief(site["name"], d.get("stocks"), d.get("etf"), d.get("fx"))
    if new:
        new["_stamp"] = stamp
        save_json(path, new)
        print("[ai] market brief updated")
        return new
    return old


ARTICLES = os.path.join(os.path.dirname(DATA_DIR), "articles")
CAT_LABELS = {"finance": "理財", "health": "健康小百科", "culture": "生活文藝"}


def parse_markdown_post(path):
    """讀取 articles/ 裡手寫的 Markdown 文章（格式見 articles/README.md）。格式錯誤回傳 None。"""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read().replace("\r\n", "\n")
    meta, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip('"').strip("'")
        body = m.group(2)
    name = os.path.splitext(os.path.basename(path))[0]
    if name.lower() == "readme" or meta.get("draft", "").lower() in ("true", "yes", "1"):
        return None
    sections, cur, para = [], {"heading": "", "paragraphs": [], "tips": []}, []

    def flush():
        if para:
            cur["paragraphs"].append(" ".join(para))
            del para[:]

    for raw in body.split("\n"):
        line = raw.strip()
        if line.startswith("# ") and not meta.get("title"):
            meta["title"] = line[2:].strip()
        elif line.startswith("## "):
            flush()
            if cur["paragraphs"] or cur["tips"] or cur["heading"]:
                sections.append(cur)
            cur = {"heading": line[3:].strip(), "paragraphs": [], "tips": []}
        elif line.startswith(("- ", "* ")):
            flush()
            cur["tips"].append(line[2:].strip())
        elif not line:
            flush()
        elif not line.startswith("# "):
            para.append(line)
    flush()
    if cur["paragraphs"] or cur["tips"] or cur["heading"]:
        sections.append(cur)
    title = meta.get("title")
    if not title or not sections:
        print("[posts] skipped (missing title or content):", os.path.basename(path))
        return None
    dm = re.match(r"(\d{4}-\d{2}-\d{2})-?(.*)$", name)
    date = meta.get("date") or (dm.group(1) if dm else now_tw().strftime("%Y-%m-%d"))
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    if not slug or slug != name.lower() or slug == re.sub(r"[^0-9-]", "", slug):
        slug = "%s-%s" % (date.replace("-", ""), hashlib.md5(name.encode("utf-8")).hexdigest()[:6])
    cat = meta.get("category", "culture").lower()
    first = next((x for s in sections for x in s["paragraphs"] if not x.startswith("![")), "")
    excerpt = meta.get("excerpt") or (first[:80] + ("…" if len(first) > 80 else ""))
    excerpt = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", excerpt).replace("**", "")
    return {"title": title, "slug": slug, "date": date, "created": date, "cat": cat,
            "label": meta.get("label") or CAT_LABELS.get(cat, "專欄"), "excerpt": excerpt, "sections": sections,
            "product_ids": [x.strip() for x in meta.get("products", "").split(",") if x.strip()], "manual": True}


def load_posts():
    posts = [load_json(p) for p in glob.glob(os.path.join(POSTS, "*.json"))]
    posts += [parse_markdown_post(p) for p in sorted(glob.glob(os.path.join(ARTICLES, "*.md")))]
    posts = [p for p in posts if p and p.get("sections")]
    posts.sort(key=lambda p: (p["date"], p.get("created", "")), reverse=True)
    return posts


def topic_context(cat, d):
    if cat == "finance":
        return {"stock_screen": (d.get("stocks") or {}).get("picks", [])[:8],
                "etf_premium": (d.get("etf") or {}).get("top_premium", [])[:5],
                "fx": (d.get("fx") or {}).get("rates", [])}
    if cat == "health":
        return {"health_news_titles": [x["title"] for x in (d.get("news") or {}).get("健康", [])[:10]]}
    return {"songs_tw": [(x["name"], x["artist"]) for x in (d.get("music") or {}).get("zh", [])[:10]],
            "songs_us": [(x["name"], x["artist"]) for x in (d.get("music") or {}).get("en", [])[:10]],
            "books": [x["name"] for x in (d.get("books") or {}).get("items", [])[:10]],
            "movies": [x["name"] for x in (d.get("movies") or {}).get("items", [])[:10]],
            "podcasts": [x["name"] for x in (d.get("apps") or {}).get("podcasts", [])[:10]]}


CAT_TAGS = {"finance": {"finance", "etf", "stock", "fx", "book"},
            "health": {"health", "sleep", "fitness", "gut"},
            "culture": {"culture", "music", "movie", "book", "podcast"}}


def write_articles(site, d, products, posts, n):
    topics = site.get("topics", [])
    if not topics or n <= 0:
        return []
    today = now_tw()
    recent = [p["title"] for p in posts]
    used = {p.get("idea") for p in posts[:60]}
    created = []
    for i in range(n):
        t = topics[(today.timetuple().tm_yday * n + i) % len(topics)]
        ideas = [x for x in t["ideas"] if x not in used] or t["ideas"]
        idea = ideas[(today.toordinal() + i) % len(ideas)]
        prods = [p for p in products if CAT_TAGS.get(t["cat"], set()) & set(p.get("tags", []))]
        art = ai.write_article(site["name"], idea, topic_context(t["cat"], d), prods, recent)
        if not art:
            print("[ai] article skipped:", idea)
            continue
        slug = re.sub(r"[^a-z0-9-]+", "-", art["slug"].lower()).strip("-")[:60] or "post"
        slug = "%s-%s" % (today.strftime("%Y%m%d"), slug)
        valid_ids = {p["id"] for p in prods}
        art.update({"slug": slug, "date": today.strftime("%Y-%m-%d"), "created": today.isoformat(),
                    "cat": t["cat"], "label": t["label"], "idea": idea,
                    "product_ids": [x for x in art.get("product_ids", []) if x in valid_ids]})
        save_json(os.path.join(POSTS, slug + ".json"), art)
        used.add(idea)
        recent.insert(0, art["title"])
        created.append(art)
        print("[ai] article:", art["title"])
    return created


def write_feeds(ctx, posts):
    base = ctx.site["base_url"].rstrip("/")
    urls = [h for h, _ in R.NAV] + ["about.html"] + ["blog/%s.html" % p["slug"] for p in posts]
    write_text(os.path.join(PUBLIC_DIR, "sitemap.xml"),
               '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>'
               % "".join("<url><loc>%s/%s</loc><lastmod>%s</lastmod></url>" % (base, u, ctx.now.strftime("%Y-%m-%d")) for u in urls))
    write_text(os.path.join(PUBLIC_DIR, "robots.txt"), "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % base)
    items = "".join("<item><title>%s</title><link>%s/blog/%s.html</link><guid>%s/blog/%s.html</guid><description>%s</description><pubDate>%s</pubDate></item>"
                    % (e(p["title"]), base, p["slug"], base, p["slug"], e(p["excerpt"]), e(p["date"])) for p in posts[:30])
    write_text(os.path.join(PUBLIC_DIR, "rss.xml"),
               '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>%s</title><link>%s</link><description>%s</description>%s</channel></rss>'
               % (e(ctx.site["name"]), base, e(ctx.site["tagline"]), items))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--articles", type=int, default=None)
    args = ap.parse_args()

    site = config("site.json")
    products = config("affiliates.json").get("products", [])
    d = gather(not args.no_fetch)
    brief = get_brief(site, d) if (d.get("stocks") or d.get("etf")) else None
    posts = load_posts()
    n = site.get("articles_per_run", 1) if args.articles is None else args.articles
    new_posts = write_articles(site, d, products, posts, n)
    posts = load_posts()

    ctx = R.Ctx(site, products, now_tw())
    pages = {
        "index.html": R.home_page(ctx, d, brief, posts),
        "stocks.html": R.stocks_page(ctx, d, brief),
        "etf.html": R.etf_page(ctx, d, brief),
        "fx.html": R.fx_page(ctx, d),
        "music.html": R.music_page(ctx, d),
        "books.html": R.books_page(ctx, d),
        "movies.html": R.movies_page(ctx, d),
        "top10.html": R.top10_page(ctx, d),
        "apps.html": R.apps_page(ctx, d),
        "news.html": R.news_page(ctx, d),
        "health.html": R.health_page(ctx, posts),
        "blog/index.html": R.blog_index(ctx, posts),
        "about.html": R.about_page(ctx),
        "search.html": R.search_page(ctx),
    }
    for p in posts:
        pages["blog/%s.html" % p["slug"]] = R.article_page(ctx, p)
    for path, html in pages.items():
        write_text(os.path.join(PUBLIC_DIR, path), html)
    write_text(os.path.join(PUBLIC_DIR, "assets", "style.css"), R.CSS)
    write_text(os.path.join(PUBLIC_DIR, "search.json"),
               json.dumps(R.search_index(ctx, d, posts), ensure_ascii=False, separators=(",", ":")))
    write_text(os.path.join(PUBLIC_DIR, ".nojekyll"), "")
    img_src = os.path.join(ARTICLES, "images")  # 手寫文章用的圖片 → /images/
    if os.path.isdir(img_src):
        shutil.copytree(img_src, os.path.join(PUBLIC_DIR, "images"), dirs_exist_ok=True)
    if site.get("custom_domain"):  # GitHub Pages 自訂網域
        write_text(os.path.join(PUBLIC_DIR, "CNAME"), site["custom_domain"] + "\n")
    write_feeds(ctx, posts)
    print("[build] %d pages -> %s" % (len(pages), PUBLIC_DIR))

    base = site["base_url"].rstrip("/")
    for p in new_posts:
        sent = social.announce(p.get("social_post") or p["title"], "%s/blog/%s.html" % (base, p["slug"]))
        if sent:
            print("[social] posted to", ", ".join(sent))


if __name__ == "__main__":
    main()
