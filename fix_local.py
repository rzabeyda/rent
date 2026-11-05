
import database as db, ad_parser as P
from datetime import datetime, timezone
db.init_db()
rows = db._conn.execute("SELECT id, text, ts FROM listings WHERE source LIKE 'fb:%' OR source LIKE 'vk:%'").fetchall()
fixed = dropped = 0
for r in rows:
    d = P.post_date(r["text"])
    if d:
        if (datetime.now(timezone.utc) - d).days > 120:
            db._conn.execute("DELETE FROM listings WHERE id=?", (r["id"],)); dropped += 1
        else:
            db._conn.execute("UPDATE listings SET ts=? WHERE id=?", (d.isoformat(), r["id"])); fixed += 1
db._conn.execute("DELETE FROM listings WHERE price_usd IS NOT NULL AND price_usd < 20")
db._conn.commit()
print("redated", fixed, "dropped old", dropped)
