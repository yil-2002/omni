#!/usr/bin/env python3
"""
Uzbek + Bilingual English Studio Phonetic & Code-Switching Engine (`uztts_normalize.py`)
=========================================================================================
1. `segment_uzbek_english_bilingual(text)`:
   - Splits mixed Uzbek + English scripts into `[('uz' | 'en', span_text), ...]` so
     `uzbek_bilingual_hd` speaks Uzbek clauses in pure `uz-UZ-SardorNeural` (`115.9 Hz`)
     and standalone English brands/terms (`Bloomberg`, `The Information`, `Apple`,
     `iPhone 17 Pro Max`, `Tesla Optimus`, `Boston Dynamics`, `OpenAI ChatGPT`, `Claude`, etc.)
     in its acoustic twin voice `en-US-ChristopherNeural` (`+2Hz` = `115.5 Hz`).
   - Bound-suffixed English tokens (`Apple'ning`, `iPhone'da`, `Claude'ni`) are phonetically
     adapted via our persistent `126,052`-word CMU Pronouncing Dictionary (`manba/cmudict_en_134k.json.gz`)
     so Uzbek inflection flows naturally in a single breath without mid-word voice cuts.
2. `normalize_uzbek_for_tts(text)`:
   - Full Uzbek + `126,052`-word CMUdict ARPAbet-to-Uzbek phonetic normalizer + complete
     English grapheme fallback (`c`, `w`, `th`, `ph`, `tion`, `oo`, `ee`, `ea`) for 100% offline
     `Silero 48 kHz b_uzb` synthesis.
"""
from __future__ import annotations

import gzip
import json
import re
import unicodedata
from pathlib import Path

APOSTROPHE = "'"  # U+0027 canonical internal form
_APOS_VARIANTS = dict.fromkeys(
    [0x02BB, 0x2018, 0x2019, 0x02BC, 0x0060, 0x2032, 0x00B4, 0x2035, 0x055A, 0xFF07], APOSTROPHE
)

_CMUDICT_GZ = Path(__file__).resolve().parent.parent / "manba" / "cmudict_en_134k.json.gz"
_CMU_CACHE: dict[str, str] | None = None

_CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": APOSTROPHE, "ь": "",
    "ы": "i", "э": "e", "ю": "yu", "я": "ya", "ў": "o" + APOSTROPHE, "қ": "q", "ғ": "g" + APOSTROPHE, "ҳ": "h",
}

_ONES = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
_TENS = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
_SCALE = [(10**12, "trillion"), (10**9, "milliard"), (10**6, "million"), (10**3, "ming"), (100, "yuz")]

_ABBR = {
    "km": "kilometr", "kg": "kilogramm", "sm": "santimetr", "mm": "millimetr", "nm": "nanometr",
    "gb": "gigabayt", "tb": "terabayt", "mb": "megabayt", "ghz": "gigagers", "hz": "gers",
    "litr": "litr", "mln": "million", "mlrd": "milliard", "trln": "trillion",
    "soat": "soat", "kun": "kun", "yil": "yil", "dona": "dona", "sek": "soniya",
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
    "million": "millioninchi", "milliard": "milliardinchi", "trillion": "trillioninchi", "nol": "nolinchi",
}

