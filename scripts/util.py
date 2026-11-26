"""共用工具：HTTP 抓取、JSON 存取、時間（純標準函式庫，相容 Python 3.6+）。"""
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
PUBLIC_DIR = os.path.join(ROOT, "public")
CONFIG_DIR = os.path.join(ROOT, "config")

TW = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (compatible; DailyRankBot/1.0)"


def now_tw():
    return datetime.now(TW)


def http_get(url, timeout=25, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 - 網路錯誤一律重試
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("GET %s failed: %s" % (url, last))


def http_json(url, **kw):
    return json.loads(http_get(url, **kw))


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def to_float(v, default=None):
    try:
        if v is None:
            return default
        s = str(v).replace(",", "").strip()
        if s in ("", "-", "--", "N/A"):
            return default
        return float(s)
    except ValueError:
        return default


def config(name):
    return load_json(os.path.join(CONFIG_DIR, name), {})
