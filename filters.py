def passes(l: dict, s: dict) -> bool:
    deal = s["deal"]
    if deal != "any" and l["deal"] not in (deal, "both"):
        return False
    if s["city"] != "all" and l["city"] != s["city"]:
        return False
    price = l["price_usd"]
    if price is None:
        if s["noprice"] != "1":
            return False
    else:
        pmin, pmax = int(s["pmin"]), int(s["pmax"])
        if price < pmin or (pmax and price > pmax):
            return False
    amin, amax = int(s["amin"]), int(s["amax"])
    if amin or amax:
        a = l["area"]
        if a is None or a < amin or (amax and a > amax):
            return False
    if s["rooms"] != "any":
        r = l["rooms"]
        if r is None:
            return False
        want = int(s["rooms"])
        if (want >= 3 and r < 3) or (want < 3 and r != want):
            return False
    return True
