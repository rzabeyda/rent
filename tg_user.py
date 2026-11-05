"""Чтение групп и каналов, в которых состоит ваш Telegram-аккаунт (Telethon).
Включается, если в .env заданы TG_API_ID и TG_API_HASH и есть сессия data/user.session
(создаётся один раз: python login.py)."""
import os
import re
import logging
from pathlib import Path

import ad_parser as P

log = logging.getLogger(__name__)
API_ID = os.getenv("TG_API_ID", "")
API_HASH = os.getenv("TG_API_HASH", "")
SESSION = "data/user"
PHOTO_DIR = Path("data/photos")
TITLE_RX = re.compile(r"хургад|hurghad|hurgad|шарм|sharm|египет|egypt|аренд|rent|недвиж|жиль|квартир|sdam|сдам", re.I)
FIRST_LIMIT = 150      # сообщений из каждого чата при первом запуске
_client = None
_last_id: dict = {}


async def start():
    """Подключиться. Возвращает True, если источник включён."""
    global _client
    if not (API_ID and API_HASH and os.path.exists(SESSION + ".session")):
        return False
    from telethon import TelegramClient
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    _client = TelegramClient(SESSION, int(API_ID), API_HASH)
    await _client.connect()
    if not await _client.is_user_authorized():
        log.warning("Telethon: сессия не авторизована, запустите login.py")
        _client = None
        return False
    log.info("Telethon: подключён")
    return True


async def fetch() -> list:
    if not _client:
        return []
    out = []
    async for d in _client.iter_dialogs():
        if not (d.is_group or d.is_channel) or not TITLE_RX.search(d.name or ""):
            continue
        ent = d.entity
        hint = "hrg" if re.search(r"хургад|hurghad|hurgad", d.name, re.I) else \
               "ssh" if re.search(r"шарм|sharm", d.name, re.I) else ""
        key = d.id
        try:
            kw = {"min_id": _last_id[key]} if key in _last_id else {"limit": FIRST_LIMIT}
            msgs = [m async for m in _client.iter_messages(ent, **kw)]
        except Exception as e:
            log.warning("Telethon %s: %s", d.name, e)
            continue
        if msgs:
            _last_id[key] = max(m.id for m in msgs)
        for m in msgs:
            text = (m.message or "").strip()
            if len(text) < 25 or m.out:
                continue
            info = P.parse(text, hint)
            if not info:
                continue
            uname = getattr(ent, "username", None)
            url = f"https://t.me/{uname}/{m.id}" if uname else f"https://t.me/c/{abs(ent.id)}/{m.id}"
            photo = None
            if m.photo:
                try:
                    path = await m.download_media(file=str(PHOTO_DIR / f"{abs(d.id)}_{m.id}.jpg"))
                    photo = f"file:{path}" if path else None
                except Exception:
                    pass
            out.append({"id": f"tg{abs(d.id)}/{m.id}", "source": uname or d.name[:30], "text": text,
                        "url": url, "ts": m.date.isoformat(), "photo": photo, **info})
    log.info("Telethon: %d объявлений", len(out))
    return out
