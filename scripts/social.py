"""自動推廣：把新文章發到 Telegram 頻道 / Discord 頻道（有設定環境變數才會發）。
其他平台（Facebook 粉專、X、Threads）需各自的官方 API 與審核，可依同樣模式擴充。"""
import json
import os
import urllib.parse
import urllib.request


def _post(url, data, as_json=False):
    if as_json:
        body, ctype = json.dumps(data).encode(), "application/json"
    else:
        body, ctype = urllib.parse.urlencode(data).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def announce(text, link):
    msg = "%s\n\n👉 %s" % (text, link)
    sent = []
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            _post("https://api.telegram.org/bot%s/sendMessage" % tok, {"chat_id": chat, "text": msg})
            sent.append("telegram")
        except Exception as e:  # noqa: BLE001
            print("[social] telegram failed:", e)
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    if hook:
        try:
            _post(hook, {"content": msg}, as_json=True)
            sent.append("discord")
        except Exception as e:  # noqa: BLE001
            print("[social] discord failed:", e)
    return sent
