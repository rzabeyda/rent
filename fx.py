"""Курсы валют (к USD), кэш на 12 часов."""
import time
import requests

FALLBACK = {"USD": 1.0, "EUR": 0.86, "GBP": 0.75, "EGP": 48.0}
_cache = {"t": 0.0, "r": dict(FALLBACK)}


def rates() -> dict:
    now = time.time()
    if now - _cache["t"] < 43200:
        return _cache["r"]
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15).json()["rates"]
        _cache["r"] = {k: float(r[k]) for k in FALLBACK}
        _cache["t"] = now
    except Exception:
        _cache["t"] = now - 43200 + 600   # повтор через 10 минут
    return _cache["r"]


def to_usd(amount: float, cur: str) -> float:
    return amount / rates()[cur]


def from_usd(usd: float, cur: str) -> float:
    return usd * rates()[cur]
