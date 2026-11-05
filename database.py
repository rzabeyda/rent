import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

import config

_lock = threading.RLock()
_conn = None

DEFAULTS = {
    "deal": "rent",       # rent / sale / any
    "city": "all",        # hrg / ssh / all
    "prices": "any",      # выбранные диапазоны цены (индексы пресетов), any = любая
    "rooms": "any",       # 0 (студия) / 1 / 2 / 3 (3+) / any
    "age": "7",           # дней
    "interval": "360",    # минут между уведомлениями
    "noprice": "1",       # показывать объявления без цены
    "amin": "0",          # площадь, м², 0 = без ограничения
    "amax": "0",
}


def init_db():
    global _conn
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    with _lock:
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(chat_id INTEGER PRIMARY KEY, username TEXT, active INTEGER DEFAULT 1, last_notified REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(chat_id INTEGER, key TEXT, value TEXT, PRIMARY KEY(chat_id, key));
        CREATE TABLE IF NOT EXISTS channels(name TEXT PRIMARY KEY, city TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS listings(
            id TEXT PRIMARY KEY, source TEXT, text TEXT, url TEXT, ts TEXT, photo TEXT,
            deal TEXT, city TEXT, price_orig REAL, cur TEXT, period TEXT, price_usd REAL,
            rooms INTEGER, hash TEXT, added REAL);
        CREATE INDEX IF NOT EXISTS idx_listings_ts ON listings(ts);
        CREATE TABLE IF NOT EXISTS sent(chat_id INTEGER, id TEXT, hash TEXT, PRIMARY KEY(chat_id, id));
        CREATE INDEX IF NOT EXISTS idx_sent_hash ON sent(chat_id, hash);
        """)
        cols = [r["name"] for r in _conn.execute("PRAGMA table_info(listings)")]
        if "area" not in cols:
            _conn.execute("ALTER TABLE listings ADD COLUMN area INTEGER")
        _conn.executemany("INSERT OR IGNORE INTO channels(name, city) VALUES(?,?)", config.DEFAULT_CHANNELS)
        _conn.commit()


# ── пользователи ──────────────────────────────────────────────
def add_user(chat_id, username=""):
    with _lock:
        _conn.execute("INSERT INTO users(chat_id, username, active) VALUES(?,?,1) "
                      "ON CONFLICT(chat_id) DO UPDATE SET active=1, username=excluded.username", (chat_id, username))
        _conn.commit()


def set_active(chat_id, active: bool):
    with _lock:
        _conn.execute("UPDATE users SET active=? WHERE chat_id=?", (int(active), chat_id))
        _conn.commit()


def active_users():
    with _lock:
        return [r["chat_id"] for r in _conn.execute("SELECT chat_id FROM users WHERE active=1")]


def get_last_notified(chat_id) -> float:
    with _lock:
        r = _conn.execute("SELECT last_notified FROM users WHERE chat_id=?", (chat_id,)).fetchone()
        return r["last_notified"] if r else 0


def set_last_notified(chat_id, t=None):
    with _lock:
        _conn.execute("UPDATE users SET last_notified=? WHERE chat_id=?", (t or time.time(), chat_id))
        _conn.commit()


# ── настройки ─────────────────────────────────────────────────
def get_settings(chat_id) -> dict:
    s = dict(DEFAULTS)
    with _lock:
        for r in _conn.execute("SELECT key, value FROM settings WHERE chat_id=?", (chat_id,)):
            s[r["key"]] = r["value"]
    return s


def set_setting(chat_id, key, value):
    with _lock:
        _conn.execute("INSERT INTO settings(chat_id,key,value) VALUES(?,?,?) "
                      "ON CONFLICT(chat_id,key) DO UPDATE SET value=excluded.value", (chat_id, key, str(value)))
        _conn.commit()


# ── каналы ────────────────────────────────────────────────────
def get_channels():
    with _lock:
        return [(r["name"], r["city"]) for r in _conn.execute("SELECT name, city FROM channels ORDER BY name")]


def add_channel(name, city=""):
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO channels(name, city) VALUES(?,?)", (name, city))
        _conn.commit()


def del_channel(name) -> bool:
    with _lock:
        n = _conn.execute("DELETE FROM channels WHERE name=?", (name,)).rowcount
        _conn.commit()
        return n > 0


# ── объявления ────────────────────────────────────────────────
def listings_count() -> int:
    with _lock:
        return _conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]


def save_listings(items) -> int:
    new = 0
    with _lock:
        for l in items:
            cur = _conn.execute(
                "INSERT OR IGNORE INTO listings(id,source,text,url,ts,photo,deal,city,price_orig,cur,period,price_usd,rooms,area,hash,added)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (l["id"], l["source"], l["text"], l["url"], l["ts"], l["photo"], l["deal"], l["city"],
                 l["price_orig"], l["cur"], l["period"], l["price_usd"], l["rooms"], l["area"], l["hash"],
                 time.time()))
            new += cur.rowcount
        _conn.commit()
    return new


def recent_listings(max_age_days: int):
    since = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    with _lock:
        return [dict(r) for r in _conn.execute("SELECT * FROM listings WHERE ts>=? ORDER BY ts DESC", (since,))]


def sent_keys(chat_id):
    with _lock:
        rows = _conn.execute("SELECT id, hash FROM sent WHERE chat_id=?", (chat_id,)).fetchall()
    return {r["id"] for r in rows}, {r["hash"] for r in rows}


def sent_texts(chat_id):
    with _lock:
        return [r["text"] for r in _conn.execute(
            "SELECT l.text FROM sent s JOIN listings l ON l.id = s.id WHERE s.chat_id=?", (chat_id,))]


def mark_sent(chat_id, l):
    with _lock:
        _conn.execute("INSERT OR IGNORE INTO sent(chat_id,id,hash) VALUES(?,?,?)", (chat_id, l["id"], l["hash"]))
        _conn.commit()


def cleanup(days: int):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _lock:
        _conn.execute("DELETE FROM listings WHERE ts<?", (cutoff,))
        _conn.execute("DELETE FROM sent WHERE id NOT IN (SELECT id FROM listings)")
        _conn.commit()
