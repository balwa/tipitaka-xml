"""Aksharamukha-based transliteration between VRI script codes."""
from __future__ import annotations

from functools import lru_cache
from aksharamukha import transliterate

# VRI folder name -> Aksharamukha script name.
# RussianCyrillic is Aksharamukha's Pali Cyrillic mapping (matches VRI cyrl).
SCRIPTS: dict[str, str] = {
    "deva": "Devanagari",
    "romn": "IAST",
    "beng": "Bengali",
    "mymr": "Burmese",
    "sinh": "Sinhala",
    "thai": "Thai",
    "cyrl": "RussianCyrillic",
    "gujr": "Gujarati",
    "guru": "Gurmukhi",
    "khmr": "Khmer",
    "knda": "Kannada",
    "mlym": "Malayalam",
    "taml": "Tamil",
    "telu": "Telugu",
    "tibt": "Tibetan",
}

ALL_SCRIPTS = tuple(SCRIPTS.keys())

# Unicode block ranges used to guess the script of a raw query string.
# Order matters: more specific blocks first.
_RANGES: list[tuple[str, int, int]] = [
    ("deva", 0x0900, 0x097F),
    ("beng", 0x0980, 0x09FF),
    ("guru", 0x0A00, 0x0A7F),
    ("gujr", 0x0A80, 0x0AFF),
    ("taml", 0x0B80, 0x0BFF),
    ("telu", 0x0C00, 0x0C7F),
    ("knda", 0x0C80, 0x0CFF),
    ("mlym", 0x0D00, 0x0D7F),
    ("sinh", 0x0D80, 0x0DFF),
    ("thai", 0x0E00, 0x0E7F),
    ("tibt", 0x0F00, 0x0FFF),
    ("mymr", 0x1000, 0x109F),
    ("khmr", 0x1780, 0x17FF),
    ("cyrl", 0x0400, 0x04FF),
]


def detect_script(query: str) -> str:
    """Best-effort script detection by counting characters per Unicode block."""
    counts: dict[str, int] = {}
    for ch in query:
        cp = ord(ch)
        for code, lo, hi in _RANGES:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    if not counts:
        return "romn"
    return max(counts.items(), key=lambda kv: kv[1])[0]


@lru_cache(maxsize=4096)
def translit(text: str, src: str, dst: str) -> str:
    """Transliterate `text` from VRI script code `src` to `dst`. Cached."""
    if src == dst:
        return text
    return transliterate.process(SCRIPTS[src], SCRIPTS[dst], text)


def fan_out(query: str, src: str | None = None) -> dict[str, str]:
    """Return {script_code: transliterated_query} for all 15 scripts."""
    if src is None:
        src = detect_script(query)
    return {dst: translit(query, src, dst) for dst in ALL_SCRIPTS}
