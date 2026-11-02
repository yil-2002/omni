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

from PIL import Image, ImageDraw, ImageFont

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if "/home/user/tashqi_xotira" not in sys.path:
    sys.path.insert(0, "/home/user/tashqi_xotira")

from cloud_render_bridge import transcribe_uzbek_via_modal  # noqa: E402
from motion_engine import VAULT_TMP, get_ffmpeg_bin, render_diyor_motion_mp4  # noqa: E402
from photo_brand_engine import render_brand_photo_parallax_frames, render_brand_photo_slide  # noqa: E402
from uzbek_male_voice_engine import mux_navoiy_voice_onto_mp4, synthesize_pro_uzbek_voice  # noqa: E402
from uztts_normalize import normalize_uzbek_for_tts  # noqa: E402

import html as _html
import json
import random
import urllib.parse
import aiohttp

DEFAULT_PORTRAIT = Path("/home/user/uploads/IMG_2860.jpeg")
BOLD_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/home/user/claude-techbrief/shared/fonts/BebasNeue-Regular.ttf",
]


def _pick_font(size: int) -> ImageFont.FreeTypeFont:
    for fp in BOLD_FONT_CANDIDATES:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


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


async def generate_dynamic_ai_blueprint(topic: str, keyword: str = "SKILL", target_duration: float = 12.0) -> dict[str, Any]:
    """
    TRUE BESPOKE AI REELS DIRECTOR:
    Every single topic produces a 100% unique Uzbek script, fresh hook, custom callouts, rotating theme
    (`lotion` vs `warm`), and topic-matched dynamic scene sequence from 7 scene archetypes!
    """
    clean_topic = re.sub(r"\s+", " ", (topic or "Sun'iy intellekt yangiliklari").strip())
    raw_kw = re.sub(r"[^A-Za-z0-9_]", "", (keyword or "").upper())[:12]
    dur_f = float(target_duration or 12.0)
    is_long = dur_f >= 25.0

    facts = await _fetch_live_topic_facts(clean_topic)
    target_words = "88 dan 108 tagacha so'z (taxminan 42-46 soniya)" if is_long else "26 dan 36 tagacha so'z (taxminan 11-15 soniya)"
    n_body_scenes = "5 yoki 6 ta" if is_long else "2 yoki 3 ta"

    angles = [
        "1) Yangilik va kutilmagan raqamlar radari (news_radar + hook_stat)",
        "2) Ko'pchilik qiladigan eski xato vs Yangi aqlli yondashuv (vs_comparison + pipeline_dm)",
        "3) Real amaliy mexanizm va natijalar tahlili (pipeline_dm + scorecard_bars)",
        "4) Chuqur texnik yoki strategik sirlar ochilishi (hook_stat + vs_comparison + scorecard_bars)",
    ]
    chosen_angle = random.choice(angles)

    sys_p = (
        "Sen @diyor.ctr Instagram sahifasining bosh kreativ ssenaristi va motion-rejissyorisan. "
        "Vazifang — berilgan MAVZU bo'yicha 100% ORIGINAL, TAKRORLANMAS, Fakt va Raqamlarga boy JSON blueprint yaratish!\n"
        "QAT'IY QOIDALAR:\n"
        "1. QAT'IY TAQIQ: Hech qachon '10 kishilik jamoa emas', 'Eski usulda vaqt yo'qotmang', '48 soatda tayyor mahsulot', 'AI IMPERIYA' kabi shablon jumlalarni ISHLATMA (faqat foydalanuvchi aynan shu so'zni so'ragandagina ruxsat)!\n"
        "2. Har bir video MAVZUGA 100% MOS, tirik, ravon O'zbek tilida (lotin yozuvida) bo'lsin.\n"
        "3. `headlineHtml` ichida Fraunces shrifti chiroyli turishi uchun qatorni mantiqiy joydan `<br>` bilan bo'l va eng kuchli 1-2 so'zni `<em>...</em>` ichiga ol.\n"
        "4. Sahna turlari (`scenes` ro'yxati oxirida har doim `cta_terminal` bo'lsin, undan oldin mavzuga eng moslarini tanla va aralashtir):\n"
        "   - `news_radar`: yangiliklar, 3 ta fakt, trendlar uchun -> `{\"type\":\"news_radar\",\"eyebrow\":\"...\",\"headlineHtml\":\"...\",\"items\":[{\"badge\":\"FAKT · 01\",\"title\":\"...\",\"source\":\"...\"}, ...3 ta]}`\n"
        "   - `vs_comparison`: eski xato vs yangi yechim -> `{\"type\":\"vs_comparison\",\"eyebrow\":\"...\",\"headlineHtml\":\"...\",\"oldTitle\":\"...\",\"oldPoints\":[\"...\",\"...\"],\"newTitle\":\"...\",\"newPoints\":[\"...\",\"...\"]}`\n"
        "   - `hook_stat`: kuchli statistika -> `{\"type\":\"hook_stat\",\"eyebrow\":\"...\",\"headlineHtml\":\"...\",\"subtext\":\"...\",\"statLabel\":\"...\",\"statValue\":87,\"statSuffix\":\"%\",\"barPercent\":87}`\n"
        "   - `pipeline_dm`: 3 qadamli tizim/qo'llanma -> `{\"type\":\"pipeline_dm\",\"eyebrow\":\"...\",\"headlineHtml\":\"...\",\"steps\":[{\"tag\":\"01 · QADAM\",\"title\":\"...\",\"meta\":\"...\"}, ...3 ta]}`\n"
        "   - `scorecard_bars`: ko'rsatkichlar tahlili -> `{\"type\":\"scorecard_bars\",\"eyebrow\":\"...\",\"headlineHtml\":\"...\",\"ringScore\":96,\"metrics\":[{\"label\":\"...\",\"val\":85,\"suffix\":\"%\",\"pct\":85}, ...3 ta]}`\n"
        "   - `code_architecture`: FAQAT dasturlash, AI prompt, bot yoki texnik mavzu bo'lsa ishlat -> `{\"type\":\"code_architecture\",\"eyebrow\":\"...\",\"headlineHtml\":\"...\",\"subtext\":\"...\",\"fileName\":\"agent.py\",\"badge\":\"AI\",\"codeLines\":[\"...\", ...4-5 qator]}`\n"
        "   - `cta_terminal` (eng oxirgi sahna): `{\"type\":\"cta_terminal\",\"eyebrow\":\"BEPUL QO'LLANMA · DIRECT\",\"headlineHtml\":\"Izohda <em>«KALIT»</em><br>deb yozing\",\"subtext\":\"...\",\"keyword\":\"KALIT\"}`\n"
        "5. FAQAT TOZA JSON QAYTAR (hech qanday izohsiz!):"
    )

    usr_p = (
        f"MAVZU: {clean_topic}\n"
        f"DAVOMIYLIK REJIMI: {'UZUN 44 SONIYALIK (6 ta sahna: 5 ta asosiy sahna + oxirida 1 ta cta_terminal)' if is_long else 'QISQA DINAMIK REEL (3 ta sahna: 2 ta asosiy sahna + oxirida 1 ta cta_terminal)'}\n"
        f"DIKTOR MATNI HAJMI (`display_words_text`): {target_words}\n"
        f"TAVSIYA ETILGAN KREATIV BURCHAK: {chosen_angle}\n"
        f"FOYDALANUVCHI KALIT SO'ZI: {raw_kw if (raw_kw and raw_kw != 'SKILL') else 'Mavzuga mos qisqa soz tanla (masalan NEWS, SOTUV, AGENT, TREND, KOD)'}\n"
        + (f"\nINTERNETDAN TOPILGAN REAL FAKTLAR:\n{facts}\n" if facts else "")
        + "\nQuyidagi JSON strukturasini to'liq to'ldirib qaytar:\n"
        '{\n'
        '  "theme": "lotion yoki warm",\n'
        '  "keyword": "MAVZUGA_MOS_SOZ",\n'
        '  "behindWord": "2 SOZ <=12 HARF",\n'
        '  "kicker": "QISQA RUBRIKA",\n'
        '  "hookHeadlineHtml": "Portret usti <em>kuchli sarlavha</em>",\n'
        '  "hookSubtext": "1 gaplik aniq izoh",\n'
        '  "callouts": [{"label": "FAKT", "value": "..."}, {"label": "NATIJA", "value": "..."}],\n'
        '  "display_words_text": "Diktor o\'qiydigan to\'liq, ravon, qiziqarli O\'zbekcha matn (oxirida izohda kalit so\'zni yozishga chaqirsin)",\n'
        f'  "scenes": [ ... {n_body_scenes} asosiy sahna va eng oxirida cta_terminal ... ],\n'
        '  "caption": "Instagram post uchun to\'liq foydali matn va @diyor.ctr obuna + izoh CTA"\n'
        '}'
    )

    raw_ai = await _call_frontier_director_llm(sys_p, usr_p)
    parsed = _extract_json_dict(raw_ai)

    if parsed and parsed.get("display_words_text") and isinstance(parsed.get("scenes"), list) and len(parsed["scenes"]) >= 2:
        kw = re.sub(r"[^A-Za-z0-9_]", "", str((raw_kw if (raw_kw and raw_kw != "SKILL") else parsed.get("keyword")) or "TIZIM").upper())[:12] or "TIZIM"
        behind = str(parsed.get("behindWord") or clean_topic.split()[0]).upper()[:13]
        lo_t = clean_topic.lower()
        if any(w in lo_t for w in ("yangilik", "kod", "python", "ai ", "model", "agent", "texno")):
            theme = "lotion"
        elif any(w in lo_t for w in ("sotuv", "biznes", "mijoz", "pul", "psixolog", "brend")):
            theme = "warm"
        else:
            theme = "warm" if str(parsed.get("theme", "")).lower() == "warm" else "lotion"
        disp_txt = re.sub(r"\s+", " ", str(parsed["display_words_text"]).strip())
        vo_script = normalize_uzbek_for_tts(disp_txt)
        callouts = parsed.get("callouts") if isinstance(parsed.get("callouts"), list) and len(parsed["callouts"]) >= 2 else [
            {"label": "MAVZU", "value": behind},
            {"label": "DIRECT", "value": f"«{kw}»"},
        ]
        scenes_list = []
        for sc in parsed["scenes"][:7]:
            if isinstance(sc, dict) and sc.get("type"):
                if sc["type"] == "cta_terminal":
                    sc["keyword"] = kw
                scenes_list.append(sc)
        if not any(s.get("type") == "cta_terminal" for s in scenes_list):
            scenes_list.append({
                "type": "cta_terminal",
                "eyebrow": "BEPUL FOYDALI MATERIAL · DIRECT",
                "headlineHtml": f"Izohda <em>«{kw}»</em><br>deb yozing",
                "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — 3 soniyada Direct’ga yuboriladi!",
                "keyword": kw,
            })
        return {
            "topic": clean_topic,
            "keyword": kw,
            "theme": theme,
            "is_long": is_long,
            "target_duration": dur_f,
            "behindWord": behind,
            "voice_script": vo_script,
            "display_words_text": disp_txt,
            "hook_config": {
                "behindWord": behind,
                "kicker": str(parsed.get("kicker") or f"TAHLIL · {kw}")[:32],
                "headlineHtml": str(parsed.get("hookHeadlineHtml") or f"{clean_topic[:28]} <em>tahlili</em>"),
                "subtext": str(parsed.get("hookSubtext") or f"@diyor.ctr · {clean_topic[:55]}"),
                "callouts": callouts[:2],
                "topicTag": f"{kw.lower()} · @diyor.ctr",
                "handle": "@DIYOR.CTR",
            },
            "scenes": scenes_list,
            "caption": str(parsed.get("caption") or f"🔥 {clean_topic}\n\nObuna bo‘ling (@diyor.ctr) va izohda «{kw}» deb yozing!"),
        }

    # Resilient offline fallback if external LLM is unreachable (still adapts scenes & theme!)
    fb = build_autopilot_blueprint(clean_topic, raw_kw or "TIZIM", target_duration=dur_f)
    return fb


