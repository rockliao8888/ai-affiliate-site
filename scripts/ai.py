"""Claude 自動撰文。沒有 ANTHROPIC_API_KEY 或 SDK 時回傳 None，網站仍可用純資料建置。"""
import json
import os

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

SYSTEM = """你是台灣繁體中文生活理財網站「{site}」的編輯。
寫作原則：
- 一律使用台灣用語的繁體中文，語氣親切、具體、有資訊量，不灌水。
- 理財內容只能客觀描述數據與風險，不可給出「買進／賣出／目標價／保證獲利」等個別投資建議；
  需要時提醒讀者自行評估或諮詢合格顧問。
- 健康內容需保守、以公認衛教知識為主，不做診斷，必要時建議就醫。
- 只能根據提供的資料敘述數字，不可捏造數據、新聞或引言。
- 推薦商品時自然融入情境，不誇大療效或報酬，並且只使用清單中提供的商品 id。"""


def _client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # noqa: WPS433
    except ImportError:
        return None
    return anthropic.Anthropic(max_retries=3)


def ask_json(prompt, schema, site_name, max_tokens=8000, effort="medium"):
    """呼叫 Claude 並以 JSON Schema 結構化輸出。失敗回傳 None。"""
    client = _client()
    if client is None:
        return None
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=SYSTEM.format(site=site_name),
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except Exception as e:  # noqa: BLE001 - AI 失敗不能讓整站建置中斷
        print("[ai] request failed:", type(e).__name__, e)
        return None
    if resp.stop_reason in ("refusal", "max_tokens"):
        print("[ai] stop_reason =", resp.stop_reason)
        return None
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except ValueError:
        print("[ai] invalid JSON")
        return None


def _obj(props, required=None):
    return {"type": "object", "properties": props,
            "required": required or list(props), "additionalProperties": False}


STR = {"type": "string"}
STRS = {"type": "array", "items": STR}

BRIEF_SCHEMA = _obj({"headline": STR, "summary": STR, "bullets": STRS, "risk_note": STR,
                     "stock_notes": {"type": "array", "items": _obj({"code": STR, "note": STR})},
                     "etf_note": STR})

ARTICLE_SCHEMA = _obj({
    "title": STR, "slug": {"type": "string", "description": "英文小寫與連字號的網址代稱"},
    "excerpt": STR, "keywords": STRS,
    "sections": {"type": "array", "items": _obj({"heading": STR, "paragraphs": STRS, "tips": STRS})},
    "product_ids": STRS,
    "social_post": {"type": "string", "description": "120 字內社群貼文，含 1~3 個 hashtag，不含網址"},
})


def market_brief(site, stocks, etf, fx):
    data = {
        "stock_screen": (stocks or {}).get("picks", [])[:10],
        "etf_top_premium": (etf or {}).get("top_premium", [])[:8],
        "etf_top_discount": (etf or {}).get("top_discount", [])[:8],
        "fx": (fx or {}).get("rates", []),
    }
    prompt = ("以下是今日台股量化篩選、ETF 折溢價與匯率資料（JSON）。請撰寫：\n"
              "1. headline：今日市場觀察標題（20 字內）\n2. summary：150~250 字總結\n"
              "3. bullets：3~5 個重點\n4. stock_notes：針對每檔篩選股各一句 40 字內的客觀數據解讀\n"
              "5. etf_note：解釋折溢價過大的意義與買 ETF 時應注意之處（100 字內）\n"
              "6. risk_note：風險提醒一句\n\n" + json.dumps(data, ensure_ascii=False))
    return ask_json(prompt, BRIEF_SCHEMA, site)


def write_article(site, topic, context, products, recent_titles):
    plist = [{"id": p["id"], "name": p["name"], "tags": p.get("tags", [])} for p in products]
    prompt = ("請寫一篇 1200~1800 字的原創網站文章。\n主題方向：%s\n"
              "參考資料（可引用其中數據）：%s\n"
              "可推薦的聯盟商品（挑 1~3 個真正相關的放入 product_ids；不相關就給空陣列）：%s\n"
              "避免與近期文章重複：%s\n"
              "要求：4~6 個段落 sections，每段 2~4 個 paragraphs，可附 tips 實用清單；"
              "標題吸引人但不聳動；slug 用英文。"
              % (topic, json.dumps(context, ensure_ascii=False)[:6000],
                 json.dumps(plist, ensure_ascii=False), "、".join(recent_titles[:30])))
    return ask_json(prompt, ARTICLE_SCHEMA, site, max_tokens=16000)
