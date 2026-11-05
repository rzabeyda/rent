def passes(l: dict, s: dict) -> bool:
    deal = s["deal"]
    if deal != "any" and l["deal"] not in (deal, "both"):
        return False
    if s["city"] != "all" and l["city"] != s["city"]:
        return False
    price = l["price_usd"]
    if price is not None:
        pmin, pmax = int(s["pmin"]), int(s["pmax"])
        if price < pmin or (pmax and price > pmax):
            return False
    if s["rooms"] != "any":
        r = l["rooms"]
        if r is None:
            return False
        wanted = [int(x) for x in s["rooms"].split(",") if x.isdigit()]
        if wanted and not any((r >= 3) if w >= 3 else (r == w) for w in wanted):
            return False
    return True
