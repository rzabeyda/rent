import html
import re
from datetime import datetime, timezone

import fx

CITY = {"hrg": "Хургада", "ssh": "Шарм-эль-Шейх", "all": "Все города", "": "Египет"}
DEAL = {"rent": "Аренда", "sale": "Покупка", "any": "Аренда и покупка", "both": "Аренда/продажа", "": "Объявление"}
SYM = {"USD": "$", "EUR": "€", "GBP": "£", "EGP": "EGP"}
PERIOD = {"day": "/сутки", "month": "/мес"}

PRICE_PRESETS = {
    "rent": [("$0–150", 0, 150), ("$150–300", 150, 300), ("$300–500", 300, 500), ("$500+", 500, 0), ("Любая", 0, 0)],
    "sale": [("до $30k", 0, 30000), ("$30–60k", 30000, 60000), ("$60–100k", 60000, 100000), ("$100k+", 100000, 0), ("Любая", 0, 0)],
}


def money(v: float, cur: str) -> str:
    n = f"{v:,.0f}".replace(",", " ")
    return f"{SYM[cur]}{n}" if cur != "EGP" else f"{n} EGP"


def ago(ts: str) -> str:
    try:
        d = datetime.fromisoformat(ts)
    except ValueError:
        return ""
    sec = (datetime.now(timezone.utc) - d).total_seconds()
    if sec < 3600:
        return f"{max(1, int(sec // 60))} мин назад"
    if sec < 86400:
        return f"{int(sec // 3600)} ч назад"
    return f"{int(sec // 86400)} дн назад"


def price_line(l: dict) -> str:
    if l["price_usd"] is None:
        return "💰 цена не указана"
    orig = money(l["price_orig"], l["cur"]) + PERIOD.get(l["period"] or "", "")
    unit = "/мес" if l["deal"] == "rent" or (l["period"] and l["deal"] != "sale") else ""
    usd = money(l["price_usd"], "USD") + unit
    gbp = money(fx.from_usd(l["price_usd"], "GBP"), "GBP") + unit
    egp = money(fx.from_usd(l["price_usd"], "EGP"), "EGP") + unit
    parts = [orig]
    for p in (usd, gbp, egp):
        if p.split("/")[0] != orig.split("/")[0] and p not in parts:
            parts.append(p)
    return "💰 " + " · ".join(parts)


def fmt_listing(l: dict) -> str:
    head = f"🏠 <b>{DEAL.get(l['deal'], 'Объявление')}</b> · {CITY.get(l['city'], 'Египет')}"
    if l["rooms"] is not None:
        head += " · " + ("студия" if l["rooms"] == 0 else f"🛏 {l['rooms']}")
    if l.get("area"):
        head += f" · 📐 {l['area']} м²"
    body = re.sub(r"\n{2,}", "\n", l["text"]).strip()
    if len(body) > 420:
        body = body[:420].rsplit(" ", 1)[0] + "…"
    return (f"{head}\n{price_line(l)}\n🕒 {ago(l['ts'])} · @{l['source']}\n\n"
            f"{html.escape(body)}\n\n<a href=\"{l['url']}\">Открыть объявление</a>")


def fmt_settings(s: dict) -> str:
    rooms = {"any": "любое", "0": "студия", "1": "1", "2": "2", "3": "3+"}[s["rooms"]]
    pmin, pmax = int(s["pmin"]), int(s["pmax"])
    price = "любая" if not pmin and not pmax else (f"от ${pmin:,}".replace(",", " ") if not pmax else
            f"${pmin:,} – ${pmax:,}".replace(",", " ") if pmin else f"до ${pmax:,}".replace(",", " "))
    iv = int(s["interval"])
    interval = f"{iv // 60} ч" if iv >= 60 else f"{iv} мин"
    return (
        "⚙️ <b>Настройки фильтров</b>\n\n"
        f"⏱ Интервал: <b>{interval}</b>\n"
        f"🕒 Давность: <b>{s['age']} дн.</b>\n"
        f"💰 Цена: <b>{price}</b>\n"
        f"🛏 Комнат: <b>{rooms}</b>\n"
        f"📍 Город: <b>{CITY[s['city']]}</b>\n"
        f"🏷 Тип: <b>{DEAL[s['deal']]}</b>"
    )