# Assimilated loanwords & common Uzbek vocabulary that MUST stay in Uzbek prosody (never spoken with an American accent!)
_UZBEK_NATIVE_AND_ASSIMILATED = {
    "va", "ham", "hamda", "yoki", "bilan", "uchun", "yangi", "endi", "bu", "shu", "har", "kuni", "eng",
    "muhim", "katta", "kichik", "tez", "kop", "ko'p", "kam", "bor", "yoq", "yo'q", "qanday", "nega",
    "nima", "kim", "qachon", "lekin", "ammo", "sababli", "orqali", "ichida", "ustida", "ostida",
    "oldinda", "keyin", "avval", "ilk", "manba", "manbasiga", "xabar", "xabariga", "kora", "ko'ra",
    "fikricha", "boyicha", "bo'yicha", "qarshi", "ortasida", "o'rtasida", "shunga", "qaramay", "hozir",
    "hozirda", "bugun", "ertaga", "kecha", "doim", "faqat", "barcha", "hamma", "bitta", "ikkita",
    "salom", "dostlar", "do'stlar", "obuna", "boling", "bo'ling", "bolib", "bo'lib", "qoysangiz",
    "qo'ysangiz", "yangilik", "yangiliklar", "yangiliklarni", "joylab", "boramiz", "tahlil", "foydali",
    "jiddiy", "muammo", "muammoga", "uchradi", "sinov", "sinovdan", "otkazmoqda", "o'tkazmoqda",
    "tayyorlamoqda", "ishlamoqda", "yaratishda", "yaratdi", "chiqardi", "chiqarish", "korsatdi",
    "ko'rsatdi", "ochdi", "yopdi", "boshladi", "qoshdi", "qo'shdi", "ozgartirdi", "o'zgartirdi",
    # Assimilated tech/international Uzbek words spoken natively in Uzbek:
    "robot", "roboti", "robotini", "robotlar", "robotlari", "robototexnika", "texnologiya",
    "texnologiyalar", "telefon", "telefoni", "telefonlar", "smartfon", "kompyuter", "internet",
    "tizim", "tizimi", "tizimini", "tizimlar", "tizimlarini", "kompaniya", "kompaniyasi",
    "kompaniyalari", "korporatsiya", "loyiha", "loyihasi", "dizayn", "dizayni", "model", "modeli",
    "versiya", "versiyasi", "million", "milliard", "trillion", "dollar", "foiz", "video", "videolar",
    "videolarni", "audio", "kanal", "kanali", "platforma", "platformasi", "server", "kod", "dastur",
    "dasturchi", "muhandis", "muhandislari", "ekspert", "agent", "avtomat", "avtomatik", "biznes",
    "marketing", "strategiya", "bozor", "bozori", "bozorida", "raqobat", "poyga", "poygasida",
    "energiya", "zavod", "zavodi", "ekran", "kamera", "batareya", "sensor", "protsessor", "grafik",
    "chip", "chiplari", "sun'iy", "intellekt", "telegram", "instagram", "trend", "post", "fayl",
    "sayt", "kurs", "dars", "qadam", "natija", "foyda", "daromad", "sotuv", "mijoz", "mijozlar",
    "izoh", "izohda", "komment", "kommentda", "yozing", "yuboraman", "bepul", "ochiq", "maxsus",
    "rasmiy", "global", "jahon", "dunyo", "olamida", "stol", "usti", "uy", "shaxsiy", "markaz",
}

_ARP2UZ = {
    "AA": "o", "AE": "e", "AH": "a", "AO": "o", "AW": "av", "AY": "ay",
    "B": "b", "CH": "ch", "D": "d", "DH": "z", "EH": "e", "ER": "er",
    "EY": "ey", "F": "f", "G": "g", "HH": "h", "IH": "i", "IY": "i",
    "JH": "j", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ng",
    "OW": "o", "OY": "oy", "P": "p", "R": "r", "S": "s", "SH": "sh",
    "T": "t", "TH": "s", "UH": "u", "UW": "u", "V": "v", "W": "v",
    "Y": "y", "Z": "z", "ZH": "j",
}

# Explicit high-priority English multi-word & brand spans spoken in crisp Native English (`en-US-ChristopherNeural`)
_EXPLICIT_EN_PHRASES_RE = re.compile(
    r"\b(?:"
    r"Wall\s+Street\s+Journal|The\s+Information|The\s+Verge|Financial\s+Times|New\s+York\s+Times|"
    r"Bloomberg|Reuters|TechCrunch|Forbes|Business\s+Insider|CNBC|BBC|"
    r"Apple\s+Intelligence|Vision\s+Pro|MacBook\s+(?:Air|Pro)|Mac\s+Studio|Mac\s+Mini|AirPods(?:\s+Pro)?|"
    r"Apple\s+Watch|iPhone(?:\s+\d+)?(?:\s+Pro)?(?:\s+Max)?(?:\s+Air|\s+Plus|\s+Mini)?|iPad(?:\s+Pro|\s+Air)?|Apple|Siri|WWDC|"
    r"OpenAI|ChatGPT|GPT[\-\s]?\d+(?:\.\d+)?(?:\s*o|\s+mini|\s+Pro)?|Sora|"
    r"Anthropic|Claude(?:\s+(?:Opus|Sonnet|Haiku))?(?:\s+\d+(?:\.\d+)?)?|"
    r"Google\s+DeepMind|Google\s+Gemini|Google|Gemini|NotebookLM|YouTube|Waymo|"
    r"DeepSeek(?:\s+R\d+|\s+V\d+)?|Perplexity|Midjourney|Cursor|Windsurf|Lovable|v0|"
    r"Tesla\s+Optimus|Cybertruck|Robotaxi|Boston\s+Dynamics|Figure\s+AI|Unitree|SpaceX|Starlink|Neuralink|xAI|Grok|"
    r"Nvidia\s+Blackwell|Nvidia\s+Rubin|Nvidia|Blackwell|TSMC|AMD|Intel|Qualcomm|Snapdragon|"
    r"Microsoft\s+Copilot|Microsoft|Windows|Copilot|GitHub(?:\s+Actions|\s+Copilot)?|VS\s+Code|"
    r"Cloudflare(?:\s+Workers|\s+Pages)?|PostgreSQL|Supabase|Firebase|Docker|Kubernetes|Linux|"
    r"Python|JavaScript|TypeScript|React|Next\.js|Node\.js|Playwright|Tailwind|"
    r"Meta\s+AI|Llama(?:\s+\d+)?|WhatsApp|TikTok|LinkedIn|Netflix|Amazon\s+AWS|Amazon|Spotify|"
    r"Sam\s+Altman|Elon\s+Musk|Jensen\s+Huang|Tim\s+Cook|Mark\s+Zuckerberg|Sundar\s+Pichai|Dario\s+Amodei|"
    r"Vibe\s+Coding|Follow[\-\s]Gate|Smart[\-\s]Gate|Direct|Reels|Stories|Explore|"
    r"Prompt|PROMPT|Skill|SKILL|Workflow|Startup|Creator|Benchmark|Hardware|Software|Feature|Framework|Open\s+Source|"
    r"API|GPU|CPU|NPU|LLM|RAG|SaaS|CRM|B2B|SDK"
    r")(?![A-Za-z'ʻʼ])",
    re.IGNORECASE,
)

