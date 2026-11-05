"""Источники объявлений. Сейчас: публичные Telegram-каналы через веб-превью t.me/s/<канал>."""
import re
import html
import logging
import requests

import ad_parser as P

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
RX_PHOTO = re.compile(r"tgme_widget_message_photo_wrap[^>]*background-image:url\(&?#?[\"']?([^\"')]+)")


def _clean(raw: str) -> str:
    raw = re.sub(r"<br\s*/?>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(raw)).strip()


def fetch_channel(name: str, city_hint: str = "", pages: int = 1) -> list:
    out, before = [], None
    for _ in range(pages):
        url = f"https://t.me/s/{name}" + (f"?before={before}" if before else "")
        r = requests.get(url, headers=UA, timeout=25, allow_redirects=False)
        if r.status_code != 200:
            break
        blocks = r.text.split("tgme_widget_message_wrap")[1:]
        if not blocks:
            break
        ids = []
        for b in blocks:
            post = re.search(r'data-post="([^"]+)"', b)
            dt = re.search(r'datetime="([^"]+)"', b)
            if not post or not dt:
                continue
            ids.append(int(post.group(1).split("/")[-1]))
            t = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', b, re.S)
            text = _clean(t.group(1)) if t else ""
            if len(text) < 25:
                continue
            info = P.parse(text, city_hint)
            if not info:
                continue
            ph = RX_PHOTO.search(b)
            out.append({
                "id": post.group(1), "source": name, "text": text,
                "url": f"https://t.me/{post.group(1)}", "ts": dt.group(1),
                "photo": ph.group(1) if ph else None, **info,
            })
        if not ids:
            break
        before = min(ids)
    return out


def channel_exists(name: str) -> bool:
    try:
        r = requests.get(f"https://t.me/s/{name}", headers=UA, timeout=20, allow_redirects=False)
        return r.status_code == 200 and "tgme_widget_message_wrap" in r.text
    except requests.RequestException:
        return False
