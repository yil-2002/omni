#!/usr/bin/env python3
"""
🤖 @diyor.ctr — 1-Command Autopilot Reels & Carousel Conveyor (`autopilot_conveyor.py`)
======================================================================================
Bitta mavzu va kalit so‘zdan (`/avto Mavzu | KALIT_SOZ` yoki `:8000` Studio 1-Klik) 100% avtomatik:
1. O‘zbekcha sotuvchi Reels ssenariysi + Karusel tuzilmasi + Instagram Caption yaratadi;
2. Yangilangan `DIYOR.CTR` studiya fonli (`IMG_2860.jpeg`) to‘liq kadrli `v4` 2.5D Hook yig‘adi;
3. `Modal Cloud · Kino Bariton HD` (`Rubberband R3 Formant + Spotify Pedalboard C++`, `-14.5 LUFS`) ovoz sintez qiladi;
4. `Modal Faster-Whisper` so‘zma-so‘z akustik taymingini aniq o‘zbekcha imlo bilan birlashtirib,
   xavfsiz pastki zonada (`y=1635`) **Dinamik Karaoke Subtitr** chizadi;
5. Tayyor `9:16` Reel + `4:5` Muqova Slaydni Cloud-Vault va `@diyor937373839337bot` ga yuboradi!
"""
from __future__ import annotations

import asyncio
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if "/home/user/tashqi_xotira" not in sys.path:
    sys.path.insert(0, "/home/user/tashqi_xotira")

from cloud_render_bridge import transcribe_uzbek_via_modal  # noqa: E402
from motion_engine import VAULT_TMP, get_ffmpeg_bin, render_diyor_motion_mp4  # noqa: E402
from photo_brand_engine import render_brand_photo_parallax_frames, render_brand_photo_slide  # noqa: E402
from topic_media_engine import (  # noqa: E402
    fetch_topic_broll_video,
    fetch_topic_editorial_image,
    render_news_broll_hook_frames,
    render_news_cover_slide,
)
from uzbek_male_voice_engine import mux_navoiy_voice_onto_mp4, synthesize_pro_uzbek_voice  # noqa: E402
from uztts_normalize import normalize_uzbek_for_tts  # noqa: E402

import html as _html
import json
import random
import urllib.parse
import aiohttp