# Ordered longest-phrase-first for 100% Uzbek phonetic normalization (offline Silero + bound-suffix stems)
_PRON_FIX_ORDERED: list[tuple[str, str]] = [
    (r"@diyor\.ctr", "diyor nuqta si ti ar"),
    (r"\bdiyor\.ctr\b", "diyor nuqta si ti ar"),
    (r"\b24/7\b", "yigirma to'rt soat"),
    (r"\bThe\s+Information\b", "Ze Informeyshn"),
    (r"\bThe\s+Verge\b", "Ze Verj"),
    (r"\bWall\s+Street\s+Journal\b", "Voll Strit Jurnal"),
    (r"\bFinancial\s+Times\b", "Faynenshl Tayms"),
    (r"\bTechCrunch\b", "TekKranch"),
    (r"\bBloomberg\b", "Blumberg"),
    (r"\bReuters\b", "Royters"),
    (r"\bForbes\b", "Forbs"),
    (r"\bBoston\s+Dynamics\b", "Boston Daynamiks"),
    (r"\bFigure\s+AI\b", "Figyur Ey Ay"),
    (r"\bApple\s+Intelligence\b", "Eppl Intellijens"),
    (r"\bSam\s+Altman\b", "Sem Altman"),
    (r"\bElon\s+Musk\b", "Ilon Mask"),
    (r"\bJensen\s+Huang\b", "Jensen Xuang"),
    (r"\bMark\s+Zuckerberg\b", "Mark Sukerberg"),
    (r"\bPavel\s+Durov\b", "Pavel Durov"),
    (r"\bTim\s+Cook\b", "Tim Kuk"),
    (r"\bSundar\s+Pichai\b", "Sundar Pichay"),
    (r"\bDario\s+Amodei\b", "Dario Amodey"),
    (r"\bBill\s+Gates\b", "Bill Geyts"),
    (r"\bFollow[\-\s]Gate\b", "Follov Geyt"),
    (r"\bSmart[\-\s]Gate\b", "Smart Geyt"),
    (r"\bVibe\s+Coding\b", "Vayb Koding"),
    (r"\bOpen\s+Source\b", "Oupen Sors"),
    (r"\bGoogle\s+DeepMind\b", "Gugl Dipmaynd"),
    (r"\bOpenAI\b", "Oupen Ey Ay"),
    (r"\bChatGPT\b", "Chat Ji Pi Ti"),
    (r"\bGPT[\-\s]?(\d+)\b", r"Ji Pi Ti \1"),
    (r"\bGPT\b", "Ji Pi Ti"),
    (r"\bClaude\b", "Klod"),
    (r"\bSonnet\b", "Sonnet"),
    (r"\bOpus\b", "Opus"),
    (r"\bHaiku\b", "Xayku"),
    (r"\bAnthropic\b", "Antropik"),
    (r"\bDeepSeek\b", "Dipsik"),
    (r"\bGemini\b", "Jeminay"),
    (r"\bNotebookLM\b", "Noutbuk El Em"),
    (r"\bPerplexity\b", "Perpleksiti"),
    (r"\bMidjourney\b", "Midjorni"),
    (r"\bCursor\b", "Kursor"),
    (r"\bWindsurf\b", "Vindserf"),
    (r"\bLovable\b", "Lavabl"),
    (r"\bSora\b", "Sora"),
    (r"\bxAI\b", "Iks Ey Ay"),
    (r"\bGrok\b", "Grok"),
    (r"\bApple\b", "Eppl"),
    (r"\biPhone\b", "Ayfon"),
    (r"\biPad\b", "Ayped"),
    (r"\bMacBook\b", "Makbuk"),
    (r"\bAirPods\b", "Eyrpods"),
    (r"\bVision\s+Pro\b", "Vijn Pro"),
    (r"\bAir\b", "Eyr"),
    (r"\bMax\b", "Maks"),
    (r"\bPlus\b", "Plyus"),
    (r"\bSiri\b", "Siri"),
    (r"\bWWDC\b", "Eppl anjumani"),
    (r"\bTesla\b", "Tesla"),
    (r"\bOptimus\b", "Optimus"),
    (r"\bCybertruck\b", "Saybertrak"),
    (r"\bRobotaxi\b", "Robotaksi"),
    (r"\bSpaceX\b", "Speys Iks"),
    (r"\bStarlink\b", "Starlink"),
    (r"\bNeuralink\b", "Neyralink"),
    (r"\bUnitree\b", "Yunitri"),
    (r"\bNvidia\b", "Envidiya"),
    (r"\bBlackwell\b", "Blekvell"),
    (r"\bRubin\b", "Rubin"),
    (r"\bTSMC\b", "Ti Es Em Si"),
    (r"\bQualcomm\b", "Kvalkomm"),
    (r"\bSnapdragon\b", "Snepdregon"),
    (r"\bMicrosoft\b", "Maykrosoft"),
    (r"\bWindows\b", "Vindovs"),
    (r"\bCopilot\b", "Kopaylot"),
    (r"\bGoogle\b", "Gugl"),
    (r"\bYouTube\b", "Yutub"),
    (r"\bAndroid\b", "Android"),
    (r"\bSamsung\b", "Samsung"),
    (r"\bGalaxy\b", "Galaksi"),
    (r"\bXiaomi\b", "Syaomi"),
    (r"\bHuawei\b", "Xuavey"),
    (r"\bBYD\b", "Bi Vay Di"),
    (r"\bAmazon\b", "Amazon"),
    (r"\bNetflix\b", "Netfliks"),
    (r"\bSpotify\b", "Spotifay"),
    (r"\bMeta\b", "Meta"),
    (r"\bInstagram\b", "Instagram"),
    (r"\bReels\b", "Rils"),
    (r"\bStories\b", "Storis"),
    (r"\bExplore\b", "Eksplor"),
    (r"\bDirect\b", "Dayrekt"),
    (r"\bTelegram\b", "Telegram"),
    (r"\bWhatsApp\b", "Vatsap"),
    (r"\bTikTok\b", "TikTok"),
    (r"\bLinkedIn\b", "Linkdin"),
    (r"\bGitHub\b", "GitXab"),
    (r"\bPython\b", "Payton"),
    (r"\bJavaScript\b", "JavaSkript"),
    (r"\bTypeScript\b", "TaypSkript"),
    (r"\bReact\b", "Riakt"),
    (r"\bNext\.js\b", "Nekst Jey Es"),
    (r"\bNode\.js\b", "Noud Jey Es"),
    (r"\bPostgreSQL\b", "Postgres Kyu El"),
    (r"\bSupabase\b", "Supabeys"),
    (r"\bFirebase\b", "Fayrbeys"),
    (r"\bCloudflare\b", "Klaudfler"),
    (r"\bPlaywright\b", "Pleyrayt"),
    (r"\bDocker\b", "Doker"),
    (r"\bKubernetes\b", "Kubernetis"),
    (r"\bLinux\b", "Linuks"),
    (r"\bBitcoin\b", "Bitkoin"),
    (r"\bEthereum\b", "Efirium"),
    (r"\bBlockchain\b", "Blokcheyn"),
    (r"\bStartup\b", "Startap"),
    (r"\bCreator\b", "Krieytor"),
    (r"\bHardware\b", "Hardver"),
    (r"\bSoftware\b", "Softver"),
    (r"\bFeature\b", "Ficher"),
    (r"\bFramework\b", "Freymvork"),
    (r"\bBenchmark\b", "Benchmark"),
    (r"\bWorkflow\b", "Vorkflou"),
    (r"\bFollow\b", "Follov"),
    (r"\bTrend\b", "trend"),
    (r"\bViral\b", "vayral"),
    (r"\bPrompt\b", "prompt"),
    (r"\bSKILL\b", "skill"),
    (r"\bV(\d+)\b", r"versiya \1"),
    (r"\bAI\b", "sun'iy intellekt"),
    (r"\bLLM\b", "El El Em"),
    (r"\bRAG\b", "Ar Ey Ji"),
    (r"\bSaaS\b", "Sas"),
    (r"\bIT\b", "Ay Ti"),
    (r"\bGPU\b", "Ji Pi Yu"),
    (r"\bCPU\b", "Si Pi Yu"),
    (r"\bNPU\b", "En Pi Yu"),
    (r"\bAPI\b", "Ey Pi Ay"),
    (r"\bSDK\b", "Es Di Key"),
    (r"\bCRM\b", "Si Ar Em"),
    (r"\bPDF\b", "Pi Di Ef"),
    (r"\bHD\b", "yuqori sifat"),
    (r"\b4K\b", "to'rt ka"),
    (r"dokumentatsiya", "dokumyentatsiya"),
]

