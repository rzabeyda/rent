"""Разбор текста объявления: тип сделки, город, цена, комнаты."""
import re
import hashlib
import fx

NUM = r"\d{1,3}(?:[  ,.]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
MULT = r"(?:млн|миллион\w*|million|mln|тыс\w*|тысяч\w*|k\b|thousand)"
CUR = (r"(?:\$|usd|долл\w*|бакс\w*|€|eur\w*|евро|£|gbp|egp|гнф|le\b|"
       r"(?:египетск\w*\s*)?фунт\w*|egyptian\s*pound\w*)")
RX_BEFORE = re.compile(rf"(?P<cur>{CUR})\s*(?P<num>{NUM})\s*(?P<mult>{MULT})?", re.I)
RX_AFTER = re.compile(rf"(?P<num>{NUM})\s*(?P<mult>{MULT})?\s*(?P<cur>{CUR})", re.I)

RX_RENT = re.compile(r"аренд|сда[ёе]тся|сдам|сдаю|сдан[аы]|снять|\brent|посуточн|в сутки|/\s*сут|per night|per month|в месяц|/\s*мес|long.?term", re.I)
RX_SALE = re.compile(r"продаж|продам|продаю|продаётся|продается|купить|покупк|for sale|\bsale\b|\bbuy\b|инвестиц", re.I)
RX_DAY = re.compile(r"сутк|посуточ|day|night|ноч|сут\b", re.I)
RX_MONTH = re.compile(r"мес|month|/\s*m\b", re.I)
RX_KEY = re.compile(r"💰|цен|стоим|price|аренд|rent|продаж|сутк|мес", re.I)

CITY_HRG = re.compile(r"хургад|hurghad|hurgad|сахл[ -]?хашиш|sahl|макади|makadi|эль[ -]?гуна|gouna|сехаль|сэхаль|sekalla|файруз|fayrouz|аль[ -]?ахия|el[ -]?ahyaa|интерконтиненталь|intercontinental|кавсер|kawther|эль[ -]?дахар|dahar", re.I)
CITY_SSH = re.compile(r"шарм|sharm|наама|naama|набк|nabq|рас ум сид|ras um sid|shark.?s bay", re.I)


def _cur(s: str) -> str:
    s = s.lower()
    if s == "$" or s.startswith(("usd", "долл", "бакс")):
        return "USD"
    if s == "€" or s.startswith(("eur", "евро")):
        return "EUR"
    if s == "£" or s.startswith("gbp"):
        return "GBP"
    return "EGP"


def _num(num: str, mult):
    n = num.replace(" ", " ").strip()
    try:
        if mult:
            v = float(n.replace(" ", "").replace(",", "."))
            m = mult.lower()
            return v * (1_000_000 if m.startswith(("млн", "милл", "mill", "mln")) else 1000)
        if re.fullmatch(r"\d{1,3}(?:[ ,.]\d{3})+", n):
            return float(re.sub(r"[ ,.]", "", n))
        return float(n.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def find_price(text: str, deal: str):
    """-> (amount, cur, period, price_usd) или None. price_usd: аренда — в месяц, продажа — полная."""
    cands = []
    for rx in (RX_BEFORE, RX_AFTER):
        for m in rx.finditer(text):
            v = _num(m.group("num"), m.group("mult"))
            if not v:
                continue
            cur = _cur(m.group("cur"))
            usd = fx.to_usd(v, cur)
            if usd < 5 or usd > 20_000_000:
                continue
            ctx = text[max(0, m.start() - 40):m.start()]
            tail = text[m.end():m.end() + 25]
            cands.append((m.start(), v, cur, usd, bool(RX_KEY.search(ctx)), tail))
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    pick = next((c for c in cands if c[4]), cands[0])
    _, v, cur, usd, _, tail = pick
    period = None
    if RX_DAY.search(tail):
        period = "day"
    elif RX_MONTH.search(tail):
        period = "month"
    elif deal == "rent" and usd <= 60:
        period = "day"
    elif deal == "rent":
        period = "month"
    usd_norm = usd * 30 if period == "day" else usd
    return v, cur, period, usd_norm


def find_rooms(text: str):
    t = text.lower()
    if re.search(r"студи|studio", t):
        return 0
    m = re.search(r"(\d)\s*\+\s*\d", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d)\s*[- ]?(?:спал|bed|br\b|bdr|комнат)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:спал\w*|bed\w*|комнат\w*)\s*[:\-]?\s*(\d)", t)
    if m:
        return int(m.group(1))
    return None


RX_AREA = re.compile(r"(\d{2,4}(?:[.,]\d+)?)\s*(?:м²|м2|кв\.?\s*м|m²|m2|sqm|sq\.?\s*m)", re.I)
RX_AREA2 = re.compile(r"(?:площадь|area|size)\s*[:\-—]?\s*(\d{2,4}(?:[.,]\d+)?)", re.I)


def find_area(text: str):
    m = RX_AREA.search(text) or RX_AREA2.search(text)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return round(v) if 10 <= v <= 2000 else None


RX_HOUSING = re.compile(r"квартир|студи|апартамент|вилл|дом|жиль|комнат|спальн|таунхаус|пентхаус|дуплекс|комплекс|недвижим|"
                        r"apartment|flat|villa|studio|bedroom|bed|room|townhouse|penthouse|duplex|compound|property|real estate", re.I)


def parse(text: str, city_hint: str = ""):
    if not RX_HOUSING.search(text):
        return None   # не жильё (барахолка, реклама)
    rent = bool(RX_RENT.search(text))
    sale = bool(RX_SALE.search(text))
    deal = "both" if rent and sale else "rent" if rent else "sale" if sale else ""
    price = find_price(text, "rent" if rent and not sale else deal)
    if not deal and price:
        deal = "rent" if price[2] in ("day", "month") else ("sale" if price[3] > 20000 else "")
    if not deal and not price:
        return None   # шум: реклама, новости
    if price and deal in ("rent", "both") and price[3] > 8000:
        deal = "sale"   # аренда дороже $8000/мес нереальна — это цена продажи
        price = (price[0], price[1], None, price[3])
    hrg, ssh = bool(CITY_HRG.search(text)), bool(CITY_SSH.search(text))
    city = "hrg" if hrg and not ssh else "ssh" if ssh and not hrg else city_hint
    return {
        "deal": deal,
        "city": city,
        "price_orig": price[0] if price else None,
        "cur": price[1] if price else None,
        "period": price[2] if price else None,
        "price_usd": price[3] if price else None,
        "rooms": find_rooms(text),
        "area": find_area(text),
        "hash": hashlib.md5(re.sub(r"\W+", "", text.lower())[:300].encode()).hexdigest(),
    }