def build_autopilot_blueprint(topic: str, keyword: str = "SKILL", target_duration: float = 10.0) -> dict[str, Any]:
    """Offline deterministic fallback blueprint if network LLM is unreachable."""
    clean_topic = re.sub(r"\s+", " ", (topic or "Sun'iy intellekt tahlili").strip())
    kw = re.sub(r"[^A-Za-z0-9_]", "", (keyword or "TIZIM").upper())[:14] or "TIZIM"
    is_long = float(target_duration or 10.0) >= 25.0

    # Extract crisp 1-2 word 3D behindWord (<= 13 chars)
    words = [w for w in re.split(r"[\s—–\-+/(),.]+", clean_topic) if len(w) >= 2]
    stop = {"VA", "BILAN", "UCHUN", "ORQALI", "QANDAY", "QURISH", "YANGI", "BIR", "KISHILIK"}
    key_words = [w.upper() for w in words if w.upper() not in stop]
    if "imperiya" in clean_topic.lower():
        behind = "AI IMPERIYA"
    elif len(key_words) >= 2 and len(f"{key_words[0]} {key_words[1]}") <= 13:
        behind = f"{key_words[0]} {key_words[1]}"
    elif key_words:
        behind = f"AI {key_words[0]}"[:13] if key_words[0] != "AI" and len(key_words[0]) <= 9 else key_words[0][:13]
    else:
        behind = "AI TIZIM"

    if is_long:
        # Full 40–46 second 6-chapter storytelling script (spoken naturally in ~42-45s by Kino Bariton HD)
        if "imperiya" in clean_topic.lower() or "vibe" in clean_topic.lower():
            voice_script = (
                f"Ko'pchilik biznes boshlash uchun o'n kishilik jamoa va minglab dollar kerak deb o'ylaydi. "
                f"Aslida esa bugun bitta inson va Klod sun'iy intellekti butun boshli agentlik o'rnini bosmoqda! "
                f"Birinchi qadam: g'oya va ssenariyni sun'iy intellekt soniyalar ichida tayyorlaydi. "
                f"Ikkinchi qadam: Vayb Koding va Klod Skills orqali dasturchisiz qirq sakkiz soatda tayyor mahsulot va sayt ishga tushadi. "
                f"Uchinchi qadam: Aqlli Follov Geyt tizimi har bir izoh yozgan mijozga uch soniyada javob qaytaradi. "
                f"Natijada xarajatlar to'qson ikki foizga qisqarib, tizim siz uxlayotgan paytda ham yigirma to'rt soat sotuv qiladi! "
                f"To'liq bepul qo'llanma va tayyor arxitekturani olish uchun hoziroq izohda {kw} deb yozing!"
            )
            display_words_text = (
                f"Ko‘pchilik biznes uchun 10 kishilik jamoa va minglab dollar kerak deb o‘ylaydi. "
                f"Aslida esa 1 kishi va Claude AI butun boshli agentlik o‘rnini bosmoqda! "
                f"1-qadam: g‘oya va ssenariyni sun’iy intellekt soniyalar ichida tayyorlaydi. "
                f"2-qadam: Vibe Coding va Claude Skills orqali dasturchisiz 48 soatda tayyor mahsulot ishga tushadi. "
                f"3-qadam: Aqlli Follow-Gate tizimi har bir izoh yozgan mijozga 3 soniyada javob qaytaradi. "
                f"Natijada xarajatlar 92% qisqarib, tizim uxlayotgan paytingizda ham 24/7 sotuv qiladi! "
                f"To‘liq bepul qo‘llanma va tayyor arxitektura uchun hoziroq izohda «{kw}» deb yozing!"
            )
            hook_head = "Dasturchisiz <em>AI-imperiya</em> quring"
            hook_sub = "Claude Skills + Vibe Coding · 1 kishi bilan 24/7 ishlovchi to‘liq avtonom tizim."
            scene1_head = "10 kishilik jamoa emas —<br><em>1 kishi + Claude</em>"
            scene1_sub = "An’anaviy agentlik xarajatlarisiz to‘liq avtonom raqamli mahsulot va sotuv tizimi."
            stat_val, stat_lbl = 92, "JAMOA XARAJATI TEJALISHI"
            c1, c2 = {"label": "JAMOA", "value": "1 kishi + AI"}, {"label": "FORMAT", "value": "24/7 Avtopilot"}
        else:
            short_t = clean_topic[:44]
            t_parts = short_t.split()
            mid = max(1, len(t_parts) // 2)
            l1 = " ".join(t_parts[:mid])
            l2 = " ".join(t_parts[mid:]) or "24/7 Avtopilotda"
            voice_script = (
                f"Eski usulda soatlab vaqt yo'qotishni to'xtating — {clean_topic} endi to'liq avtopilotda ishlaydi! "
                f"Bugun bitta mutaxassis va Klod sun'iy intellekti o'n kishilik bo'lim qiladigan ishni avtonom tarzda bajarmoqda. "
                f"Birinchi bosqichda sun'iy intellekt mijoz ehtiyojini tahlil qiladi va aniq yechim tuzadi. "
                f"Ikkinchi bosqichda Klod kod va dizayn arxitekturasini inson aralashuvisiz ishga tushiradi. "
                f"Uchinchi bosqichda esa Aqlli Follov Geyt botimiz har bir murojaatni uch soniya ichida sotuvga aylantiradi. "
                f"Natijada samaradorlik to'qson to'rt foizga oshib, tizim kechayu kunduz to'xtovsiz ishlaydi! "
                f"Tayyor shablon va qadamma-qadam qo'llanmani olish uchun izohda {kw} deb yozing!"
            )
            display_words_text = (
                f"Eski usulda vaqt yo‘qotishni to‘xtating — {short_t} endi to‘liq avtopilotda ishlaydi! "
                f"Bugun 1 mutaxassis va Claude AI 10 kishilik bo‘lim ishini avtonom bajarmoqda. "
                f"1-bosqichda sun’iy intellekt mijoz ehtiyojini tahlil qiladi va aniq yechim tuzadi. "
                f"2-bosqichda Claude kod va dizayn arxitekturasini inson aralashuvisiz ishga tushiradi. "
                f"3-bosqichda Aqlli Follow-Gate bot har bir murojaatni 3 soniyada sotuvga aylantiradi. "
                f"Natijada samaradorlik 94% oshib, tizim kechayu kunduz 24/7 to‘xtovsiz ishlaydi! "
                f"Tayyor shablon va qo‘llanmani olish uchun izohda «{kw}» deb yozing!"
            )
            hook_head = f"{l1} <em>{l2}</em>"
            hook_sub = "@diyor.ctr · Claude AI orqali biznesni 24/7 to‘liq avtomatlashtirish arxitekturasi."
            scene1_head = f"{l1}<br><em>{l2}</em>"
            scene1_sub = "Inson omilisiz kechayu kunduz ishlovchi sun’iy intellekt va avto-sotuv zanjiri."
            stat_val, stat_lbl = 94, "AVTOMATLASHTIRISH SAMARASI"
            c1, c2 = {"label": "TIZIM", "value": "Claude 24/7"}, {"label": "KALIT SO‘Z", "value": f"«{kw}» Direct"}
    else:
        # Short punchy 8-12s Reel script
        if "imperiya" in clean_topic.lower() or "vibe" in clean_topic.lower():
            voice_script = (
                f"O'n kishilik jamoa emas, bir kishi va Klod! "
                f"Qirq sakkiz soatda tayyor mahsulot va avto-sotuv. "
                f"Bepul qo'llanma uchun izohda {kw} deb yozing!"
            )
            display_words_text = (
                f"10 kishilik jamoa emas — 1 kishi va Claude! "
                f"48 soatda tayyor mahsulot va avto-sotuv. "
                f"Bepul qo‘llanma uchun izohda «{kw}» deb yozing!"
            )
            hook_head = "Dasturchisiz <em>AI-biznes</em> quring"
            hook_sub = "Claude Skills + Vibe Coding orqali 48 soatda g‘oyadan tayyor mahsulotgacha."
            scene1_head = "10 kishilik jamoa emas —<br><em>1 kishi + Claude</em>"
            scene1_sub = "Vibe Coding va Claude Skills yordamida 48 soatda tayyor mahsulot va avto-sotuv."
            stat_val, stat_lbl = 92, "JAMOA XARAJATI TEJALISHI"
            c1, c2 = {"label": "JAMOA", "value": "1 kishi + AI"}, {"label": "NATIJA", "value": "48 soatda MVP"}
        else:
            short_t = clean_topic[:44]
            voice_script = (
                f"Eski usulda vaqt yo'qotmang — {clean_topic} endi to'liq avtopilotda! "
                f"Klod sun'iy intellekti siz uchun yigirma to'rt soat ishlaydi. "
                f"Tayyor tizimni olish uchun izohda {kw} deb yozing!"
            )
            display_words_text = (
                f"Eski usulda vaqt yo‘qotmang — {short_t} endi avtopilotda! "
                f"Claude AI siz uchun 24/7 ishlaydi. "
                f"Tayyor tizim uchun izohda «{kw}» deb yozing!"
            )
            t_parts = short_t.split()
            mid = max(1, len(t_parts) // 2)
            l1 = " ".join(t_parts[:mid])
            l2 = " ".join(t_parts[mid:]) or "24/7 Avtopilotda"
            hook_head = f"{l1} <em>{l2}</em>"
            hook_sub = "@diyor.ctr · Claude AI orqali biznesni to‘liq avtomatlashtirish tizimi."
            scene1_head = f"{l1}<br><em>{l2}</em>"
            scene1_sub = "Inson omilisiz 24/7 ishlovchi sun’iy intellekt va avto-sotuv zanjiri."
            stat_val, stat_lbl = 94, "AVTOMATLASHTIRISH SAMARASI"
            c1, c2 = {"label": "TIZIM", "value": "Claude 24/7"}, {"label": "KALIT SO‘Z", "value": f"«{kw}» Direct"}

    caption = (
        f"🚀 {clean_topic} — endi 1 kishi va Claude AI bilan!\n\n"
        f"Ko‘pchilik hali ham katta jamoa va uzoq vaqt sarflayotganda, sun’iy intellekt tizimlari "
        f"barcha jarayonni 24/7 avtopilotga o‘tkazmoqda.\n\n"
        f"👇 Bepul qadamma-qadam qo‘llanma va shablonlarni olish uchun:\n"
        f"1️⃣ @diyor.ctr sahifasiga obuna bo‘ling;\n"
        f"2️⃣ Izohda «{kw}» deb yozing — Aqlli Follow-Gate bot 3 soniyada Direct’ingizga yuboradi!"
    )

    return {
        "topic": clean_topic,
        "keyword": kw,
        "is_long": is_long,
        "target_duration": float(target_duration or 10.0),
        "behindWord": behind,
        "voice_script": voice_script,
        "display_words_text": display_words_text,
        "hook_config": {
            "behindWord": behind,
            "kicker": f"AI AVTOPILOT · {kw}",
            "headlineHtml": hook_head,
            "subtext": hook_sub,
            "callouts": [c1, c2],
            "topicTag": f"ai · {kw.lower()}",
            "handle": "@DIYOR.CTR",
        },
        "scene1": {
            "eyebrow": f"01 · MUAMMO VA YECHIM",
            "headlineHtml": scene1_head,
            "subtext": scene1_sub,
            "statLabel": stat_lbl,
            "statValue": stat_val,
        },
        "caption": caption,
    }


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


def render_karaoke_overlay_onto_mp4(
    in_mp4: Path,
    out_mp4: Path,
    word_timings: list[dict[str, Any]],
    fps: int = 30,
    y_center: int = 1638,
) -> None:
    """
    Renders clean, borderless floating Kinetic Karaoke Subtitles (`3` words per chunk, ZERO dark box /
    ZERO `qora xoshiya` behind the text!) into the lower Reels safe-zone (`y=1638` on `1080×1920`).
    Automatically adapts text ink per frame (`#FAF9F5` + `#F0835E` on dark studio portrait; `#141413` +
    `#D97757` on `#FAF9F5` Claude TechBrief paper) so zero faces, `DIYOR.CTR`, or HUDs are covered.
    """
    if not word_timings:
        out_mp4.write_bytes(in_mp4.read_bytes())
        return

    ffmpeg_bin = get_ffmpeg_bin()
    proc = subprocess.run([ffmpeg_bin, "-i", str(in_mp4)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    v_dur = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 10.0
    total_frames = max(1, int(round(v_dur * fps)))

    # Group into punchy 3-word karaoke phrases
    groups: list[list[dict[str, Any]]] = []
    chunk_sz = 3
    for i in range(0, len(word_timings), chunk_sz):
        groups.append(word_timings[i : i + chunk_sz])

    fnt = _pick_font(44)
    fnt_act = _pick_font(49)
    bar_w, bar_h = 1080, 148
    y_top = max(0, min(1920 - bar_h, y_center - bar_h // 2))
    frame_lumas = _probe_frame_luminance_per_frame(ffmpeg_bin, in_mp4, fps, y_top, bar_h, total_frames)

    # Pre-render unique `(group_idx, active_word_idx, is_light_bg)` RGBA strips (pure floating typography + kinetic pop, ZERO dark box!)
    state_cache: dict[tuple[int, int, bool], bytes] = {}
    empty_strip = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0)).tobytes()

    for g_idx, grp in enumerate(groups):
        for act_idx in range(len(grp)):
            for is_light_bg in (False, True):
                im = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                word_boxes = []
                gap = 20
                for j_chk, w_obj in enumerate(grp):
                    cur_f = fnt_act if j_chk == act_idx else fnt
                    bb = cur_f.getbbox(w_obj["word"])
                    ww, wh = bb[2] - bb[0], bb[3] - bb[1]
                    word_boxes.append((w_obj["word"], ww, wh, bb[0], bb[1], cur_f))

                tot_text_w = sum(x[1] for x in word_boxes) + gap * (len(word_boxes) - 1)
                cx = (bar_w - tot_text_w) // 2
                mid_y = bar_h // 2

                for j, (w_str, ww, wh, bx0, by0, cur_f) in enumerate(word_boxes):
                    wy = mid_y - wh // 2 - by0
                    if j == act_idx:
                        act_col = (217, 119, 87, 255) if is_light_bg else (242, 133, 94, 255)
                        d.text((cx - bx0, wy), w_str, font=cur_f, fill=act_col)
                        # Sleek 4px terracotta accent underline under active spoken word (no dark box!)
                        ul_y = mid_y + wh // 2 + 8
                        d.rounded_rectangle([cx, ul_y, cx + ww, ul_y + 4], radius=2, fill=act_col)
                    else:
                        inact_col = (20, 20, 19, 234) if is_light_bg else (250, 249, 245, 244)
                        d.text((cx - bx0, wy), w_str, font=cur_f, fill=inact_col)
                    cx += ww + gap

                state_cache[(g_idx, act_idx, is_light_bg)] = im.tobytes()

    with tempfile.TemporaryDirectory(prefix="karaoke_", dir=str(VAULT_TMP)) as td:
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
                    for j, w_obj in enumerate(grp):
                        if t >= w_obj["start"] - 0.03:
                            act_j = j
                    chosen_bytes = state_cache[(g_idx, act_j, is_light)]
                    break
            proc_ov.stdin.write(chosen_bytes)

        proc_ov.stdin.close()
        err_out = proc_ov.stderr.read() if proc_ov.stderr else b""
        if proc_ov.wait() != 0:
            raise RuntimeError(f"Karaoke overlay failed: {err_out.decode(errors='ignore')[-400:]}")


async def run_one_click_autopilot(
    topic: str,
    keyword: str = "SKILL",
    out_dir: Path | None = None,
    voice_profile: str = "modal_bariton_hd",
    with_subtitles: bool = True,
    photo_path: Path | None = None,
    target_duration: float = 10.0,
    on_step=None,
) -> dict[str, Any]:
    """
    End-to-end 1-Command Autopilot Conveyor:
    Supports BOTH short 10s Viral Hook Reels AND full 40+ second 7-chapter Storytelling Reels!
    Topic + Keyword -> DIYOR.CTR 4:5 Cover PNG + v4 Full-Frame 9:16 Hook + Claude TechBrief + Clawd
    + Modal Kino Bariton HD (-14.5 LUFS) + Modal Whisper Sync Karaoke Subtitles + Caption!
    """
    async def _emit(msg: str) -> None:
        if on_step is not None:
            try:
                await on_step(msg)
            except Exception:
                pass

    t0 = time.time()
    await _emit("🧠 <b>2-qadam:</b> Jonli internet faktlari va AI-rejissyor orqali noyob ssenariy tuzilmoqda...")
    bp = await generate_dynamic_ai_blueprint(topic, keyword, target_duration=target_duration)
    kw = bp["keyword"]
    is_long = bool(bp.get("is_long"))
    ts = int(time.time())
    portrait = photo_path if (photo_path and photo_path.exists()) else DEFAULT_PORTRAIT

    if out_dir is None:
        out_dir = Path("/home/user/.cache/diyor_vault/media/custom_renders") / f"autopilot_{kw.lower()}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize Modal Cloud · Kino Bariton HD Voiceover
    await _emit("🎙 <b>3-qadam:</b> Kino Bariton HD ovoz sintez qilinmoqda...")
    vo_wav = out_dir / f"00_voice_{voice_profile}.wav"
    tts_meta = await synthesize_pro_uzbek_voice(bp["voice_script"], vo_wav, profile=voice_profile, speed=1.0)
    min_floor = max(float(target_duration or 12.0), 40.0) if is_long else max(float(target_duration or 11.0), 9.5)
    vo_dur = max(min_floor, float(tts_meta["duration"]) + 0.85)

    # 2. Fetch Modal Faster-Whisper Word-Timestamps in parallel with 4:5 Cover & v4 9:16 Hook frames!
    await _emit("🖼 <b>4-qadam:</b> 4:5 DIYOR.CTR muqova va 3D hook kadrlar chizilmoqda...")
    ffmpeg_bin = get_ffmpeg_bin()
    vo_16k = out_dir / "tmp_vo_16k.wav"
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(vo_wav), "-ar", "16000", "-ac", "1", str(vo_16k)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )

    cover_4x5_png = out_dir / f"01_KARUSEL_muqova_{kw.lower()}_4x5.png"
    hook_dur = 3.2 if is_long else 2.6
    rem_dur = max(36.8 if is_long else 6.8, round(vo_dur - hook_dur, 2))

    whisper_task = asyncio.create_task(transcribe_uzbek_via_modal(vo_16k))
    cover_task = asyncio.create_task(
        render_brand_photo_slide(portrait, cover_4x5_png, config=bp["hook_config"], aspect="4:5")
    )
    hook_frames_task = asyncio.create_task(
        render_brand_photo_parallax_frames(portrait, config=bp["hook_config"], aspect="9:16", duration=hook_dur, fps=30)
    )

    w_res, _, hook_frames = await asyncio.gather(whisper_task, cover_task, hook_frames_task)
    vo_16k.unlink(missing_ok=True)

    # 3. Render 9:16 Full-Frame v4 Hook + Bespoke AI-Authored Multi-Scene Story + Clawd
    await _emit("🎬 <b>5-qadam:</b> 9:16 Claude TechBrief noyob sahnalari render qilinmoqda...")
    raw_mp4 = out_dir / "tmp_raw_reel.mp4"

    ai_scenes = bp.get("scenes")
    if isinstance(ai_scenes, list) and len(ai_scenes) >= 2:
        # Weight multi-card scenes (`news_radar`, `pipeline_dm`, `scorecard_bars`, `vs_comparison`) slightly longer than CTA
        weights: list[float] = []
        for sc in ai_scenes:
            st_t = sc.get("type", "hook_stat")
            if st_t in ("news_radar", "pipeline_dm", "scorecard_bars", "vs_comparison"):
                weights.append(1.22)
            elif st_t == "cta_terminal":
                weights.append(0.85)
            else:
                weights.append(1.0)
        w_sum = sum(weights) or 1.0
        scenes_payload = []
        used = 0.0
        for idx_s, sc in enumerate(ai_scenes):
            sc_copy = dict(sc)
            if idx_s == len(ai_scenes) - 1:
                sc_copy["duration"] = max(2.4, round(rem_dur - used, 2))
            else:
                d_s = max(2.6, round(rem_dur * (weights[idx_s] / w_sum), 2))
                sc_copy["duration"] = d_s
                used += d_s
            scenes_payload.append(sc_copy)
    else:
        s1 = bp["scene1"]
        s1_dur = round(rem_dur * 0.58, 2)
        s2_dur = round(rem_dur - s1_dur, 2)
        scenes_payload = [
            {
                "type": "hook_stat",
                "duration": s1_dur,
                "eyebrow": s1["eyebrow"],
                "headlineHtml": s1["headlineHtml"],
                "subtext": s1["subtext"],
                "statLabel": s1["statLabel"],
                "statValue": s1["statValue"],
                "statSuffix": "%",
                "barPercent": s1["statValue"],
            },
            {
                "type": "cta_terminal",
                "duration": s2_dur,
                "eyebrow": "BEPUL QO‘LLANMA · DIRECT",
                "headlineHtml": f"Izohda <em>«{kw}»</em><br>deb yozing",
                "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — 3 soniyada Direct’ga yuboriladi!",
                "keyword": kw,
            },
        ]

    reel_meta = await render_diyor_motion_mp4(
        {
            "aspect": "9:16",
            "theme": bp.get("theme", "lotion"),
            "topicTag": f"{kw.lower()} · @diyor.ctr",
            "handle": "@DIYOR.CTR",
            "scenes": scenes_payload,
        },
        raw_mp4,
        fps=30,
        with_clawd=True,
        prepend_rgb_frames=hook_frames,
    )

    # 4. Mux Modal Kino Bariton HD + Ducked FX Bed (-14.5 LUFS)
    await _emit("🔤 <b>6-qadam:</b> -14.5 LUFS ovoz va qora xoshiyasiz karaoke subtitr yozilmoqda...")
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

    # 5. Burn Modal Whisper-Synced Kinetic Karaoke Subtitles into lower safe zone (`y=1638`)!
    final_reel_mp4 = out_dir / f"02_REELS_avto_{kw.lower()}_diyor_ctr_9x16.mp4"
    whisper_words = (w_res or {}).get("words", [])
    aligned_words = align_clean_uzbek_words(bp["display_words_text"], whisper_words, float(tts_meta["duration"]))

    if with_subtitles:
        await asyncio.to_thread(render_karaoke_overlay_onto_mp4, voiced_mp4, final_reel_mp4, aligned_words, 30, 1638)
        voiced_mp4.unlink(missing_ok=True)
    else:
        voiced_mp4.rename(final_reel_mp4)

    caption_file = out_dir / "INSTAGRAM_CAPTION.txt"
    caption_file.write_text(bp["caption"], encoding="utf-8")

    return {
        "ok": True,
        "topic": bp["topic"],
        "keyword": kw,
        "behindWord": bp["behindWord"],
        "reel_mp4": str(final_reel_mp4),
        "cover_png": str(cover_4x5_png),
        "voice_wav": str(vo_wav),
        "caption": bp["caption"],
        "tts": tts_meta,
        "whisper_words_count": len(whisper_words),
        "aligned_words": aligned_words,
        "duration": reel_meta["duration"],
        "elapsed_sec": round(time.time() - t0, 2),
    }
