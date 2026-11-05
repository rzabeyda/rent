"""Перевод текста на русский (бесплатный endpoint Google Translate), с кэшем."""
import re
import logging
import requests

log = logging.getLogger(__name__)
_cache: dict = {}


def is_russian(text: str) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё؀-ۿ]", text)
    if not letters:
        return True
    cyr = sum(1 for ch in letters if "А" <= ch <= "я" or ch in "Ёё")
    return cyr / len(letters) >= 0.5


def to_ru(text: str) -> str:
    if is_russian(text):
        return text
    if text in _cache:
        return _cache[text]
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                         params={"client": "gtx", "sl": "auto", "tl": "ru", "dt": "t", "q": text},
                         timeout=15)
        out = "".join(part[0] for part in r.json()[0] if part and part[0])
        if out:
            _cache[text] = out
            if len(_cache) > 500:
                _cache.pop(next(iter(_cache)))
            return out
    except Exception as e:
        log.warning("translate failed: %s", e)
    return text
