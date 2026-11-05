"""Загрузка объявлений, собранных вручную (Facebook/Telegram через браузер), в базу бота.
Запуск: python import_posts.py posts.json   (формат: [{"id","source","text","url","city"}])"""
import json
import re
import sys
from datetime import datetime, timezone

import database as db
import ad_parser as P

db.init_db()
now = datetime.now(timezone.utc).isoformat()
items = []
for p in json.load(open(sys.argv[1], encoding="utf-8")):
    info = P.parse(p["text"], p.get("city", "hrg"))
    if info:
        items.append({"id": p["id"], "source": re.sub(r"\(\d+\)\s*", "", p["source"]), "text": p["text"], "url": p["url"],
                      "ts": p.get("ts", now), "photo": None, **info})
print("разобрано:", len(items), "новых:", db.save_listings(items))