DEFAULT_PORTRAIT = Path("/home/user/uploads/IMG_2860.jpeg")
BOLD_FONT_CANDIDATES = [
    "/home/user/claude-techbrief/shared/fonts/Montserrat-Variable.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _pick_font(size: int, weight: int = 850) -> ImageFont.FreeTypeFont:
    for fp in BOLD_FONT_CANDIDATES:
        if Path(fp).exists():
            f = ImageFont.truetype(fp, size)
            if "Variable" in fp:
                try:
                    f.set_variation_by_axes([max(400, min(900, int(weight)))])
                except Exception:
                    pass
            return f
    return ImageFont.load_default()


def resolve_video_mode(topic: str, keyword: str = "", video_mode: str = "auto") -> str:
    """
    Resolves between the 2 @diyor.ctr content tracks:
      - `"edu"`  (1-yo'nalish: O'rganish / Qo'llanma / Tizim + Follow-Gate `cta_terminal`)
      - `"news"` (2-yo'nalish: Yangilik va Maksimal Prosmotr — Jonli B-Roll Hook + Boy Media + Gate'siz `follow_outro`)
    """
    vm = (video_mode or "auto").strip().lower()
    if vm in ("news", "yangilik", "viral", "prosmotr", "2"):
        return "news"
    if vm in ("edu", "organish", "o'rganish", "tutorial", "gate", "1"):
        return "edu"
    kw_clean = re.sub(r"[^A-Za-z0-9_]", "", (keyword or "").upper())
    if kw_clean and kw_clean not in ("SKILL", "AUTO", "NONE", "YOQ"):
        return "edu"
    lo = (topic or "").lower()
    if lo.strip() in ("top", "auto_top", "trend", "top_mavzu"):
        return "news"
    edu_signals = ("qanday", "o'rgan", "organ", "qo'llanma", "qollanma", "qadam", "voronka", "kurs", "dars", "strategiya", "sotuv tizimi", "follow-gate")
    news_signals = (
        "yangilik", "xabar", "chiqdi", "taqdim", "inqilob", "shok", "prosmotr", "fakt", "top", "trend",
        "robot", "openai", "gpt", "gemini", "claude 4", "tesla", "apple", "iphone", "google", "meta", "nvidia",
        "dunyo", "2026", "nima bo'ldi", "elon", "sam altman", "durov", "telegram", "xitoy", "amerika",
    )
    if any(w in lo for w in edu_signals) and not any(w in lo for w in ("yangilik", "xabar", "prosmotr")):
        return "edu"
    if any(w in lo for w in news_signals):
        return "news"
    return "edu"


_VIRAL_BRAND_BOOST = (
    "openai", "chatgpt", "gpt", "apple", "iphone", "siri", "tesla", "optimus", "elon musk",
    "nvidia", "google", "gemini", "deepseek", "anthropic", "claude", "meta", "instagram",
    "telegram", "durov", "tiktok", "youtube", "robot", "humanoid", "chip", "trillion", "billion", "ai ",
)


async def fetch_viral_top_topics(limit: int = 6) -> list[dict[str, Any]]:
    """
    🔥 Live Viral Explore-Ready Topic Radar (`Topga chiqadigan mavzular`):
    Pulls breaking global tech/AI/money stories from Google News Tech RSS + HackerNews Front Page,
    scores them by Instagram Reels viral curiosity & mass appeal, and frames them in crisp Uzbek!
    """
    raw_candidates: list[dict[str, Any]] = []
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) DiyorStudio/2.0"}
    timeout = aiohttp.ClientTimeout(total=6.5)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            gnews_u = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"
            hn_u = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=16"
            r_gn, r_hn = await asyncio.gather(
                sess.get(gnews_u, headers=headers),
                sess.get(hn_u, headers=headers),
                return_exceptions=True,
            )
            if not isinstance(r_gn, Exception) and r_gn.status == 200:
                xml_txt = await r_gn.text(errors="ignore")
                items = re.findall(r"<item>(.*?)</item>", xml_txt, flags=re.S)
                for it in items[:18]:
                    tm = re.search(r"<title>(.*?)</title>", it, flags=re.S)
                    if not tm:
                        continue
                    t_str = _html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", tm.group(1))).strip()
                    src = ""
                    if " - " in t_str:
                        t_str, src = t_str.rsplit(" - ", 1)
                    if len(t_str) >= 22:
                        raw_candidates.append({"en_title": t_str.strip(), "source": src.strip() or "Google News", "base_pts": 65})

            if not isinstance(r_hn, Exception) and r_hn.status == 200:
                hn_d = await r_hn.json()
                for h in (hn_d.get("hits") or [])[:15]:
                    ht = str(h.get("title") or "").strip()
                    pts = int(h.get("points") or 0)
                    if len(ht) >= 20:
                        raw_candidates.append({"en_title": ht, "source": f"HN · {pts}▲", "base_pts": min(95, 45 + pts // 8)})
    except Exception:
        pass

    # Score for Instagram Reels Explore virality (mass audience + giant brands + numbers + AI/future shock)
    scored: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for c in raw_candidates:
        en_t = c["en_title"]
        lo = en_t.lower()
        dedup_k = " ".join(re.findall(r"[a-z0-9]+", lo)[:4])
        if not dedup_k or dedup_k in seen_keys:
            continue
        seen_keys.add(dedup_k)
        score = int(c["base_pts"])
        for b in _VIRAL_BRAND_BOOST:
            if b in lo:
                score += 18
        if re.search(r"\$?\d+\s*(?:billion|trillion|million|%|x)\b|\b2026\b|\bnew\b|\blaunch|\bunveil|\bbreakthrough", lo):
            score += 14
        scored.append({**c, "viral_score": min(99, score)})

    scored.sort(key=lambda x: x["viral_score"], reverse=True)
    top_raw = scored[: max(limit, 6)]

    # Frame into punchy Explore-worthy Uzbek viral hooks via Frontier LLM (fast JSON array)
    if top_raw:
        numbered = "\n".join(f"{i+1}. {x['en_title']} ({x['source']})" for i, x in enumerate(top_raw[:limit]))
        sys_tr = (
            "Sen Instagram Reels'da millionlab prosmotr yig'adigan @diyor.ctr kanalining bosh muharririsan. "
            "Quyidagi real jahon texno-xabarlarini O'zbek auditoriyasi uchun TOPGA CHIQADIGAN, qiziqish uyg'otadigan (curiosity gap), "
            "lekin 100% rost va tabiiy O'zbek tilidagi (lotin yozuvida) mavzu sarlavhalariga aylantir. "
            "FAQAT JSON ro'yxat qaytar: [{\"idx\":1,\"uz_topic\":\"...\",\"mode\":\"news\",\"why_viral\":\"...\"}]"
        )
        raw_tr = await _call_frontier_director_llm(sys_tr, numbered)
        try:
            i0, i1 = raw_tr.find("["), raw_tr.rfind("]")
            if i0 >= 0 and i1 > i0:
                arr = json.loads(raw_tr[i0 : i1 + 1])
                if isinstance(arr, list) and len(arr) >= 2:
                    enriched: list[dict[str, Any]] = []
                    for i, item in enumerate(top_raw[:limit]):
                        m_obj = next((a for a in arr if isinstance(a, dict) and int(a.get("idx") or 0) == i + 1), None) or (arr[i] if i < len(arr) and isinstance(arr[i], dict) else {})
                        uz_t = str(m_obj.get("uz_topic") or item["en_title"]).strip()
                        enriched.append({
                            "rank": i + 1,
                            "uz_topic": uz_t,
                            "en_title": item["en_title"],
                            "source": item["source"],
                            "viral_score": item["viral_score"],
                            "mode": "news",
                            "why_viral": str(m_obj.get("why_viral") or "Global texno trend · Yuqori ushlab qolish (Retention)"),
                        })
                    return enriched
        except Exception:
            pass

    # High-impact curated + live fallback list if LLM formatting skipped
    curated = [
        {
            "rank": 1,
            "uz_topic": "Tesla Optimus gumanoid robotlari fabrikalarda odamlar o‘rnida ish boshladi: 2026-yilgi real kadrlar va narxi",
            "en_title": "Tesla Optimus humanoid robots begin autonomous factory deployment in 2026",
            "source": "Global Tech · Trend #1",
            "viral_score": 98,
            "mode": "news",
            "why_viral": "Vizual robot kadrlari + kelajak kasblari bahsi (Explore CTR 98/100)",
        },
        {
            "rank": 2,
            "uz_topic": "Apple va OpenAI yangi avlod AI chiplari poygasi: iPhone endi internetsiz ham fikrlay oladimi?",
            "en_title": "Apple and OpenAI race on custom AI silicon for on-device iPhone intelligence",
            "source": "Apple & AI · Trend #2",
            "viral_score": 96,
            "mode": "news",
            "why_viral": "Har bir smartfon egasiga tegishli mavzu + kuchli brendlar to‘qnashuvi",
        },
        {
            "rank": 3,
            "uz_topic": "Nvidia va sun’iy intellekt superkompyuterlari: nega bitta kichik chip oltindan ham qimmat bo‘lib ketdi?",
            "en_title": "Nvidia next-generation AI GPU superchips reshape global trillion-dollar economy",
            "source": "Bloomberg Tech · Trend #3",
            "viral_score": 95,
            "mode": "news",
            "why_viral": "Katta pul va texnologiya siri — yuqori saqlash (Save) va ulashish (Share)",
        },
        {
            "rank": 4,
            "uz_topic": "Pavel Durov va Telegram yangi AI davrida: messenjer ichida nimalar tubdan o‘zgarmoqda?",
            "en_title": "Pavel Durov expands Telegram AI ecosystem for billion monthly users",
            "source": "Telegram News · Trend #4",
            "viral_score": 94,
            "mode": "news",
            "why_viral": "O‘zbekistonda eng ommabop ilova — 100% ommaviy qiziqish",
        },
        {
            "rank": 5,
            "uz_topic": "ChatGPT va Claude yordamida kunlik 4 soatlik ishni 15 daqiqada bajarishning 3 ta aniq usuli",
            "en_title": "Practical AI workflow automation with Claude and ChatGPT",
            "source": "@diyor.ctr · Amaliy Top",
            "viral_score": 92,
            "mode": "edu",
            "why_viral": "Yuqori Save + Follow-Gate konversiyasi (1-yo‘nalish O‘rganish)",
        },
    ]
    return curated[:limit]


async def _fetch_live_topic_facts(topic: str) -> str:
    """Pulls live web facts & recent headlines from DuckDuckGo + HackerNews so every video has real fresh substance."""
    q = urllib.parse.quote_plus(topic[:80])
    snippets: list[str] = []
    timeout = aiohttp.ClientTimeout(total=5.0)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            ddg_u = f"https://html.duckduckgo.com/html/?q={q}"
            hn_u = f"https://hn.algolia.com/api/v1/search?query={q}&hitsPerPage=4"
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            r_ddg, r_hn = await asyncio.gather(
                sess.get(ddg_u, headers=headers),
                sess.get(hn_u, headers=headers),
                return_exceptions=True,
            )
            if not isinstance(r_ddg, Exception) and r_ddg.status == 200:
                raw_h = await r_ddg.text()
                titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', raw_h, flags=re.S)
                descs = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', raw_h, flags=re.S)
                for idx, t_raw in enumerate(titles[:4]):
                    t_clean = _html.unescape(re.sub(r"<[^>]+>", "", t_raw)).strip()
                    d_pair = descs[idx] if idx < len(descs) else ("", "")
                    d_clean = _html.unescape(re.sub(r"<[^>]+>", "", d_pair[0] or d_pair[1])).strip()
                    if t_clean:
                        snippets.append(f"- {t_clean}: {d_clean[:160]}")
            if not isinstance(r_hn, Exception) and r_hn.status == 200:
                hn_d = await r_hn.json()
                for h in (hn_d.get("hits") or [])[:3]:
                    if h.get("title"):
                        snippets.append(f"- [Tech] {h['title']} (points: {h.get('points', 0)})")
    except Exception:
        pass
    return "\n".join(snippets[:6])


async def _call_frontier_director_llm(system_prompt: str, user_prompt: str) -> str:
    """Calls uncapped Frontier SSE stream (`reflection/beam-free` -> `stealth/glyph-cluster` -> `llm7`) to author bespoke JSON."""
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    timeout = aiohttp.ClientTimeout(total=28.0)
    async with aiohttp.ClientSession(timeout=timeout) as sess:
        for model in ("reflection/beam-free", "stealth/glyph-cluster"):
            try:
                async with sess.post(
                    "https://api.kilo.ai/api/gateway/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                        "Authorization": "Bearer anonymous",
                        "User-Agent": "Kilo-Code/4.2.0",
                    },
                    json={
                        "model": model,
                        "stream": True,
                        "reasoning": {"effort": "low"},
                        "temperature": 0.65,
                        "max_tokens": 3000,
                        "messages": msgs,
                    },
                ) as resp:
                    if resp.status != 200:
                        continue
                    out_parts: list[str] = []
                    async for raw_line in resp.content:
                        ln = raw_line.decode("utf-8", errors="ignore").strip()
                        if not ln.startswith("data:"):
                            continue
                        ds = ln[5:].strip()
                        if ds == "[DONE]":
                            break
                        try:
                            ev = json.loads(ds)
                            delta = (((ev.get("choices") or [{}])[0]).get("delta") or {}).get("content")
                            if delta:
                                out_parts.append(delta)
                        except Exception:
                            pass
                    joined = "".join(out_parts).strip()
                    if len(joined) >= 80 and "{" in joined:
                        return joined
            except Exception:
                continue

        # Fallback: api.llm7.io
        try:
            async with sess.post(
                "https://api.llm7.io/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": "Bearer unused"},
                json={"model": "codestral-latest", "messages": msgs, "max_tokens": 2600, "temperature": 0.6},
            ) as r7:
                if r7.status == 200:
                    d7 = await r7.json()
                    txt = ((((d7.get("choices") or [{}])[0]).get("message") or {}).get("content") or "").strip()
                    if "{" in txt:
                        return txt
        except Exception:
            pass
    return ""


def _extract_json_dict(raw_txt: str) -> dict[str, Any] | None:
    if not raw_txt:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_txt.strip(), flags=re.I | re.M)
    i0 = cleaned.find("{")
    i1 = cleaned.rfind("}")
    if i0 < 0 or i1 <= i0:
        return None
    try:
        obj = json.loads(cleaned[i0 : i1 + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


async def generate_dynamic_ai_blueprint(
    topic: str,
    keyword: str = "SKILL",
    target_duration: float = 15.0,
    video_mode: str = "auto",
) -> dict[str, Any]:
    """
    TRUE DUAL-TRACK BESPOKE AI REELS DIRECTOR:
      - Track 1 (`mode == "edu"`): O'rganish / Qo'llanma / Arxitektura -> DIYOR.CTR 3D Portrait Hook + step-by-step scenes + Follow-Gate `cta_terminal`.
      - Track 2 (`mode == "news"`): Yangilik va Prosmotr -> 1-soniyadanoq Jonli HD B-Roll Hook + Rasm va Videolarga boy ketma-ketlik + Gate'siz `follow_outro` ("Obuna bo'lsangiz shunday videolarni joylab boramiz!").
    """
    clean_topic = re.sub(r"\s+", " ", (topic or "Sun'iy intellekt yangiliklari").strip())
    raw_kw = re.sub(r"[^A-Za-z0-9_]", "", (keyword or "").upper())[:12]
    mode = resolve_video_mode(clean_topic, raw_kw, video_mode)
    dur_f = float(target_duration or 15.0)
    is_long = dur_f >= 25.0

    facts = await _fetch_live_topic_facts(clean_topic)
    target_words = "92 dan 112 tagacha so'z (taxminan 42-46 soniya)" if is_long else "34 dan 44 tagacha so'z (taxminan 16-19 soniya)"

    if mode == "news":
        ending_rule = (
            "MUHIM (2-YO'NALISH — YANGILIK VA PROSMOTR, GATE YO'Q!): "
            "Bu videoda HECH QANDAY maxfiy kalit so'z, Direct yoki Follow-Gate ISHLATILMAYDI! "
            "Oxirgi sahna sifatida FAQAT `follow_outro` ishlat va diktor nutqi (`display_words_text`) hamda `caption` oxirida tabiiy qilib: "
            "'Obuna bo'lib qo'ysangiz, har kuni shunday eng muhim yangilik va tahlillarni joylab boramiz!' mazmunidagi iliq chaqiriq bo'lsin!"
        )
        scene_plan = (
            "UZUN 44 SONIYALIK TOP VIRAL YANGILIK REEL (7 ta sahna: `media_card` -> `broll_card` -> `news_radar` -> `media_card` -> `broll_card` -> `hook_stat` -> oxirida `follow_outro` — AYNAN MAVZUGA MOS real HD rasmlar va jonli B-roll videolarga maksimal boy!)"
            if is_long
            else "TOPGA CHIQADIGAN VIRAL YANGILIK REEL (5 ta sahna: `media_card` -> `broll_card` -> `news_radar` -> `broll_card` -> oxirida `follow_outro` — har 3 soniyada aynan mavzuga 100% mos yangi HD rasm yoki jonli video kadr almashsin!)"
        )
    else:
        ending_rule = (
            "MUHIM (1-YO'NALISH — O'RGANISH VA QO'LLANMA, FOLLOW-GATE BILAN!): "
            "Bu o'rgatuvchi amaliy video! Oxirgi sahna sifatida `cta_terminal` ishlat va diktor nutqi (`display_words_text`) oxirida "
            "bepul qo'llanma/shablonni olish uchun izohda maxfiy kalit so'zni yozishga chaqir."
        )
        scene_plan = (
            "UZUN 44 SONIYALIK O'QUV REEL (6 ta sahna: `media_card` -> `broll_card` -> `vs_comparison` -> `pipeline_dm` -> `media_card` -> oxirida `cta_terminal`)"
            if is_long
            else "AMALIY O'QUV REEL (5 ta sahna: `media_card` -> `broll_card` -> `pipeline_dm` yoki `vs_comparison` -> `scorecard_bars` -> oxirida `cta_terminal` — mavzuga aynan mos rasm va jonli videolarga boy!)"
        )

    sys_p = (
        "Sen @diyor.ctr Instagram sahifasining bosh kreativ ssenaristi va motion-rejissyorisan. "
        "Vazifang — berilgan MAVZU va YO'NALISH bo'yicha INSTAGRAM TOP (EXPLORE) ga chiqadigan, 100% ORIGINAL, AYNAN MAVZUGA MOS HD Rasm va B-Roll videolarga boy JSON blueprint yaratish!\n"
        "QAT'IY QOIDALAR:\n"
        "1. QAT'IY TAQIQ: Hech qachon '10 kishilik jamoa emas', 'Eski usulda vaqt yo'qotmang', '48 soatda tayyor mahsulot', 'AI IMPERIYA' kabi shablon jumlalarni ISHLATMA!\n"
        "2. Har bir video MAVZUGA 100% MOS, sof, tabiiy Toshkent adabiy O'zbek tilida (lotin yozuvida, chet so'zlarsiz va tarjima g'alizliklarisiz) bo'lsin. Birinchi gapdanoq tomoshabinni ushlab qoladigan kuchli fakt yoki savol bilan boshla!\n"
        "3. `headlineHtml` ichida Fraunces shrifti chiroyli turishi uchun qatorni mantiqiy joydan `<br>` bilan bo'l va eng kuchli 1-2 so'zni `<em>...</em>` ichiga ol.\n"
        f"4. {ending_rule}\n"
        "5. O'TA MUHIM (AYNAN MAVZUGA MOS MEDIA!): `hookImageQuery`, `hookBrollQuery`, hamda har bir `media_card` (`imageQuery`) va `broll_card` (`brollQuery`) uchun UMUMIY 'office laptop' kabi so'zlarni EMAS, balki AYNAN MAVZUDAGI kompaniya, shaxs, qurilma yoki jarayonning aniq inglizcha nomini yoz (masalan: `'Tesla Optimus humanoid robot walking factory'`, `'Apple iPhone 17 Pro AI chip closeup'`, `'Sam Altman OpenAI semiconductor wafer'`, `'Nvidia Blackwell GPU server rack'`, `'Pavel Durov Telegram smartphone app'`). Har bir sahnadagi qidiruv so'rovi BIR-BIRIDAN FARQLI rakursda bo'lsin!\n"
        "6. Sahna turlari:\n"
        "   - `media_card`: `{\"type\":\"media_card\",\"eyebrow\":\"VIZUAL DALIL · FAKTLAR\",\"headlineHtml\":\"...\",\"captionText\":\"1 qator qisqa o'zbekcha izoh\",\"imageQuery\":\"exact specific English press/product photo search query (4-6 words)\"}`\n"
        "   - `broll_card`: `{\"type\":\"broll_card\",\"eyebrow\":\"JONLI LAVHA · B-ROLL\",\"headlineHtml\":\"...\",\"captionText\":\"1 qator qisqa o'zbekcha izoh\",\"brollQuery\":\"exact specific English video/press query (3-5 words, include brand/product + visual subject)\"}`\n"
        "   - `news_radar`: `{\"type\":\"news_radar\",\"eyebrow\":\"ASOSIY FAKTLAR · RADAR\",\"headlineHtml\":\"...\",\"items\":[{\"badge\":\"FAKT · 01\",\"title\":\"...\",\"source\":\"...\"}, ...3 ta]}`\n"
        "   - `vs_comparison`: `{\"type\":\"vs_comparison\",\"eyebrow\":\"TAQQOSLASH\",\"headlineHtml\":\"...\",\"oldTitle\":\"...\",\"oldPoints\":[\"...\",\"...\"],\"newTitle\":\"...\",\"newPoints\":[\"...\",\"...\"]}`\n"
        "   - `hook_stat`: `{\"type\":\"hook_stat\",\"eyebrow\":\"RAQAMLARDA\",\"headlineHtml\":\"...\",\"subtext\":\"...\",\"statLabel\":\"...\",\"statValue\":87,\"statSuffix\":\"%\",\"barPercent\":87}`\n"
        "   - `pipeline_dm`: `{\"type\":\"pipeline_dm\",\"eyebrow\":\"QADAMMA-QADAM\",\"headlineHtml\":\"...\",\"steps\":[{\"tag\":\"01 · QADAM\",\"title\":\"...\",\"meta\":\"...\"}, ...3 ta]}`\n"
        "   - `scorecard_bars`: `{\"type\":\"scorecard_bars\",\"eyebrow\":\"SAMARADORLIK\",\"headlineHtml\":\"...\",\"ringScore\":96,\"metrics\":[{\"label\":\"...\",\"val\":85,\"suffix\":\"%\",\"pct\":85}, ...3 ta]}`\n"
        "   - `code_architecture`: `{\"type\":\"code_architecture\",\"eyebrow\":\"TEXNIK YECHIM\",\"headlineHtml\":\"...\",\"subtext\":\"...\",\"fileName\":\"agent.py\",\"badge\":\"AI\",\"codeLines\":[\"...\", ...4-5 qator]}`\n"
        "   - `cta_terminal` (faqat 1-yo'nalish O'rganish videolari oxirida): `{\"type\":\"cta_terminal\",\"eyebrow\":\"BEPUL QO'LLANMA · DIRECT\",\"headlineHtml\":\"Izohda <em>«KALIT»</em><br>deb yozing\",\"subtext\":\"...\",\"keyword\":\"KALIT\"}`\n"
        "   - `follow_outro` (faqat 2-yo'nalish Yangilik videolari oxirida — Gate'siz!): `{\"type\":\"follow_outro\",\"eyebrow\":\"KUNLIK YANGILIKLAR · @DIYOR.CTR\",\"headlineHtml\":\"Shunday videolarni<br><em>o‘tkazib yubormang</em>\",\"subtext\":\"Obuna bo‘lib qo‘ysangiz, har kuni shunday eng muhim yangilik va tahlillarni joylab boramiz!\"}`\n"
        "7. INGLIZCHA BREND VA ATAMALAR QOIDASI: `display_words_text` va `spokenText` ichida mashhur brend va texnologik nomlarni (Apple, iPhone, Bloomberg, The Verge, OpenAI, ChatGPT, Claude, Tesla Optimus, Boston Dynamics) asl inglizcha imlosida yozing va ularga (-ning, -da, -ni, -ga) qo'shimchasini bevosita yopishtirmang (masalan: `Apple'ning` o'rniga `Apple kompaniyasining`, `iPhone'da` o'rniga `iPhone modelida`, `Claude'ni` o'rniga `Claude tizimini` deb yozing)!\n"
        "8. O'TA QAT'IY HIKOYA VA SAHNA MOSLIGI QOIDASI (CHALA GAP TAQIQLANADI!): HECH QACHON gap oxirida yoki o'rtasida 'Keling batafsil bilib olamiz', 'Hozir aytib beraman', 'Videoni oxirigacha ko'ring' kabi javobsiz va'da gaplarni YOZMA! Video to'liq mantiqiy yakunga ega bo'lsin: `hookSpoken` (kuchli 1 gaplik kirish fakti) -> har bir `scenes[i]` ichida AYNAN SHU SAHNADAGI rasm/kartaga 100% mos 1 gaplik to'liq fakt (`spokenText`) -> oxirgi sahnada yakuniy xulosa va obuna/kalit so'z chaqirig'i!\n"
        "9. FAQAT TOZA JSON QAYTAR (hech qanday izohsiz!):"
    )

    usr_p = (
        f"MAVZU: {clean_topic}\n"
        f"TANLANGAN YO'NALISH: {'2-YO`NALISH: YANGILIK VA MAKSIMAL PROSMOTR (B-Roll Hook + Rasm/Videolarga boy + Gate YO`Q, oxirida Follow chaqirig`i!)' if mode == 'news' else '1-YO`NALISH: O`RGANISH VA AMALIY QO`LLANMA (Portret Hook + Qadamma-qadam dars + Follow-Gate kalit so`z!)'}\n"
        f"SAHNALAR REJASI: {scene_plan}\n"
        f"DIKTOR MATNI HAJMI: {target_words}\n"
        + (f"FOYDALANUVCHI KALIT SO'ZI: {raw_kw if (raw_kw and raw_kw != 'SKILL') else 'Mavzuga mos qisqa kalit so`z tanla'}\n" if mode == "edu" else "")
        + (f"\nINTERNETDAN TOPILGAN REAL FAKTLAR:\n{facts}\n" if facts else "")
        + "\nQuyidagi JSON strukturasini to'liq to'ldirib qaytar (har bir `scenes` obyektida AYNAN o'sha sahna sarlavhasi va rasmiga mos 1 gaplik `spokenText` bo'lishi SHART!):\n"
        '{\n'
        '  "theme": "lotion yoki warm",\n'
        '  "keyword": "KALIT_SOZ_YOKI_YANGILIK_TEGI",\n'
        '  "behindWord": "2 SOZ <=12 HARF",\n'
        '  "kicker": "TEZKOR YANGILIK · 2026 yoki AMALIY DARS",\n'
        '  "hookHeadlineHtml": "Sensatsion yoki kuchli sarlavha <br> va <em>urg\'u</em>",\n'
        '  "hookSubtext": "1 gaplik aniq qiziqtiruvchi izoh",\n'
        '  "hookSpoken": "0-soniyada Hook kadr ustida aytiladigan 1 gaplik aniq kirish fakti",\n'
        '  "hookBrollQuery": "2-3 concrete English visual words for opening B-roll video (e.g. \'humanoid robot\', \'data center\', \'electric car\')",\n'
        '  "hookImageQuery": "specific English search query for cover/hook photo (3-5 words)",\n'
        '  "callouts": [{"label": "FAKT", "value": "..."}, {"label": "MANBA", "value": "..."}],\n'
        '  "display_words_text": "hookSpoken va barcha scenes[].spokenText birlashmasidan iborat to\'liq tugallangan matn",\n'
        '  "scenes": [\n'
        '    {"type": "media_card", "spokenText": "Aynan shu 1-sahna rasmi va sarlavhasiga mos to\'liq fakt gap.", ...},\n'
        '    ...\n'
        '  ],\n'
        '  "caption": "Instagram post uchun to\'liq foydali matn"\n'
        '}'
    )

    raw_ai = await _call_frontier_director_llm(sys_p, usr_p)
    parsed = _extract_json_dict(raw_ai)

    if parsed and parsed.get("display_words_text") and isinstance(parsed.get("scenes"), list) and len(parsed["scenes"]) >= 2:
        if mode == "news":
            kw = re.sub(r"[^A-Za-z0-9_]", "", str(parsed.get("keyword") or "NEWS").upper())[:12] or "NEWS"
        else:
            kw = re.sub(r"[^A-Za-z0-9_]", "", str((raw_kw if (raw_kw and raw_kw != "SKILL") else parsed.get("keyword")) or "TIZIM").upper())[:12] or "TIZIM"
        behind = str(parsed.get("behindWord") or clean_topic.split()[0]).upper()[:13]
        lo_t = clean_topic.lower()
        if mode == "news" or any(w in lo_t for w in ("yangilik", "kod", "python", "ai ", "model", "agent", "texno")):
            theme = "lotion"
        elif any(w in lo_t for w in ("sotuv", "biznes", "mijoz", "pul", "psixolog", "brend")):
            theme = "warm"
        else:
            theme = "warm" if str(parsed.get("theme", "")).lower() == "warm" else "lotion"

        disp_txt = re.sub(r"\s+", " ", str(parsed["display_words_text"]).strip())
        if mode == "news" and not any(w in disp_txt.lower() for w in ("obuna", "follov", "follow")):
            if not disp_txt.endswith((".", "!", "?")):
                disp_txt += "."
            disp_txt += " Obuna bo'lib qo'ysangiz, har kuni shunday muhim yangiliklarni joylab boramiz!"
        # Preserve original English brand orthography in `vo_script` so `uzbek_bilingual_hd` speaks
        # English words natively (`ChristopherNeural`) while monolingual fallbacks normalize internally!
        vo_script = disp_txt
        callouts = parsed.get("callouts") if isinstance(parsed.get("callouts"), list) and len(parsed["callouts"]) >= 2 else [
            {"label": "FAKT", "value": behind},
            {"label": "TAHLIL" if mode == "news" else "DIRECT", "value": "@diyor.ctr" if mode == "news" else f"«{kw}»"},
        ]

        scenes_list: list[dict[str, Any]] = []
        for sc in parsed["scenes"][:7]:
            if not (isinstance(sc, dict) and sc.get("type")):
                continue
            if mode == "news" and sc["type"] == "cta_terminal":
                # Strictly forbid Follow-Gate in Mode 2 (`news`)!
                continue
            if mode == "edu" and sc["type"] == "cta_terminal":
                sc["keyword"] = kw
            scenes_list.append(sc)

        if mode == "news":
            if not any(s.get("type") == "follow_outro" for s in scenes_list):
                scenes_list.append({
                    "type": "follow_outro",
                    "eyebrow": "KUNLIK YANGILIKLAR · @DIYOR.CTR",
                    "headlineHtml": "Shunday videolarni<br><em>o‘tkazib yubormang</em>",
                    "subtext": "Obuna bo‘lib qo‘ysangiz, har kuni shunday eng muhim yangilik va vizual tahlillarni joylab boramiz!",
                })
        else:
            if not any(s.get("type") == "cta_terminal" for s in scenes_list):
                scenes_list.append({
                    "type": "cta_terminal",
                    "eyebrow": "BEPUL FOYDALI MATERIAL · DIRECT",
                    "headlineHtml": f"Izohda <em>«{kw}»</em><br>deb yozing",
                    "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — 3 soniyada Direct’ga yuboriladi!",
                    "keyword": kw,
                })

        fb_iq, fb_vq = _infer_english_visual_queries(clean_topic)
        scenes_list = _ensure_visual_scene_slots(scenes_list, clean_topic, mode)
        hook_spoken_raw = str(parsed.get("hookSpoken") or "")
        beat_texts, clean_disp_joined = _synchronize_beats_and_scenes(
            hook_spoken_raw, disp_txt, scenes_list, mode, kw
        )
        return {
            "video_mode": mode,
            "topic": clean_topic,
            "keyword": kw,
            "theme": theme,
            "is_long": is_long,
            "target_duration": dur_f,
            "behindWord": behind,
            "beat_texts": beat_texts,
            "voice_script": clean_disp_joined,
            "display_words_text": clean_disp_joined,
            "hookBrollQuery": str(parsed.get("hookBrollQuery") or fb_vq).strip(),
            "hookImageQuery": str(parsed.get("hookImageQuery") or fb_iq).strip(),
            "hook_config": {
                "behindWord": behind,
                "kicker": str(parsed.get("kicker") or ("TEZKOR YANGILIK · 2026" if mode == "news" else f"AMALIY DARS · {kw}"))[:34],
                "headlineHtml": str(parsed.get("hookHeadlineHtml") or f"{clean_topic[:28]} <em>tahlili</em>"),
                "subtext": str(parsed.get("hookSubtext") or f"@diyor.ctr · {clean_topic[:55]}"),
                "callouts": callouts[:2],
                "topicTag": ("yangiliklar · @diyor.ctr" if mode == "news" else f"{kw.lower()} · @diyor.ctr"),
                "handle": "@DIYOR.CTR",
            },
            "scenes": scenes_list,
            "caption": str(
                parsed.get("caption")
                or (
                    f"🔥 {clean_topic}\n\nObuna bo‘lib qo‘ysangiz (@diyor.ctr), har kuni shunday eng muhim yangilik va tahlillarni joylab boramiz!"
                    if mode == "news"
                    else f"🔥 {clean_topic}\n\nObuna bo‘ling (@diyor.ctr) va izohda «{kw}» deb yozing!"
                )
            ),
        }

    fb = build_autopilot_blueprint(clean_topic, raw_kw or "TIZIM", target_duration=dur_f, video_mode=mode)
    return fb


def build_autopilot_blueprint(
    topic: str,
    keyword: str = "SKILL",
    target_duration: float = 14.0,
    video_mode: str = "auto",
) -> dict[str, Any]:
    """Offline deterministic fallback blueprint if network LLM is unreachable."""
    clean_topic = re.sub(r"\s+", " ", (topic or "Sun'iy intellekt tahlili").strip())
    mode = resolve_video_mode(clean_topic, keyword, video_mode)
    kw = "NEWS" if mode == "news" else (re.sub(r"[^A-Za-z0-9_]", "", (keyword or "TIZIM").upper())[:14] or "TIZIM")
    is_long = float(target_duration or 14.0) >= 25.0
    fb_iq, fb_vq = _infer_english_visual_queries(clean_topic)

    words = [w for w in re.split(r"[\s—–\-+/(),.]+", clean_topic) if len(w) >= 2]
    stop = {"VA", "BILAN", "UCHUN", "ORQALI", "QANDAY", "QURISH", "YANGI", "BIR", "KISHILIK"}
    key_words = [w.upper() for w in words if w.upper() not in stop]
    if len(key_words) >= 2 and len(f"{key_words[0]} {key_words[1]}") <= 13:
        behind = f"{key_words[0]} {key_words[1]}"
    elif key_words:
        behind = key_words[0][:13]
    else:
        behind = "AI YANGILIK" if mode == "news" else "AI TIZIM"

    short_t = clean_topic[:44]
    t_parts = short_t.split()
    mid = max(1, len(t_parts) // 2)
    l1 = " ".join(t_parts[:mid])
    l2 = " ".join(t_parts[mid:]) or ("yangi bosqichda" if mode == "news" else "amaliy tahlil")

    if mode == "news":
        display_words_text = (
            f"Texnologiya olamida katta yangilik: {clean_topic}! "
            f"Yangi ma'lumotlarga ko'ra, bu o'zgarish millionlab foydalanuvchilar va soha bozoriga bevosita ta'sir ko'rsatmoqda. "
            f"Mutaxassislar jarayon kutilganidan uch barobar tez rivojlanayotganini tasdiqladi. "
            f"Obuna bo'lib qo'ysangiz, har kuni shunday eng muhim yangilik va tahlillarni joylab boramiz!"
        )
        voice_script = display_words_text
        scenes = [
            {
                "type": "media_card",
                "eyebrow": "VIZUAL DALIL · FAKTLAR",
                "headlineHtml": f"{l1}<br><em>{l2}</em>",
                "captionText": f"{clean_topic[:52]} — asosiy kadr",
                "imageQuery": fb_iq,
            },
            {
                "type": "broll_card",
                "eyebrow": "JONLI LAVHA · B-ROLL",
                "headlineHtml": "Jarayon <em>real</em><br>kadrlar ichida",
                "captionText": "Texnologiya amaliyotda qanday ishlamoqda",
                "brollQuery": fb_vq,
            },
            {
                "type": "follow_outro",
                "eyebrow": "KUNLIK YANGILIKLAR · @DIYOR.CTR",
                "headlineHtml": "Shunday videolarni<br><em>o‘tkazib yubormang</em>",
                "subtext": "Obuna bo‘lib qo‘ysangiz, har kuni shunday eng muhim yangilik va vizual tahlillarni joylab boramiz!",
            },
        ]
        caption = f"🔥 {clean_topic}\n\nObuna bo‘lib qo‘ysangiz (@diyor.ctr), har kuni shunday eng muhim yangilik va tahlillarni joylab boramiz!"
        c1, c2 = {"label": "FAKT", "value": behind}, {"label": "MANBA", "value": "Global Tech"}
    else:
        display_words_text = (
            f"Ko'pchilik {clean_topic} bo'yicha eng muhim amaliy mexanizmni e'tibordan chetda qoldiradi. "
            f"Birinchi qadam: jarayonni aniq tizimga soling. "
            f"Ikkinchi qadam: sun'iy intellekt yordamida takroriy ishlarni avtomatlashtiring. "
            f"To'liq bepul qo'llanmani olish uchun obuna bo'ling va izohda «{kw}» deb yozing!"
        )
        voice_script = display_words_text
        scenes = [
            {
                "type": "media_card",
                "eyebrow": "AMALIY VIZUAL · DARS",
                "headlineHtml": f"{l1}<br><em>{l2}</em>",
                "captionText": f"{clean_topic[:52]} — amaliy ko'rinish",
                "imageQuery": fb_iq,
            },
            {
                "type": "pipeline_dm",
                "eyebrow": "QADAMMA-QADAM TIZIM",
                "headlineHtml": "3 ta aniq <em>amaliy</em><br>bosqich",
                "steps": [
                    {"tag": "01 · QADAM", "title": "Maqsad va strukturani belgilash", "meta": "Aniq reja"},
                    {"tag": "02 · QADAM", "title": "AI vositalarini ulash", "meta": "Avtomatika"},
                    {"tag": "03 · QADAM", "title": "Natijani o‘lchash va kuchaytirish", "meta": "O‘sish"},
                ],
            },
            {
                "type": "cta_terminal",
                "eyebrow": "BEPUL QO‘LLANMA · DIRECT",
                "headlineHtml": f"Izohda <em>«{kw}»</em><br>deb yozing",
                "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — 3 soniyada Direct’ga yuboriladi!",
                "keyword": kw,
            },
        ]
        caption = f"🚀 {clean_topic}\n\nObuna bo‘ling (@diyor.ctr) va izohda «{kw}» deb yozing — bepul qo‘llanma Direct’ingizga boradi!"
        c1, c2 = {"label": "DARS", "value": behind}, {"label": "DIRECT", "value": f"«{kw}»"}

    scenes = _ensure_visual_scene_slots(scenes, clean_topic, mode)
    beat_texts, clean_disp_joined = _synchronize_beats_and_scenes("", display_words_text, scenes, mode, kw)

    return {
        "video_mode": mode,
        "topic": clean_topic,
        "keyword": kw,
        "theme": "lotion" if mode == "news" else "warm",
        "is_long": is_long,
        "target_duration": float(target_duration or 14.0),
        "behindWord": behind,
        "beat_texts": beat_texts,
        "voice_script": clean_disp_joined,
        "display_words_text": clean_disp_joined,
        "hookBrollQuery": fb_vq,
        "hookImageQuery": fb_iq,
        "hook_config": {
            "behindWord": behind,
            "kicker": "TEZKOR YANGILIK · 2026" if mode == "news" else f"AMALIY DARS · {kw}",
            "headlineHtml": f"{l1} <em>{l2}</em>",
            "subtext": f"@diyor.ctr · {clean_topic[:58]}",
            "callouts": [c1, c2],
            "topicTag": "yangiliklar · @diyor.ctr" if mode == "news" else f"dars · {kw.lower()}",
            "handle": "@DIYOR.CTR",
        },
        "scenes": scenes,
        "caption": caption,
    }


_DANGLING_CLIFFHANGER_RE = re.compile(
    r"(?:keling[,\s]+)?(?:buni\s+|bu\s+haqda\s+|endi\s+|hozir\s+)?(?:batafsil\s+|birgalikda\s+|yaqindan\s+)?"
    r"(?:bilib\s+olamiz|ko['ʻʼ]?rib\s+chiqamiz|aytib\s+beraman|gaplashamiz|tushuntiraman|ko['ʻʼ]?ramiz)[!.\s]*|"
    r"(?:videoni\s+oxirigacha\s+ko['ʻʼ]?ring|shu\s+videoda\s+aytib\s+beraman)[!.\s]*",
    re.IGNORECASE,
)


def _strip_dangling_cliffhangers(text: str) -> str:
    """Removes empty teaser cliffhangers ('keling batafsil bilib olamiz', 'hozir aytib beraman') so every Reel finishes its story completely!"""
    if not text:
        return ""
    cleaned = _DANGLING_CLIFFHANGER_RE.sub(" ", text)
    cleaned = re.sub(r"\s+([,.!?:;])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _split_sentences_clean(text: str) -> list[str]:
    pts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if p.strip()]
    return pts


def _synchronize_beats_and_scenes(
    hook_spoken: str,
    full_disp_text: str,
    scenes_list: list[dict[str, Any]],
    mode: str,
    kw: str,
) -> tuple[list[str], str]:
    """
    Guarantees 1-to-1 narrative & timing lock:
      - Returns `(beat_texts, joined_display_text)` where `len(beat_texts) == 1 + len(scenes_list)`:
        * `beat_texts[0]` -> spoken during Opening Hook (`0.0s .. hook_dur`)
        * `beat_texts[i + 1]` -> spoken during `scenes_list[i]`!
      - Strips any unfinished 'aytib beraman / bilib olamiz' cliffhangers so every thought concludes cleanly!
    """
    outro_default = (
        "Obuna bo'lib qo'ysangiz, har kuni shunday eng muhim yangilik va tahlillarni joylab boramiz!"
        if mode == "news"
        else f"To'liq bepul qo'llanmani olish uchun obuna bo'ling va izohda {kw} deb yozing!"
    )

    h_clean = _strip_dangling_cliffhangers(hook_spoken)
    scene_spokens = [_strip_dangling_cliffhangers(str(s.get("spokenText") or "")) for s in scenes_list]

    # If the LLM supplied explicit `hookSpoken` + `spokenText` for every scene, validate & finalize!
    if h_clean and all(bool(x) for x in scene_spokens):
        last_low = scene_spokens[-1].lower()
        if mode == "news" and not any(w in last_low for w in ("obuna", "follov", "joylab")):
            scene_spokens[-1] = (scene_spokens[-1].rstrip(".!? ") + ". " + outro_default).strip()
        elif mode == "edu" and kw.lower() not in last_low and "izoh" not in last_low:
            scene_spokens[-1] = (scene_spokens[-1].rstrip(".!? ") + ". " + outro_default).strip()
        beats = [h_clean, *scene_spokens]
        for idx_s, s_txt in enumerate(scene_spokens):
            scenes_list[idx_s]["spokenText"] = s_txt
        return beats, " ".join(beats)

    # Otherwise partition `full_disp_text` sentences monotonically across `[Hook, Scene_0, ..., Scene_{N-1}]`
    cleaned_full = _strip_dangling_cliffhangers(full_disp_text)
    sents = _split_sentences_clean(cleaned_full)
    # Separate closing CTA sentence if already at end
    if sents and any(w in sents[-1].lower() for w in ("obuna", "follov", "izohda", "joylab boramiz")):
        outro_sent = sents.pop()
    else:
        outro_sent = outro_default

    body_slots = max(1, len(scenes_list))  # Hook + (len(scenes_list) - 1) content scenes; last scene gets `outro_sent`
    if len(sents) < body_slots:
        # Derive missing factual sentences directly from scene headlines/captions so every card matches speech!
        while len(sents) < body_slots:
            sc_ref = scenes_list[min(len(sents) - 1 if len(sents) > 0 else 0, len(scenes_list) - 1)]
            hd_plain = re.sub(r"<[^>]+>", " ", str(sc_ref.get("headlineHtml") or "")).strip()
            cap_plain = str(sc_ref.get("captionText") or sc_ref.get("subtext") or "").strip()
            synth_s = f"{hd_plain}: {cap_plain}." if (hd_plain and cap_plain) else (f"{hd_plain}." if hd_plain else "Jarayon yangi bosqichga chiqmoqda.")
            sents.append(re.sub(r"\s+", " ", synth_s))

    # Group `sents` into `body_slots` buckets (`slot 0` = Hook, `slots 1..N-1` = content scenes)
    buckets: list[str] = []
    n_s = len(sents)
    for b_i in range(body_slots):
        i0 = int(round(b_i * n_s / float(body_slots)))
        i1 = int(round((b_i + 1) * n_s / float(body_slots)))
        chunk_s = " ".join(sents[i0:max(i0 + 1, i1)]).strip()
        buckets.append(chunk_s)

    beats_out = [*buckets, outro_sent]
    for idx_s in range(len(scenes_list)):
        scenes_list[idx_s]["spokenText"] = beats_out[idx_s + 1]
    return beats_out, " ".join(beats_out)


def align_clean_uzbek_words(display_text: str, whisper_words: list[dict[str, Any]], total_dur: float) -> list[dict[str, Any]]:
    """
    Maps Modal Faster-Whisper's exact acoustic `[start, end]` timestamps monotonically onto the
    100% typo-free Uzbek Latin display words so brand names (`Claude`, `SKILL`, `48`) are NEVER misspelled!
    """
    raw_tokens = [t for t in display_text.strip().split() if t]
    clean_tokens: list[str] = []
    for tok in raw_tokens:
        if tok in ("—", "–", "-") and clean_tokens:
            clean_tokens[-1] = clean_tokens[-1] + " " + tok
        else:
            clean_tokens.append(tok)
    if not clean_tokens:
        return []

    n_disp = len(clean_tokens)
    if whisper_words and len(whisper_words) >= 3:
        n_w = len(whisper_words)
        aligned: list[dict[str, Any]] = []
        for i, tok in enumerate(clean_tokens):
            w_idx0 = min(n_w - 1, int(math.floor(i * n_w / float(n_disp))))
            w_idx1 = min(n_w - 1, max(w_idx0, int(math.floor((i + 1) * n_w / float(n_disp))) - 1))
            t_start = float(whisper_words[w_idx0]["start"])
            t_end = float(whisper_words[w_idx1]["end"])
            if t_end <= t_start:
                t_end = t_start + 0.24
            aligned.append({"word": tok, "start": round(t_start, 2), "end": round(t_end, 2)})
        return aligned

    # Fallback proportional character-weighted timing if offline
    speech_span = max(1.5, total_dur - 0.35)
    weights = [max(2, len(t)) for t in clean_tokens]
    tot_w = float(sum(weights))
    cur_t = 0.08
    out = []
    for tok, w in zip(clean_tokens, weights):
        dt = speech_span * (w / tot_w)
        out.append({"word": tok, "start": round(cur_t, 2), "end": round(cur_t + dt, 2)})
        cur_t += dt
    return out


def _probe_frame_luminance_per_frame(ffmpeg_bin: str, in_mp4: Path, fps: int, y_top: int, bar_h: int, total_frames: int) -> list[float]:
    """
    Samples average luminance (`0..255`) inside the subtitle zone (`x=240..840, y=y_top..y_top+bar_h`)
    across `in_mp4` in a single fast `16x4` downscaled raw gray pass (<0.15s) so borderless subtitles
    automatically switch between crisp `#FAF9F5` cream (on dark portrait) and `#141413` charcoal ink
    (on `#FAF9F5` Claude TechBrief paper) at the exact frame of every scene cut!
    """
    w_crop, h_crop = 600, max(24, bar_h)
    x_crop = (1080 - w_crop) // 2
    cmd = [
        ffmpeg_bin, "-v", "error",
        "-i", str(in_mp4),
        "-vf", f"fps={fps},crop={w_crop}:{h_crop}:{x_crop}:{y_top},scale=8:2,format=gray",
        "-f", "rawvideo", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True).stdout or b""
    px_per_frame = 16
    lumas: list[float] = []
    for idx in range(total_frames):
        chunk = raw[idx * px_per_frame : (idx + 1) * px_per_frame]
        if len(chunk) == px_per_frame:
            lumas.append(sum(chunk) / float(px_per_frame))
        else:
            lumas.append(lumas[-1] if lumas else 40.0)
    return lumas


def _group_words_into_kinetic_beats(word_timings: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """
    Splits aligned words into natural 2–3 word Ali Abdaal / Vox editorial beats:
      - Max 3 words and <= 21 visible characters per beat so words stay bold, airy, and centered;
      - Breaks cleanly at sentence/clause punctuation (`.` `,` `!` `?` `:` `;` `—`).
    """
    groups: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    cur_chars = 0
    for w in word_timings:
        txt = str(w.get("word") or "").strip()
        if not txt:
            continue
        add_len = len(txt) + (1 if cur else 0)
        if cur and (len(cur) >= 3 or (cur_chars + add_len > 21)):
            groups.append(cur)
            cur = []
            cur_chars = 0
        cur.append(w)
        cur_chars += len(txt) + (1 if len(cur) > 1 else 0)
        if txt.endswith((".", "!", "?", ",", ":", ";", "—")) and len(cur) >= 1:
            groups.append(cur)
            cur = []
            cur_chars = 0
    if cur:
        groups.append(cur)
    return groups


def render_karaoke_overlay_onto_mp4(
    in_mp4: Path,
    out_mp4: Path,
    word_timings: list[dict[str, Any]],
    fps: int = 30,
    y_center: int = 1642,
) -> None:
    """
    NEW `Kinetic Pop` Subtitle Engine (Ali Abdaal / Vox Luxury Style):
      - `Montserrat-Variable` geometric typography (760 Bold inactive + 900 Black active word);
      - True 3-stage `easeOutBack` upward spring pop (`1.07x -> 1.17x -> 1.13x`) on every spoken word;
      - ZERO underline bar, ZERO dark box (`qora xoshiyasiz`), soft Gaussian cinema drop-shadow;
      - Per-frame luminance adaptation between dark/B-Roll frames and `#FAF9F5`/`#F4EDE3` paper frames!
    """
    if not word_timings:
        out_mp4.write_bytes(in_mp4.read_bytes())
        return

    ffmpeg_bin = get_ffmpeg_bin()
    proc = subprocess.run([ffmpeg_bin, "-i", str(in_mp4)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    v_dur = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 10.0
    total_frames = max(1, int(round(v_dur * fps)))

    groups = _group_words_into_kinetic_beats(word_timings)
    fnt_inact = _pick_font(46, weight=760)
    fnt_pop_stages = [
        _pick_font(50, weight=880),  # stage 0: initial strike (0..33ms)
        _pick_font(55, weight=900),  # stage 1: spring overshoot peak (33..105ms)
        _pick_font(53, weight=900),  # stage 2: crisp settled pop (105ms+)
    ]
    dy_stages = [-3, -7, -5]

    bar_w, bar_h = 1080, 184
    y_top = max(0, min(1920 - bar_h, y_center - bar_h // 2))
    frame_lumas = _probe_frame_luminance_per_frame(ffmpeg_bin, in_mp4, fps, y_top, bar_h, total_frames)

    state_cache: dict[tuple[int, int, int, bool], bytes] = {}
    empty_strip = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0)).tobytes()
    baseline_y = bar_h // 2 + 18
    gap = 20

    for g_idx, grp in enumerate(groups):
        for act_idx in range(len(grp)):
            for stg in (0, 1, 2):
                cur_act_fnt = fnt_pop_stages[stg]
                cur_dy = dy_stages[stg]
                # Measure word advances along shared typographic baseline
                measured = []
                for j_chk, w_obj in enumerate(grp):
                    f_use = cur_act_fnt if j_chk == act_idx else fnt_inact
                    adv = int(round(f_use.getlength(w_obj["word"])))
                    measured.append((w_obj["word"], adv, f_use))
                tot_w = sum(x[1] for x in measured) + gap * max(0, len(measured) - 1)
                start_x = (bar_w - tot_w) // 2

                for is_light_bg in (False, True):
                    shadow_layer = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
                    sd = ImageDraw.Draw(shadow_layer)
                    text_layer = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
                    td = ImageDraw.Draw(text_layer)

                    cx = start_x
                    for j, (w_str, adv, f_use) in enumerate(measured):
                        by = (baseline_y + cur_dy) if j == act_idx else baseline_y
                        if is_light_bg:
                            # Soft warm paper shadow + crisp editorial ink/terracotta contrast
                            sh_col = (20, 20, 19, 62 if j == act_idx else 32)
                            sd.text((cx, by + 4), w_str, font=f_use, fill=sh_col, anchor="ls")
                            col = (206, 84, 48, 255) if j == act_idx else (76, 72, 65, 192)
                            td.text((cx, by), w_str, font=f_use, fill=col, anchor="ls")
                        else:
                            # Rich cinema drop-shadow + subtle 1.5px dark micro-halo for 100% B-Roll legibility without a box!
                            sd.text((cx, by + 5), w_str, font=f_use, fill=(0, 0, 0, 235), anchor="ls")
                            col = (255, 140, 92, 255) if j == act_idx else (244, 241, 235, 222)
                            td.text(
                                (cx, by), w_str, font=f_use, fill=col, anchor="ls",
                                stroke_width=2, stroke_fill=(14, 13, 12, 175),
                            )
                        cx += adv + gap

                    blur_r = 4.5 if is_light_bg else 8.5
                    comp = Image.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_r)), text_layer)
                    state_cache[(g_idx, act_idx, stg, is_light_bg)] = comp.tobytes()

    with tempfile.TemporaryDirectory(prefix="karaoke_", dir=str(VAULT_TMP)) as td_tmp:
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(in_mp4),
            "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{bar_w}x{bar_h}", "-r", str(fps), "-i", "-",
            "-filter_complex", f"[0:v]unsharp=3:3:0.32:3:3:0.0[vsharp];[vsharp][1:v]overlay=0:{y_top}:format=auto[vout]",
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart",
            str(out_mp4),
        ]
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        proc_ov = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc_ov.stdin is not None

        for f_idx in range(total_frames):
            t = f_idx / float(fps)
            is_light = frame_lumas[f_idx] >= 145.0
            chosen_bytes = empty_strip
            for g_idx, grp in enumerate(groups):
                g_start = grp[0]["start"] - 0.04
                g_end = grp[-1]["end"] + 0.16
                if g_start <= t <= g_end:
                    act_j = 0
                    w_start_t = grp[0]["start"]
                    for j, w_obj in enumerate(grp):
                        if t >= w_obj["start"] - 0.025:
                            act_j = j
                            w_start_t = w_obj["start"]
                    dt_word = max(0.0, t - (w_start_t - 0.025))
                    if dt_word < 0.036:
                        stg = 0
                    elif dt_word < 0.115:
                        stg = 1
                    else:
                        stg = 2
                    chosen_bytes = state_cache[(g_idx, act_j, stg, is_light)]
                    break
            proc_ov.stdin.write(chosen_bytes)

        proc_ov.stdin.close()
        err_out = proc_ov.stderr.read() if proc_ov.stderr else b""
        if proc_ov.wait() != 0:
            raise RuntimeError(f"Karaoke overlay failed: {err_out.decode(errors='ignore')[-400:]}")


def _infer_english_visual_queries(topic: str) -> tuple[str, str]:
    """Maps Uzbek/mixed topic text to hyper-specific English `(image_query, broll_query)` preserving brand/person names."""
    lo = (topic or "").lower()
    # Preserve exact proper brands/entities mentioned in the topic!
    entities: list[str] = []
    entity_map = [
        ("tesla", "Tesla"), ("optimus", "Optimus humanoid robot"), ("elon", "Elon Musk"), ("musk", "Elon Musk"),
        ("apple", "Apple"), ("iphone", "iPhone Pro"), ("siri", "Apple Siri AI"), ("openai", "OpenAI Sam Altman"),
        ("chatgpt", "ChatGPT OpenAI"), ("claude", "Anthropic Claude AI"), ("gemini", "Google Gemini AI"),
        ("google", "Google"), ("nvidia", "Nvidia AI GPU chip"), ("deepseek", "DeepSeek AI"),
        ("telegram", "Telegram Pavel Durov"), ("durov", "Pavel Durov Telegram"), ("instagram", "Instagram Reels"),
        ("meta", "Meta Mark Zuckerberg"), ("tiktok", "TikTok app"), ("bitcoin", "Bitcoin crypto"),
        ("samsung", "Samsung Galaxy"), ("xiaomi", "Xiaomi smartphone"), ("byd", "BYD electric car"),
    ]
    for trig, en_lbl in entity_map:
        if trig in lo and en_lbl not in entities:
            entities.append(en_lbl)

    ent_prefix = " ".join(entities[:2]).strip()
    if any(k in lo for k in ("robot", "optimus", "figure", "gumanoid")):
        base_i = f"{ent_prefix} humanoid robot factory 2026".strip()
        base_v = f"{ent_prefix} humanoid robot".strip()
        return (base_i, base_v)
    if any(k in lo for k in ("chip", "protsessor", "gpu", "yarimo'tkazgich", "nvidia")):
        return (f"{ent_prefix} AI microchip semiconductor wafer".strip(), f"{ent_prefix} microchip processor".strip())
    if any(k in lo for k in ("telefon", "smartfon", "iphone", "galaxy", "ilova", "messenjer", "telegram", "insta")):
        return (f"{ent_prefix} smartphone technology press photo".strip(), f"{ent_prefix} smartphone screen".strip())
    if any(k in lo for k in ("kod", "python", "dastur", "vibe", "claude", "gpt", "agent", "bot")):
        return (f"{ent_prefix} AI software developer screen".strip(), f"{ent_prefix} software developer coding".strip())
    if any(k in lo for k in ("sotuv", "biznes", "pul", "daromad", "mijoz", "voronka", "crm", "trillion", "milliard")):
        return (f"{ent_prefix} global tech business headquarters".strip(), f"{ent_prefix} financial stock market".strip())
    if ent_prefix:
        return (f"{ent_prefix} official press photo 2026", f"{ent_prefix} technology")
    return ("artificial intelligence hardware innovation press photo", "microchip processor")


def _extract_first_frame_data_url(mp4_path: str) -> str:
    """Extracts frame 0 of a local B-roll MP4 as a JPEG base64 data URI for seamless slide-in."""
    import base64 as _b64
    try:
        ff = get_ffmpeg_bin()
        proc = subprocess.run(
            [ff, "-y", "-ss", "0.15", "-i", mp4_path, "-frames:v", "1", "-vf", "scale=720:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8,
        )
        if proc.returncode == 0 and len(proc.stdout) > 1500:
            return "data:image/jpeg;base64," + _b64.b64encode(proc.stdout).decode("ascii")
    except Exception:
        pass
    return ""


def _ensure_visual_scene_slots(
    scenes_list: list[dict[str, Any]],
    topic: str,
    video_mode: str = "news",
) -> list[dict[str, Any]]:
    """
    Ensures visual density (`>= 3` photo/video scenes in `news`, `>= 2` in `edu`) BEFORE
    audio beat synchronization so `1 + len(scenes)` stays 100% locked to `len(beat_texts)`!
    """
    if not scenes_list:
        return scenes_list
    fb_img_q, fb_vid_q = _infer_english_visual_queries(topic)
    out_scenes = [dict(s) for s in scenes_list]
    short_head = re.sub(r"\s+", " ", topic).strip()[:36]

    visual_count = sum(1 for s in out_scenes if s.get("type") in ("media_card", "broll_card"))
    min_visuals = 3 if video_mode == "news" else 2

    if visual_count < min_visuals and len(out_scenes) >= 1:
        insert_pos = max(0, len(out_scenes) - 1)
        if visual_count == 0:
            out_scenes.insert(
                0,
                {
                    "type": "media_card",
                    "eyebrow": "REAL KADR · FAKTLAR",
                    "headlineHtml": f"{short_head[:20]}<br><em>asosiy dalil</em>",
                    "captionText": f"{short_head} — real fotolavha",
                    "imageQuery": fb_img_q,
                },
            )
            visual_count += 1
            insert_pos = max(1, len(out_scenes) - 1)
        while visual_count < min_visuals:
            angle_sfx = "closeup hardware" if visual_count % 2 == 1 else "keynote showcase"
            out_scenes.insert(
                insert_pos,
                {
                    "type": "broll_card",
                    "eyebrow": "JONLI LAVHA · HD",
                    "headlineHtml": "Jarayon <em>real</em><br>kadrlar ichida",
                    "captionText": f"{short_head} — amaliy ko‘rinish",
                    "brollQuery": f"{fb_vid_q} {angle_sfx}".strip(),
                },
            )
            visual_count += 1
            insert_pos = min(len(out_scenes) - 1, insert_pos + 1)
    return out_scenes


async def hydrate_topic_media_scenes(
    scenes_list: list[dict[str, Any]],
    topic: str,
    avoid_urls: set[str] | None = None,
    video_mode: str = "news",
) -> list[dict[str, Any]]:
    """
    Hydrates every `media_card` (with Computer-Vision `focalX`/`focalY` subject-zoom lock!) and
    `broll_card` without altering scene count so beat-locked scene cuts stay 100% synchronized!
    """
    if not scenes_list:
        return scenes_list
    used_urls = avoid_urls if avoid_urls is not None else set()
    fb_img_q, fb_vid_q = _infer_english_visual_queries(topic)
    out_scenes = [dict(s) for s in scenes_list]

    hydrated: list[dict[str, Any]] = []
    broll_slot_idx = 0
    img_slot_idx = 0
    angle_variants = ["", "press photo", "technology closeup", "event stage"]

    for sc in out_scenes:
        st = sc.get("type")
        if st == "media_card" and not sc.get("imageDataUrl"):
            iq_base = str(sc.get("imageQuery") or fb_img_q).strip()
            iq = f"{iq_base} {angle_variants[img_slot_idx % len(angle_variants)]}".strip()
            img_slot_idx += 1
            res = await fetch_topic_editorial_image(iq, avoid_urls=used_urls)
            if res and res.get("data_url"):
                sc["imageDataUrl"] = res["data_url"]
                sc["focalX"] = float(res.get("focal_x", 0.50))
                sc["focalY"] = float(res.get("focal_y", 0.44))
                sc["sourceLabel"] = str(res.get("source") or "VIZUAL FAKTLAR · HD").upper()
        elif st == "broll_card" and not sc.get("videoPath"):
            vq = str(sc.get("brollQuery") or fb_vid_q).strip()
            prefer_montage = (broll_slot_idx % 2 == 1)
            broll_slot_idx += 1
            vres = await fetch_topic_broll_video(vq, avoid_urls=used_urls, prefer_press_montage=prefer_montage)
            if vres and vres.get("path") and Path(vres["path"]).exists():
                sc["videoPath"] = vres["path"]
                sc["sourceLabel"] = str(vres.get("source") or "B-ROLL · HD").upper()
                sc["posterDataUrl"] = await asyncio.to_thread(_extract_first_frame_data_url, vres["path"])
            else:
                iq = str(sc.get("imageQuery") or vq or fb_img_q).strip()
                ires = await fetch_topic_editorial_image(iq, avoid_urls=used_urls)
                if ires and ires.get("data_url"):
                    sc["type"] = "media_card"
                    sc["imageDataUrl"] = ires["data_url"]
                    sc["focalX"] = float(ires.get("focal_x", 0.50))
                    sc["focalY"] = float(ires.get("focal_y", 0.44))
                    sc["sourceLabel"] = str(ires.get("source") or "VIZUAL FAKTLAR · HD").upper()
        hydrated.append(sc)
    return hydrated


async def run_one_click_autopilot(
    topic: str,
    keyword: str = "",
    out_dir: Path | None = None,
    voice_profile: str = "uzbek_bilingual_hd",
    with_subtitles: bool = True,
    photo_path: Path | None = None,
    target_duration: float = 15.0,
    video_mode: str = "auto",
    on_step=None,
) -> dict[str, Any]:
    """
    End-to-end Dual-Track Autopilot Conveyor (`v6` Hyper-Visual + Bilingual Uzbek+English Male HD):
      - Auto-resolves `topic="TOP"` / `"AUTO_TOP"` via live `fetch_viral_top_topics(limit=3)`!
      - Track 1 (`video_mode="edu"`): O'rganish / Qo'llanma -> DIYOR.CTR 3D Portrait Hook + rich visuals + Follow-Gate `cta_terminal`
      - Track 2 (`video_mode="news"`): Yangilik va Prosmotr -> Real-Topic HD B-Roll Hook + Dense Exact Photos & Videos + Gate'siz `follow_outro`!
      - Default Voice: `uzbek_bilingual_hd` (`uz-UZ-SardorNeural` 115.9Hz + acoustic twin `en-US-ChristopherNeural` 115.5Hz — 100% crisp English & Uzbek, `-14.5 LUFS`)!
    """
    async def _emit(msg: str) -> None:
        if on_step is not None:
            try:
                await on_step(msg)
            except Exception:
                pass

    t0 = time.time()
    eff_topic = (topic or "").strip()
    if eff_topic.upper() in ("TOP", "AUTO_TOP", "TREND", ""):
        await _emit("🔥 <b>1.5-qadam:</b> Dunyo bo‘yicha TOPga chiqadigan eng qaynoq viral mavzu qidirilmoqda...")
        top_list = await fetch_viral_top_topics(limit=3)
        if top_list:
            eff_topic = top_list[0]["uz_topic"]
            if video_mode == "auto":
                video_mode = top_list[0].get("mode", "news")
        else:
            eff_topic = "Tesla Optimus gumanoid robotlari fabrikalarda ish boshladi: 2026 real kadrlar"

    await _emit("🧠 <b>2-qadam:</b> Jonli internet faktlari va AI-rejissyor orqali ssenariy tuzilmoqda...")
    bp = await generate_dynamic_ai_blueprint(eff_topic, keyword, target_duration=target_duration, video_mode=video_mode)
    mode = bp.get("video_mode", "edu")
    kw = bp["keyword"]
    is_long = bool(bp.get("is_long"))
    ts = int(time.time())
    portrait = photo_path if (photo_path and photo_path.exists()) else DEFAULT_PORTRAIT

    if out_dir is None:
        out_dir = Path("/home/user/.cache/diyor_vault/media/custom_renders") / f"autopilot_{mode}_{kw.lower()}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize Beat-Locked Bilingual Uzbek + English Male Studio Voiceover (`uzbek_bilingual_hd` default!)
    await _emit("🎙 <b>3-qadam:</b> Sahnalarga 100% sinxron O‘zbek + Ingliz Bilingual HD erkak ovozi sintez qilinmoqda...")
    vo_wav = out_dir / f"00_voice_{voice_profile}.wav"
    beat_texts = bp.get("beat_texts") or []
    tts_meta = await synthesize_pro_uzbek_voice(
        bp["voice_script"], vo_wav, profile=voice_profile, speed=1.0, beat_texts=beat_texts
    )
    min_floor = max(float(target_duration or 14.0), 40.0) if is_long else max(float(target_duration or 13.0), 10.5)
    vo_dur = max(min_floor, round(float(tts_meta["duration"]) + 0.55, 2))
    beat_timings = tts_meta.get("beat_timings") or []

    # 2. Compute exact beat-locked `hook_dur` + scene durations so EVERY visual card cuts at the exact spoken sentence!
    ffmpeg_bin = get_ffmpeg_bin()
    vo_16k = out_dir / "tmp_vo_16k.wav"
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(vo_wav), "-ar", "16000", "-ac", "1", str(vo_16k)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )

    cover_4x5_png = out_dir / f"01_KARUSEL_muqova_{kw.lower()}_4x5.png"
    ai_scenes_raw = bp.get("scenes") or []
    if beat_timings and len(beat_timings) == 1 + len(ai_scenes_raw):
        hook_dur = max(2.2, round(float(beat_timings[0]["end"]), 2))
    else:
        hook_dur = 3.2 if is_long else 2.8
    rem_dur = max(36.8 if is_long else 7.5, round(vo_dur - hook_dur, 2))
    used_media_urls: set[str] = set()

    async def _fast_whisper_or_none(p_wav: Path):
        if tts_meta.get("acoustic_words"):
            return None
        try:
            return await asyncio.wait_for(transcribe_uzbek_via_modal(p_wav), timeout=10.0)
        except Exception:
            return None

    if mode == "news":
        await _emit("🎞 <b>4-qadam:</b> Mavzuga 100% mos Real-Kadr Hook, HD fotolar va B-Roll videolar yig‘ilmoqda...")
        hook_img_res = await fetch_topic_editorial_image(bp.get("hookImageQuery") or bp["topic"], avoid_urls=used_media_urls)
        hook_broll_res = await fetch_topic_broll_video(
            bp.get("hookBrollQuery") or bp["topic"],
            avoid_urls=used_media_urls,
            portrait_hook=True,
        )
        hook_mp4_p = Path(hook_broll_res["path"]) if (hook_broll_res and hook_broll_res.get("path")) else None
        hook_img_du = (hook_img_res or {}).get("data_url", "")

        whisper_task = asyncio.create_task(_fast_whisper_or_none(vo_16k))
        media_task = asyncio.create_task(
            hydrate_topic_media_scenes(bp.get("scenes") or [], bp["topic"], avoid_urls=used_media_urls, video_mode=mode)
        )
        await render_news_cover_slide(hook_img_du, cover_4x5_png, bp["hook_config"])
        hook_frames = await render_news_broll_hook_frames(
            ffmpeg_bin, hook_mp4_p, hook_img_du, bp["hook_config"], duration=hook_dur, fps=30
        )
        w_res, hydrated_scenes = await asyncio.gather(whisper_task, media_task)
    else:
        await _emit("🖼 <b>4-qadam:</b> 4:5 DIYOR.CTR muqova, 3D portret hook va mavzuga mos kadrlari chizilmoqda...")
        whisper_task = asyncio.create_task(_fast_whisper_or_none(vo_16k))
        media_task = asyncio.create_task(
            hydrate_topic_media_scenes(bp.get("scenes") or [], bp["topic"], avoid_urls=used_media_urls, video_mode=mode)
        )
        await render_brand_photo_slide(portrait, cover_4x5_png, config=bp["hook_config"], aspect="4:5")
        hook_frames = await render_brand_photo_parallax_frames(
            portrait, config=bp["hook_config"], aspect="9:16", duration=hook_dur, fps=30
        )
        w_res, hydrated_scenes = await asyncio.gather(whisper_task, media_task)
    vo_16k.unlink(missing_ok=True)
    if hydrated_scenes:
        bp["scenes"] = hydrated_scenes

    # 3. Render 9:16 Hook + Bespoke Multi-Scene Story + Clawd
    await _emit("🎬 <b>5-qadam:</b> 9:16 sahnalar va HD B-Roll lavhalar montaj qilinmoqda...")
    raw_mp4 = out_dir / "tmp_raw_reel.mp4"

    ai_scenes = bp.get("scenes")
    if isinstance(ai_scenes, list) and len(ai_scenes) >= 2:
        if beat_timings and len(beat_timings) == 1 + len(ai_scenes):
            # Sample-exact Beat-Locked Scene Durations: every card stays on screen for the exact sentence spoken about it!
            scenes_payload = []
            prev_cut = hook_dur
            for idx_s, sc in enumerate(ai_scenes):
                sc_copy = dict(sc)
                if idx_s == len(ai_scenes) - 1:
                    d_s = max(2.2, round(vo_dur - prev_cut, 2))
                else:
                    target_cut = max(prev_cut + 2.0, round(float(beat_timings[idx_s + 1]["end"]), 2))
                    d_s = round(target_cut - prev_cut, 2)
                    prev_cut = round(prev_cut + d_s, 2)
                sc_copy["duration"] = d_s
                scenes_payload.append(sc_copy)
        else:
            weights: list[float] = []
            for sc in ai_scenes:
                st_t = sc.get("type", "hook_stat")
                if st_t in ("news_radar", "pipeline_dm", "scorecard_bars", "vs_comparison", "broll_card", "media_card"):
                    weights.append(1.22)
                elif st_t in ("cta_terminal", "follow_outro"):
                    weights.append(0.88)
                else:
                    weights.append(1.0)
            w_sum = sum(weights) or 1.0
            scenes_payload = []
            used = 0.0
            for idx_s, sc in enumerate(ai_scenes):
                sc_copy = dict(sc)
                if idx_s == len(ai_scenes) - 1:
                    sc_copy["duration"] = max(2.5, round(rem_dur - used, 2))
                else:
                    d_s = max(2.6, round(rem_dur * (weights[idx_s] / w_sum), 2))
                    sc_copy["duration"] = d_s
                    used += d_s
                scenes_payload.append(sc_copy)
    else:
        scenes_payload = bp.get("scenes") or []

    reel_meta = await render_diyor_motion_mp4(
        {
            "aspect": "9:16",
            "theme": bp.get("theme", "lotion"),
            "topicTag": ("yangiliklar · @diyor.ctr" if mode == "news" else f"{kw.lower()} · @diyor.ctr"),
            "handle": "@DIYOR.CTR",
            "scenes": scenes_payload,
        },
        raw_mp4,
        fps=30,
        with_clawd=True,
        prepend_rgb_frames=hook_frames,
    )

    # 4. Mux Toshkent Diktor HD Voice + Ducked FX Bed (-14.5 LUFS)
    await _emit("🔤 <b>6-qadam:</b> -14.5 LUFS sof o‘zbek ovozi va Kinetic Pop subtitrlar yozilmoqda...")
    voiced_mp4 = out_dir / f"tmp_voiced_{kw.lower()}.mp4"
    await asyncio.to_thread(
        mux_navoiy_voice_onto_mp4,
        raw_mp4,
        vo_wav,
        voiced_mp4,
        reel_meta.get("cuts", []),
        float(reel_meta["duration"]),
    )
    raw_mp4.unlink(missing_ok=True)

    # 5. Burn 100% Harfma-Harf Millisecond-Exact Kinetic Pop Subtitles into lower safe zone (`y=1642`)!
    final_reel_mp4 = out_dir / f"02_REELS_{mode}_{kw.lower()}_diyor_ctr_9x16.mp4"
    whisper_words = (w_res or {}).get("words") or tts_meta.get("acoustic_words") or []
    if tts_meta.get("exact_word_boundaries") and tts_meta.get("acoustic_words"):
        aligned_words = [
            {
                "word": str(w["word"]).strip(),
                "start": round(float(w["start"]), 3),
                "end": round(float(w["end"]), 3),
            }
            for w in tts_meta["acoustic_words"]
            if str(w.get("word") or "").strip()
        ]
    else:
        aligned_words = align_clean_uzbek_words(bp["display_words_text"], whisper_words, float(tts_meta["duration"]))

    if with_subtitles:
        await asyncio.to_thread(render_karaoke_overlay_onto_mp4, voiced_mp4, final_reel_mp4, aligned_words, 30, 1642)
        voiced_mp4.unlink(missing_ok=True)
    else:
        voiced_mp4.rename(final_reel_mp4)

    caption_file = out_dir / "INSTAGRAM_CAPTION.txt"
    caption_file.write_text(bp["caption"], encoding="utf-8")

    critic_audit = {
        "no_dangling_cliffhanger": not bool(
            re.search(r"\b(aytib beraman|batafsil bilib olamiz|keling ko['‘]?ramiz)\b", bp["voice_script"], flags=re.IGNORECASE)
        ),
        "beat_scene_sync_count": len(beat_timings),
        "exact_harfma_harf_subtitles": bool(tts_meta.get("exact_word_boundaries")) and len(aligned_words) >= 6,
        "smart_focal_zoom_scenes": sum(
            1 for s in bp.get("reel_spec", {}).get("scenes", []) if ("focalX" in s or s.get("type") in ("media_card", "broll_card"))
        ),
    }

    return {
        "ok": True,
        "video_mode": mode,
        "topic": bp["topic"],
        "keyword": kw,
        "behindWord": bp["behindWord"],
        "reel_mp4": str(final_reel_mp4),
        "cover_png": str(cover_4x5_png),
        "voice_wav": str(vo_wav),
        "caption": bp["caption"],
        "voice_script": bp["voice_script"],
        "tts": tts_meta,
        "whisper_words_count": len(whisper_words),
        "aligned_words": aligned_words,
        "critic_audit": critic_audit,
        "duration": reel_meta["duration"],
        "elapsed_sec": round(time.time() - t0, 2),
    }
