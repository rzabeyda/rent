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
        want = int(s["rooms"])
        if (want >= 3 and r < 3) or (want < 3 and r != want):
            return False
    return True
