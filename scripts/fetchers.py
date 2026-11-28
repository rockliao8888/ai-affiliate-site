"""各類公開資料抓取。每個 fetcher 失敗時回傳 None，由 build.py 改用上次快照。"""
import csv
import io
import os
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

from util import http_get, http_json, to_float

APPLE = "https://rss.applemarketingtools.com/api/v2/{cc}/{kind}/{chart}/{n}/{typ}.json"


# ---------------------------------------------------------------- 理財 ----
def fetch_etf_premium():
    """證交所 ETF 即時預估折溢價（每 15 秒更新，收盤後為最終值）。"""
    raw = http_json("https://mis.twse.com.tw/stock/data/all_etf.txt")
    rows = []
    for grp in raw.get("a1", []):
        for m in grp.get("msgArray", []) or []:
            prem, price, nav = to_float(m.get("g")), to_float(m.get("e")), to_float(m.get("f"))
            if prem is None or not price or not nav:
                continue
            rows.append({
                "code": m.get("a"), "name": m.get("b"), "price": price, "nav": nav,
                "premium": prem, "prev_nav": to_float(m.get("h")),
                "units": to_float(m.get("c")), "units_chg": to_float(m.get("d")),
                "time": "%s %s" % (m.get("i", ""), m.get("j", "")),
            })
    if not rows:
        return None
    rows.sort(key=lambda r: r["premium"], reverse=True)
    return {
        "updated": rows[0]["time"],
        "count": len(rows),
        "top_premium": rows[:20],
        "top_discount": sorted(rows, key=lambda r: r["premium"])[:20],
        "inflow": sorted([r for r in rows if r["units_chg"]], key=lambda r: -(r["units_chg"] or 0))[:10],
    }


def fetch_stock_screen():
    """量化篩選：高殖利率 + 合理本益比 + 低股價淨值比 + 足夠成交值。"""
    val = http_json("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")
    day = {d["Code"]: d for d in http_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")}
    picks = []
    for v in val:
        code = v.get("Code", "")
        if not (len(code) == 4 and code.isdigit()):
            continue  # 排除 ETF / 權證
        pe, dy, pb = to_float(v.get("PEratio")), to_float(v.get("DividendYield")), to_float(v.get("PBratio"))
        d = day.get(code)
        if not d or pe is None or dy is None or pb is None:
            continue
        close, chg = to_float(d.get("ClosingPrice")), to_float(d.get("Change"), 0)
        tv = to_float(d.get("TradeValue"), 0)
                # 本益比 <5 或殖利率 >12% 多半是一次性業外收益或股價崩跌，排除以免誤導
        if not close or tv < 5e7 or not (5 <= pe <= 18) or not (4 <= dy <= 12) or pb > 2:
            continue
        # 分數：殖利率越高、本益比與淨值比越低越好；成交值給少量加分
        score = dy * 2.0 + (18 - pe) * 0.6 + (2 - pb) * 3 + min(tv / 1e9, 3)
        picks.append({
            "code": code, "name": v.get("Name"), "close": close,
            "chg_pct": round(chg / (close - chg) * 100, 2) if close != chg else 0,
            "pe": pe, "yield": dy, "pb": pb, "value_m": round(tv / 1e6), "score": round(score, 1),
        })
    picks.sort(key=lambda r: -r["score"])
    if not picks:
        return None
    date = val[0].get("Date", "")
    return {"date": roc_to_iso(date), "picks": picks[:20], "universe": len(val)}


def fetch_fx():
    j = http_json("https://open.er-api.com/v6/latest/TWD")
    r = j.get("rates", {})
    out = []
    for cur, name in [("USD", "美元"), ("JPY", "日圓"), ("EUR", "歐元"), ("CNY", "人民幣"),
                      ("HKD", "港幣"), ("KRW", "韓元"), ("GBP", "英鎊"), ("AUD", "澳幣")]:
        if r.get(cur):
            out.append({"cur": cur, "name": name, "twd_per": round(1 / r[cur], 4 if cur in ("JPY", "KRW") else 3)})
    return {"updated": j.get("time_last_update_utc"), "rates": out} if out else None


def roc_to_iso(s):
    s = str(s)
    if len(s) == 7 and s.isdigit():
        return "%d-%s-%s" % (int(s[:3]) + 1911, s[3:5], s[5:])
    return s


# ---------------------------------------------------------- 生活排行 ----
def _apple(cc, kind, chart, typ, n=25):
    j = http_json(APPLE.format(cc=cc, kind=kind, chart=chart, n=n, typ=typ))
    seen, res = set(), []
    for x in j.get("feed", {}).get("results", []):  # 去除同名重複（不同版本）
        if x.get("name") not in seen:
            seen.add(x.get("name"))
            res.append(x)
    return [{
        "rank": i + 1, "name": x.get("name"), "artist": x.get("artistName"),
        "img": (x.get("artworkUrl100") or "").replace("100x100", "200x200"),
        "url": x.get("url"), "genre": (x.get("genres") or [{}])[0].get("name", ""),
    } for i, x in enumerate(res)]


def fetch_music():
    zh = _apple("tw", "music", "most-played", "songs")
    en = _apple("us", "music", "most-played", "songs")
    return {"zh": zh, "en": en} if (zh or en) else None


def fetch_books():
    for cc, chart in [("tw", "top-paid"), ("tw", "top-free"), ("us", "top-paid")]:
        try:
            items = _apple(cc, "books", chart, "books")
        except RuntimeError:
            continue
        if items:
            return {"source": "Apple Books %s %s" % (cc.upper(), chart), "items": items}
    return None


def fetch_movies():
    j = http_json("https://itunes.apple.com/tw/rss/topmovies/limit=25/json")
    out = []
    for i, e in enumerate(j.get("feed", {}).get("entry", [])):
        imgs = e.get("im:image", [])
        out.append({
            "rank": i + 1, "name": e.get("im:name", {}).get("label"),
            "genre": e.get("category", {}).get("attributes", {}).get("label", ""),
            "img": imgs[-1]["label"] if imgs else "",
            "url": e.get("id", {}).get("label"),
            "summary": (e.get("summary", {}).get("label") or "")[:120],
        })
    return {"items": out} if out else None


def fetch_apps_podcasts():
    apps = _apple("tw", "apps", "top-free", "apps")
    pods = _apple("tw", "podcasts", "top", "podcasts")
    return {"apps": apps, "podcasts": pods} if (apps or pods) else None


def fetch_news():
    """Google 新聞 RSS：只取標題、來源與連結（不轉載內文）。"""
    sections = {
        "焦點": "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "財經": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "科技": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "健康": "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "娛樂": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    }
    out = {}
    for name, url in sections.items():
        try:
            root = ET.fromstring(http_get(url))
        except Exception:  # noqa: BLE001
            continue
        items = []
        for it in root.iter("item"):
            src = it.find("source")
            items.append({"title": it.findtext("title"), "url": it.findtext("link"),
                          "source": src.text if src is not None else "", "date": it.findtext("pubDate")})
            if len(items) >= 15:
                break
        out[name] = items
    return out or None


# ---------------------------------------------------------- 10 大熱門 ----
def _yt(category=None, n=10):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    q = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": "TW", "hl": "zh-TW",
         "maxResults": n, "key": key}
    if category:
        q["videoCategoryId"] = category
    j = http_json("https://www.googleapis.com/youtube/v3/videos?" + urlencode(q))
    out = []
    for i, v in enumerate(j.get("items", [])):
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        th = sn.get("thumbnails", {})
        out.append({"rank": i + 1, "name": (sn.get("localized") or {}).get("title") or sn.get("title"),
                    "artist": sn.get("channelTitle", ""), "views": int(st.get("viewCount") or 0),
                    "img": (th.get("medium") or th.get("default") or {}).get("url", ""),
                    "url": "https://www.youtube.com/watch?v=" + v.get("id", "")})
    return out


