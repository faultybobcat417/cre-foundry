from __future__ import annotations

import re
import unicodedata

_SUFFIXES = {
    "inc", "incorporated", "ltd", "limited", "corp", "corporation", "co", "company"
}
_STREET = {
    "street": "st", "road": "rd", "avenue": "ave", "boulevard": "blvd",
    "drive": "dr", "court": "ct", "highway": "hwy", "lane": "ln"
}


def _ascii(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def normalize_name(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", _ascii(value).lower())
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_address(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", _ascii(value).lower())
    return " ".join(_STREET.get(token, token) for token in tokens)