_UZ_BOUND_SUFFIX_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9\.]{1,22}?)(?:['ʻʼ\-])"
    r"(ning|niki|dagi|dagilar|larni|larga|larda|lardan|lariga|larining|lari|lar|imiz|ingiz|miz|ngiz|dan|ga|ka|qa|da|ni|si|i|dek|day|cha)$",
    re.IGNORECASE,
)


def _get_cmudict() -> dict[str, str]:
    global _CMU_CACHE
    if _CMU_CACHE is not None:
        return _CMU_CACHE
    if _CMUDICT_GZ.exists():
        try:
            with gzip.open(_CMUDICT_GZ, "rt", encoding="utf-8") as f:
                _CMU_CACHE = json.load(f)
                return _CMU_CACHE
        except Exception:
            pass
    _CMU_CACHE = {}
    return _CMU_CACHE


def _arpabet_to_uzbek(arp_str: str) -> str:
    arp = arp_str.split()
    out: list[str] = []
    for idx_p, ph in enumerate(arp):
        base = "".join(c for c in ph if not c.isdigit())
        if ph == "AH0":
            nxt = arp[idx_p + 1] if idx_p + 1 < len(arp) else ""
            out.append("i" if nxt in ("N", "NG", "SH", "S", "Z") else "a")
        else:
            out.append(_ARP2UZ.get(base, base.lower()))
    return "".join(out)


def _english_oov_grapheme_to_uzbek(word: str) -> str:
    """Fallback English spelling -> Uzbek phonetic rules if an English word is not even in 126k CMUdict."""
    s = word
    # Protect Uzbek/English `ch` and `sh` digraphs using temporary placeholders before mapping standalone `c`!
    lo = s.lower()
    lo = re.sub(r"tch", "\x01", lo)
    lo = re.sub(r"ch", "\x01", lo)
    lo = re.sub(r"sh", "\x02", lo)
    rules = [
        (r"tion\b", "\x02n"), (r"sion\b", "jn"), (r"ture\b", "\x01er"),
        (r"ght", "t"), (r"dge", "j"), (r"ck", "k"),
        (r"ph", "f"), (r"th", "s"), (r"wh", "v"), (r"qu", "kv"),
        (r"oo", "u"), (r"ee", "i"), (r"ea", "i"), (r"ou", "au"), (r"ow", "ou"),
        (r"ai", "ey"), (r"ay", "ey"), (r"oi", "oy"),
        (r"c(?=[eiy])", "s"), (r"c", "k"), (r"w", "v"),
    ]
    for pat, rep in rules:
        lo = re.sub(pat, rep, lo)
    lo = lo.replace("\x01", "ch").replace("\x02", "sh")
    return lo.capitalize() if s[:1].isupper() else lo


def english_word_to_uzbek_phonetic(word: str) -> str:
    """Converts a single English word/stem (`Bloomberg`, `Apple`, `Dynamics`) into clean Uzbek phonetics."""
    for pat, repl in _PRON_FIX_ORDERED:
        if re.fullmatch(pat, word, flags=re.IGNORECASE):
            return re.sub(pat, repl, word, flags=re.IGNORECASE)
    cmu = _get_cmudict()
    arp = cmu.get(word.lower())
    if arp:
        res = _arpabet_to_uzbek(arp)
        return res.capitalize() if word[:1].isupper() else res
    if re.search(r"c(?!h)|w|th|ph|oo|ee|ea|tion|sion|ck|ght", word.lower()):
        return _english_oov_grapheme_to_uzbek(word)
    return word


def is_standalone_english_word(token: str) -> bool:
    """
    Returns True when `token` is a standalone English word/brand that should be articulated
    by the Native English Twin Male Voice (`en-US-ChristopherNeural`), while keeping all
    Uzbek native & assimilated words (`robot`, `telefon`, `texnologiya`, `kompaniya`, `ancha`, etc.) in Uzbek!
    """
    clean = token.strip(",.;:!?()[]{}\"“”«»—–-")
    if len(clean) < 2 or not clean.isascii():
        return False
    lo = clean.lower()
    # Any Uzbek apostrophe/digraph/q or native/assimilated Uzbek word -> stay in Uzbek!
    if any(k in lo for k in ("o'", "g'", "'", "q")) or lo in _UZBEK_NATIVE_AND_ASSIMILATED:
        return False
    # Native Uzbek `ch`/`sh`/`x` words (`ancha`, `qachon`, `yaxshi`, `boshqa`, `hech`, `kuchli`) -> stay in Uzbek!
    if ("x" in lo or re.search(r"(?:ch[aoiu]|sh[aoiu]|moq|otgan|ayotgan|ishda|ishga)", lo)) and not _EXPLICIT_EN_PHRASES_RE.fullmatch(clean):
        return False
    # Check Uzbek inflectional endings on Uzbek stems
    for sfx in ("lar", "lari", "larni", "larga", "larda", "lardan", "ning", "dagi", "dan", "ga", "da", "ni",
                "miz", "siz", "moqda", "yapmiz", "adi", "gan", "ish", "lik", "chi"):
        if lo.endswith(sfx) and len(lo) - len(sfx) >= 3:
            root = lo[:-len(sfx)]
            if root in _UZBEK_NATIVE_AND_ASSIMILATED or "q" in root or "x" in root or "ch" in root or "sh" in root:
                return False
    # Explicit brand match
    if _EXPLICIT_EN_PHRASES_RE.fullmatch(clean):
        return True
    # CamelCase tech brands (`LangChain`, `HuggingFace`, `ByteDance`, `OnePlus`, `FastAPI`)
    if any(ch.isupper() for ch in clean[1:]) and any(ch.islower() for ch in clean):
        return True
    # Check 126,052-word CMU English dictionary when orthography clearly signals English (`c(?!h)`, `w`, `th`, `oo`, etc.)
    cmu = _get_cmudict()
    if lo in cmu and re.search(r"(?:c(?!h)|w|th|ph|oo|ee|ea|ou|ow|tion|sion|dge|ck|ght|ai|ew|ey|ui)", lo):
        return True
    return False


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


def _expand_uzbek_numbers_and_symbols(text: str) -> str:
    """Expands currencies, %, ordinals, units, and numbers into clean Uzbek words."""
    _cur_scale = {"t": "trillion", "b": "milliard", "m": "million", "k": "ming"}
    text = re.sub(
        r"\$(\d+(?:[.,]\d+)?)\s*([TtBbMmKk])\b",
        lambda m: f"{number_to_words(m.group(1))} {_cur_scale[m.group(2).lower()]} dollar",
        text,
    )
    text = re.sub(r"\$(\d+(?:[.,]\d+)?)", lambda m: f"{number_to_words(m.group(1))} dollar", text)
    text = re.sub(r"(\d+(?:[.,]\d+)?)\s*%", lambda m: f"{number_to_words(m.group(1))} foiz", text)
    text = re.sub(r"\b(\d+)x\b", lambda m: f"{number_to_words(m.group(1))} barobar", text, flags=re.IGNORECASE)
    text = re.sub(r"\b24/7\b", "yigirma to'rt soat", text)
    text = re.sub(r"@diyor\.ctr", "diyor nuqta si ti ar", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdiyor\.ctr\b", "diyor nuqta si ti ar", text, flags=re.IGNORECASE)

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
        text = re.sub(r"\b(" + "|".join(keys) + r")\b", lambda m: _ABBR.get(m.group(0).lower(), m.group(0)), text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", text)
    text = re.sub(r"\b(\d+)-(?=[A-Za-z'])", lambda m: _ordinal_words(int(m.group(1))) + " ", text)
    text = re.sub(r"\d+[.,]\d+|\d+", lambda m: number_to_words(m.group(0)), text)
    return text


def segment_uzbek_english_bilingual(text: str) -> list[tuple[str, str]]:
    """
    Segments mixed Uzbek + English text into `[('uz' | 'en', chunk_str), ...]` for
    `uzbek_bilingual_hd` (`uz-UZ-SardorNeural` + acoustic twin `en-US-ChristopherNeural`):
    - Bound-suffixed English words (`Apple'ning` -> `Epplning`, `iPhone'da` -> `Ayfonda`)
      are converted into smooth Uzbek phonetics so Uzbek suffixes never split mid-word!
    - Standalone English phrases & brands (`Bloomberg`, `The Information`, `Apple`,
      `iPhone 17 Pro Max`, `Boston Dynamics`, `OpenAI ChatGPT`, plus any CMUdict English word)
      are tagged `'en'` for crisp Native English articulation!
    """
    if not text or not text.strip():
        return []
    s = unicodedata.normalize("NFC", text).translate(_APOS_VARIANTS)
    # Transliterate any accidental Cyrillic characters to Uzbek Latin first
    lat = []
    for ch in s:
        rep = _CYR2LAT.get(ch.lower())
        if rep is not None:
            lat.append(rep.upper() if ch.isupper() and rep else rep)
        else:
            lat.append(ch)
    s = "".join(lat)

    # 0. Cleanly expand common brand + Uzbek suffix (`Apple'ning` -> `Apple kompaniyasining`, `iPhone'da` -> `iPhone modelida`)
    #    so BOTH the Bilingual Twin Voice AND Harfma-Harf Subtitles keep 100% pure brand spelling & pronunciation!
    _brand_noun_map = [
        (r"\b(Apple|OpenAI|Anthropic|Google|Microsoft|Nvidia|Tesla|Meta|Samsung|Amazon|SpaceX)['\-](ning)\b", r"\1 kompaniyasining"),
        (r"\b(Apple|OpenAI|Anthropic|Google|Microsoft|Nvidia|Tesla|Meta|Samsung|Amazon|SpaceX)['\-](da)\b", r"\1 kompaniyasida"),
        (r"\b(Apple|OpenAI|Anthropic|Google|Microsoft|Nvidia|Tesla|Meta|Samsung|Amazon|SpaceX)['\-](ga)\b", r"\1 kompaniyasiga"),
        (r"\b(Apple|OpenAI|Anthropic|Google|Microsoft|Nvidia|Tesla|Meta|Samsung|Amazon|SpaceX)['\-](dan)\b", r"\1 kompaniyasidan"),
        (r"\b(Bloomberg|Reuters|Forbes|TechCrunch)['\-](ning)\b", r"\1 nashrining"),
        (r"\b(Bloomberg|Reuters|Forbes|TechCrunch)['\-](da)\b", r"\1 nashrida"),
        (r"\b(iPhone|iPad|MacBook|Galaxy)['\-](da)\b", r"\1 qurilmasida"),
        (r"\b(iPhone|iPad|MacBook|Galaxy)['\-](ning)\b", r"\1 qurilmasining"),
        (r"\b(ChatGPT|Claude|Gemini|DeepSeek|Siri)['\-](da)\b", r"\1 tizimida"),
        (r"\b(ChatGPT|Claude|Gemini|DeepSeek|Siri)['\-](ni)\b", r"\1 tizimini"),
        (r"\b(ChatGPT|Claude|Gemini|DeepSeek|Siri)['\-](ning)\b", r"\1 tizimining"),
    ]
    for b_pat, b_rep in _brand_noun_map:
        s = re.sub(b_pat, b_rep, s, flags=re.IGNORECASE)

    # 1. Convert any remaining bound-suffixed English stems (`GitHub'dan` -> `GitXabdan`)
    def _fix_bound_suffix(m: re.Match) -> str:
        full_tok = m.group(0)
        stem, sfx = m.group(1), m.group(2)
        if stem.lower() in ("o", "g") or stem.lower() in _UZBEK_NATIVE_AND_ASSIMILATED:
            return full_tok
        uz_stem = english_word_to_uzbek_phonetic(stem)
        # Smooth triple-consonant clusters before consonant-initial Uzbek suffixes (`Epplning` -> `Epilning`)
        uz_stem = re.sub(r"ppl$", "pil", uz_stem, flags=re.IGNORECASE)
        return uz_stem + sfx

    s = re.sub(r"\b[A-Za-z][A-Za-z0-9\.]{1,22}['\-][A-Za-z]{1,10}\b", lambda m: (
        _fix_bound_suffix(bm) if (bm := _UZ_BOUND_SUFFIX_RE.match(m.group(0))) else m.group(0)
    ), s)

    # 2. Mark explicit English multi-word/brand spans FIRST (preserving numbers inside `iPhone 17 Pro Max`, `GPT-5`, etc.)
    spans: list[tuple[str, str]] = []
    pos = 0
    for m in _EXPLICIT_EN_PHRASES_RE.finditer(s):
        if m.start() > pos:
            spans.append(("uz_raw", s[pos:m.start()]))
        end_p = m.end()
        while end_p < len(s) and s[end_p] in ",.;:!?":
            end_p += 1
        spans.append(("en", s[m.start():end_p].strip()))
        pos = end_p
    if pos < len(s):
        spans.append(("uz_raw", s[pos:]))

    # 3. Inside `uz_raw` chunks, check if any remaining standalone token is an unlisted English word (via 126k CMUdict!)
    refined: list[tuple[str, str]] = []
    for kind, chunk in spans:
        if kind == "en":
            refined.append(("en", chunk))
            continue
        # Scan tokens inside `uz_raw`
        tok_pos = 0
        for tm in re.finditer(r"[A-Za-z][A-Za-z0-9'ʻʼ\.\-]*[,.;:!?]?", chunk):
            tok_full = tm.group(0)
            core = tok_full.rstrip(",.;:!?")
            if is_standalone_english_word(core):
                if tm.start() > tok_pos:
                    uz_pre = _expand_uzbek_numbers_and_symbols(chunk[tok_pos:tm.start()]).strip()
                    if uz_pre:
                        refined.append(("uz", uz_pre))
                refined.append(("en", tok_full.strip()))
                tok_pos = tm.end()
        if tok_pos < len(chunk):
            uz_tail = _expand_uzbek_numbers_and_symbols(chunk[tok_pos:]).strip()
            if uz_tail:
                refined.append(("uz", uz_tail))

    # 4. Merge adjacent `('en', ...)` spans so `"OpenAI"` + `"ChatGPT"` or `"Bloomberg,"` + `"Reuters"` flow naturally!
    merged: list[tuple[str, str]] = []
    for lg, tx in refined:
        tx_clean = re.sub(r"\s+", " ", tx).strip()
        if not tx_clean or not re.search(r"[\wА-Яа-я]", tx_clean):
            if merged and tx_clean in (",", ".", "!", "?", ":", ";"):
                merged[-1] = (merged[-1][0], merged[-1][1] + tx_clean)
            continue
        if merged and merged[-1][0] == lg:
            merged[-1] = (lg, merged[-1][1].rstrip() + " " + tx_clean.lstrip())
        else:
            merged.append((lg, tx_clean))
    return merged


def normalize_uzbek_for_tts(text: str) -> str:
    """
    Complete Uzbek phonetic text normalizer for monolingual Uzbek TTS (`Silero 48 kHz b_uzb` fallback):
    expands currencies/numbers, applies 150+ brand rules, AND converts any remaining unlisted
    English word via our 126,052-word CMUdict + English grapheme G2P rules so ZERO English words
    are ever read letter-by-letter!
    """
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

    # First convert bound-suffixed English tokens (`Bloomberg'ning` -> `Blumbergning`)
    text = re.sub(r"\b[A-Za-z][A-Za-z0-9\.]{1,22}['\-][A-Za-z]{1,10}\b", lambda m: (
        (english_word_to_uzbek_phonetic(bm.group(1)) + bm.group(2))
        if (bm := _UZ_BOUND_SUFFIX_RE.match(m.group(0)))
        and bm.group(1).lower() not in ("o", "g")
        and bm.group(1).lower() not in _UZBEK_NATIVE_AND_ASSIMILATED
        else m.group(0)
    ), text)

    for pat, repl in _PRON_FIX_ORDERED:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    text = _expand_uzbek_numbers_and_symbols(text)

    # Convert any remaining unlisted English words via 126,052-word CMUdict + English grapheme fallback!
    def _cmu_tok(m: re.Match) -> str:
        w = m.group(0)
        lo = w.lower()
        if any(k in lo for k in ("o'", "g'", "'", "q")) or lo in _UZBEK_NATIVE_AND_ASSIMILATED:
            return w
        if is_standalone_english_word(w) or re.search(r"c(?!h)|w|th|ph|oo|ee|ea|tion|sion", lo):
            return english_word_to_uzbek_phonetic(w)
        return w

    text = re.sub(r"\b[A-Za-z]{2,}\b", _cmu_tok, text)
    text = "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t")
    return re.sub(r"[ \t]+", " ", text).strip()
