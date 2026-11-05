from formatter import PRICE_PRESETS
from ad_parser import is_wanted


def passes(l: dict, s: dict) -> bool:
    if is_wanted(l["text"]):
        return False
    deal = s["deal"]
    if deal != "any" and l["deal"] not in (deal, "both"):
        return False
    if s["city"] != "all" and l["city"] != s["city"]:
        return False
    price = l["price_usd"]
    if price is None:
        return False                      # без цены не присылаем
    if s["prices"] != "any":
        presets = PRICE_PRESETS.get(deal, [])
        ranges = [presets[int(i)][1:] for i in s["prices"].split(",") if i.isdigit() and int(i) < len(presets)]
        if ranges and not any(price >= a and (not z or price <= z) for a, z in ranges):
            return False
    if s["rooms"] != "any":
        r = l["rooms"]
        if r is None:
            return False
        wanted = [int(x) for x in s["rooms"].split(",") if x.isdigit()]
        if wanted and not any((r >= 3) if w >= 3 else (r == w) for w in wanted):
            return False
    return True