def fetch_youtube():
    """YouTube 台灣發燒影片與熱門音樂影片（需要 YOUTUBE_API_KEY，免費額度即可）。"""
    videos = _yt()
    try:
        music = _yt("10")
    except RuntimeError:  # 少數地區不支援依類別取熱門，影片榜仍可用
        music = []
    return {"videos": videos, "music": music} if (videos or music) else None


def fetch_anime():
    """本季動畫，依 MyAnimeList 追蹤人數排序（Jikan API，免金鑰）。"""
    seen, rows = set(), []
    for page in (1, 2):
        try:
            j = http_json("https://api.jikan.moe/v4/seasons/now?sfw=true&page=%d" % page)
        except RuntimeError:
            break
        for a in j.get("data", []):
            if a.get("mal_id") in seen:
                continue
            seen.add(a.get("mal_id"))
            rows.append(a)
        if not (j.get("pagination") or {}).get("has_next_page"):
            break
    rows.sort(key=lambda a: -(a.get("members") or 0))
    out = []
    for i, a in enumerate(rows[:10]):
        jp = a.get("title_japanese") or ""
        name = a.get("title") or jp
        out.append({"rank": i + 1, "name": name, "alt": a.get("title_english") or "", "jp": jp,
                    "members": a.get("members") or 0, "score": a.get("score"), "episodes": a.get("episodes"),
                    "img": ((a.get("images") or {}).get("jpg") or {}).get("image_url", ""),
                    "url": a.get("url") or ""})
    return {"items": out} if out else None


def fetch_drama():
    """Netflix 官方每週 Top 10：台灣影集榜（免金鑰）。"""
    tsv = http_get("https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv", timeout=90)
    rows = [r for r in csv.DictReader(io.StringIO(tsv), delimiter="\t")
            if r.get("country_iso2") == "TW" and r.get("category") == "TV"]
    if not rows:
        return None
    week = max(r["week"] for r in rows)
    cur = sorted((r for r in rows if r["week"] == week), key=lambda r: int(r.get("weekly_rank") or 99))
    out = []
    for r in cur[:10]:
        title = r.get("show_title") or ""
        season = r.get("season_title") or ""
        if season in ("N/A", title):
            season = ""
        out.append({"rank": int(r["weekly_rank"]), "name": title, "season": season,
                    "weeks": int(r.get("cumulative_weeks_in_top_10") or 1), "img": "",
                    "url": "https://www.netflix.com/search?q=" + quote(title)})
    return {"week": week, "items": out}


ALL = {
    "etf": fetch_etf_premium,
    "stocks": fetch_stock_screen,
    "fx": fetch_fx,
    "music": fetch_music,
    "books": fetch_books,
    "movies": fetch_movies,
    "apps": fetch_apps_podcasts,
    "news": fetch_news,
    "youtube": fetch_youtube,
    "anime": fetch_anime,
    "drama": fetch_drama,
}
