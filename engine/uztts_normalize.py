#!/usr/bin/env python3
"""
Uzbek (Latin) text normalization for Navoiy TTS (Apache-2.0, adapted from `aisha-org/navoiy-tts`
with @diyor.ctr social/tech abbreviations: `%` -> `foiz`, `$0` -> `nol dollar`, `24/7`, `@diyor.ctr`).
Uses only the Python standard library (0 MB extra RAM).
"""
from __future__ import annotations

import re
import unicodedata

APOSTROPHE = "'"  # U+0027 canonical for Navoiy byte-BPE
_APOS_VARIANTS = dict.fromkeys(
    [0x02BB, 0x2018, 0x2019, 0x02BC, 0x0060, 0x2032, 0x00B4, 0x2035, 0x055A, 0xFF07], APOSTROPHE
)

_CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": APOSTROPHE, "ь": "",
    "ы": "i", "э": "e", "ю": "yu", "я": "ya", "ў": "o" + APOSTROPHE, "қ": "q", "ғ": "g" + APOSTROPHE, "ҳ": "h",
}

_ONES = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
_TENS = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
_SCALE = [(10**9, "milliard"), (10**6, "million"), (10**3, "ming"), (100, "yuz")]

_ABBR = {
    "km": "kilometr", "kg": "kilogramm", "sm": "santimetr", "mm": "millimetr", "litr": "litr",
    "mln": "million", "mlrd": "milliard", "soat": "soat", "kun": "kun", "yil": "yil", "dona": "dona",
}
_MONTHS = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust",
           "sentabr", "oktabr", "noyabr", "dekabr"]

_ORD_SUFFIX = re.compile(r"\b(\d+)[-‐-―]?(?:inchi|nchi|chi)\b", re.IGNORECASE)
_ORDINAL_LAST = {
    "bir": "birinchi", "ikki": "ikkinchi", "uch": "uchinchi", "to'rt": "to'rtinchi",
    "besh": "beshinchi", "olti": "oltinchi", "yetti": "yettinchi", "sakkiz": "sakkizinchi",
    "to'qqiz": "to'qqizinchi", "o'n": "o'ninchi", "yigirma": "yigirmanchi", "o'ttiz": "o'ttizinchi",
    "qirq": "qirqinchi", "ellik": "ellikinchi", "oltmish": "oltmishinchi", "yetmish": "yetmishinchi",
    "sakson": "saksoninchi", "to'qson": "to'qsoninchi", "yuz": "yuzinchi", "ming": "minginchi",
    "million": "millioninchi", "milliard": "milliardinchi", "nol": "nolinchi",
}

_PRON_FIX = {
    "dokumentatsiya": "dokumyentatsiya",
    r"@diyor\.ctr": "diyor nuqta si ti ar",
    r"\b24/7\b": "yigirma to'rt soat",
    r"\bClaude\b": "Klod",
    r"\bOpenAI\b": "Open Ey Ay",
    r"\bChatGPT\b": "Chat Ji Pi Ti",
    r"\bGPT\b": "Ji Pi Ti",
    r"\bDeepSeek\b": "Dip Sik",
    r"\bV(\d+)\b": r"versiya \1",
    r"\bGemini\b": "Jemini",
    r"\bGitHub\b": "Git Xab",
    r"\bPython\b": "Payton",
    r"\bFollow[\-\s]Gate\b": "Follov Geyt",
    r"\bVibe\s+Coding\b": "Vayb Koding",
    r"\bAI\b": "sun'iy intellekt",
    r"\bDirect\b": "dayrekt",
    r"\bReels\b": "rils",
    r"\bSKILL\b": "skill",
}


def _int_to_words(n: int) -> str:
    if n == 0:
        return "nol"
    if n < 0:
        return "minus " + _int_to_words(-n)
    parts = []
    for value, name in _SCALE:
        if n >= value:
            count, n = n // value, n % value
            if value == 100:
                parts.append(_int_to_words(count) + " yuz")
            else:
                lead = _int_to_words(count)
                parts.append((lead + " " if not (value == 1000 and count == 1) else "") + name)
    if n >= 20:
        parts.append(_TENS[n // 10])
        n %= 10
    elif n >= 10:
        parts.append(_TENS[1])
        n -= 10
    if 0 < n < 10:
        parts.append(_ONES[n])
    return " ".join(p for p in parts if p).strip()


def _ordinal_words(n: int) -> str:
    w = _int_to_words(n).split()
    if not w:
        return "nolinchi"
    w[-1] = _ORDINAL_LAST.get(w[-1], w[-1] + "inchi")
    return " ".join(w)


def number_to_words(num_str: str) -> str:
    num_str = num_str.replace(" ", "").replace("\u00a0", "")
    sign = ""
    if num_str.startswith("-"):
        sign, num_str = "minus ", num_str[1:]
    if re.fullmatch(r"\d+[.,]\d+", num_str):
        intp, frac = re.split(r"[.,]", num_str, 1)
        return sign + _int_to_words(int(intp)) + " butun " + " ".join(_int_to_words(int(d)) for d in frac)
    if num_str.isdigit():
        return sign + _int_to_words(int(num_str))
    return sign + num_str


def normalize_uzbek_for_tts(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_APOS_VARIANTS)
    out = []
    for ch in text:
        rep = _CYR2LAT.get(ch.lower())
        if rep is not None:
            out.append(rep.upper() if ch.isupper() and rep else rep)
        else:
            out.append(ch)
    text = "".join(out)

    # Expand % and $ cleanly before general number expansion
    text = re.sub(r"\$(\d+)", lambda m: f"{number_to_words(m.group(1))} dollar", text)
    text = re.sub(r"(\d+)\s*%", lambda m: f"{number_to_words(m.group(1))} foiz", text)
    text = re.sub(r"(\d+)x\b", lambda m: f"{number_to_words(m.group(1))} barobar", text, flags=re.IGNORECASE)

    for pat, repl in _PRON_FIX.items():
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # Dates & times
    def _d_repl(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        mo_name = _MONTHS[mo] if 1 <= mo <= 12 else number_to_words(str(mo))
        return f"{number_to_words(str(d))} {mo_name} {number_to_words(str(y))}"

    text = re.sub(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b", _d_repl, text)
    text = re.sub(
        r"\b(\d{1,2}):(\d{2})\b",
        lambda m: number_to_words(m.group(1)) if int(m.group(2)) == 0 else f"{number_to_words(m.group(1))} {number_to_words(m.group(2))}",
        text,
    )
    text = _ORD_SUFFIX.sub(lambda m: _ordinal_words(int(m.group(1))), text)

    keys = sorted((re.escape(k) for k in _ABBR if k.isalnum()), key=len, reverse=True)
    if keys:
        text = re.sub(r"\b(" + "|".join(keys) + r")\b", lambda m: _ABBR.get(m.group(0), m.group(0)), text)

    text = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", text)
    text = re.sub(r"\b(\d+)-(?=[A-Za-z'])", lambda m: _ordinal_words(int(m.group(1))) + " ", text)
    text = re.sub(r"\d+[.,]\d+|\d+", lambda m: number_to_words(m.group(0)), text)
    text = "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t")
    return re.sub(r"[ \t]+", " ", text).strip()
