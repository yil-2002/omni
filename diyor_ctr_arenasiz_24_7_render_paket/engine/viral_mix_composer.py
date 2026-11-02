#!/usr/bin/env python3
"""
MODULE 3: @diyor.ctr Multi-Series Instagram Mixed-Media ("Viral Mix") Factory
============================================================================
Generates complete 2026 Algorithm-Optimized Mixed-Media Carousels (`4:5`) + Hybrid Reels (`9:16`)
wired directly to @diyor.ctr's `🔒 Aqlli Follow-Gate` keywords (`TIZIM`, `XODIM`, `SOTUV`):

  1. `viral_mix_01_tizim` — AI + Follow-Gate 24/7 Avtopilot Voronkasi (`#FAF9F5` `--lotion`, keyword `TIZIM`)
  2. `viral_mix_02_xodim` — AI Xodim vs 500$ Menejer: Claude MCP + CRM (`#F4EDE3` `warm`, keyword `XODIM`)
  3. `viral_mix_03_sotuv` — Sovuq Obunachidan Issiq Xaridgacha: 2.33% ER + DM Skript (`#FAF9F5`, keyword `SOTUV`)

Every series produces 6 deliverables (5 Carousel items + 1 Hybrid 9:16 Reel + Uzbek Caption) stored in
`/home/user/.cache/diyor_vault/media/<slug>` and automatically synced to Telegram Cloud-Vault + GoFile!
"""
import argparse
import asyncio
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if "/home/user/tashqi_xotira" not in sys.path:
    sys.path.insert(0, "/home/user/tashqi_xotira")

from photo_brand_engine import render_brand_photo_slide, render_brand_photo_parallax_frames  # noqa: E402
from motion_engine import (  # noqa: E402
    CLAWD_SPRITE_BANK,
    ensure_clawd_sprite_bank,
    render_diyor_motion_mp4,
    render_static_editorial_slide,
)
from cloud_vault import (  # noqa: E402
    VAULT_MEDIA,
    init_vault_dirs,
    load_manifest,
    upload_file_to_cloud,
    workspace_health_report,
)

PRESETS: dict[str, dict[str, Any]] = {
    "tizim": {
        "slug": "viral_mix_01_tizim",
        "title": "01 · AI + Follow-Gate 24/7 Avtopilot Tizimi",
        "keyword": "TIZIM",
        "theme": "lotion",
        "slide1_photo": {
            "behindWord": "AVTOPILOT",
            "kicker": "SHAXSIY BREND · AI TIZIM",
            "headlineHtml": "Biznesingiz <em>24/7 avtopilotda</em> ishlasin",
            "subtext": "Instagram Direct + Claude AI orqali mijozlarni uyquda ham saralovchi tizim.",
            "topicTag": "01 / 05 · suring →",
            "callouts": [
                {"label": "CLAUDE MCP", "value": "24/7 Avtopilot"},
                {"label": "KONVERSIYA", "value": "+312 issiq lid/oy"},
            ],
        },
        "slide2_motion": {
            "topicTag": "02 / 05 · muammo va oqim",
            "scenes": [
                {
                    "type": "hook_stat",
                    "duration": 3.4,
                    "eyebrow": "NEGA LIDLAR SOVIYDI?",
                    "headlineHtml": "Mijoz yozganda<br><em>3 soniyada</em> javob",
                    "subtext": "Direct’da 15 daqiqa kutgan mijozning 78 foizi raqobatchidan xarid qiladi.",
                    "statLabel": "SAQLAB QOLINGAN ISSIQ LIDLAR",
                    "statValue": 94,
                    "statSuffix": "%",
                    "barPercent": 94,
                },
                {
                    "type": "pipeline_dm",
                    "duration": 4.2,
                    "eyebrow": "AQLLI FOLLOW-GATE OQIMI",
                    "headlineHtml": "Uch qadamli<br><em>avtomatik voronka</em>",
                    "steps": [
                        {"tag": "01 · IZOH", "title": "Mijoz post ostiga «TIZIM» deb yozadi", "meta": "0.4 soniya"},
                        {"tag": "02 · FOLLOW-GATE", "title": "Obuna holati Graph API orqali tekshiriladi", "meta": "is_follow = true"},
                        {"tag": "03 · DIRECT AI", "title": "PDF qo‘llanma + AI saralash savoli boradi", "meta": "24/7 Avtopilot"},
                    ],
                },
            ],
        },
        "slide3_arch": {
            "eyebrow": "SAQLAB QO‘YISH UCHUN SXEMA",
            "headlineHtml": "Bitta postdan<br><em>issiq sotuvgacha</em> yo‘l",
            "nodes": [
                {"num": "01", "tag": "TRIGGER · REELS / POST", "title": "Mijoz izohda «TIZIM» so‘zini yozadi", "desc": "Algoritm izohlar oqimi hisobiga postni obunachi bo‘lmagan auditoriyaga (Explore) chiqaradi."},
                {"num": "02", "tag": "TEKSHIRUV · GRAPH API", "title": "Aqlli Follow-Gate obunani tekshiradi", "desc": "Obuna bo‘lmagan foydalanuvchiga 1-bosishli tugma chiqadi — obunaga o‘tish 3.1x oshadi."},
                {"num": "03", "tag": "KONVERSIYA · CLAUDE MCP", "title": "PDF qo‘llanma + 2 savolli AI saralash", "desc": "Claude mijoz budjeti va ehtiyojini aniqlab, tayyor issiq lidni CRM’ga yuboradi."},
            ],
        },
        "slide4_score": {
            "eyebrow": "30 KUNLIK NATIJA · SCORECARD",
            "headlineHtml": "Raqamlar<br><em>aldamaydi</em>",
            "ringScore": 98,
            "metrics": [
                {"label": "Yangi obunachi konversiyasi (Follow-Gate)", "val": 310, "suffix": "%", "pct": 92},
                {"label": "O‘rtacha javob tezligi (Direct AI)", "val": 3, "suffix": " soniya", "pct": 96},
                {"label": "Sotuvga tayyor issiq lidlar ulushi", "val": 42, "suffix": "%", "pct": 78},
            ],
            "ctaHead": "To‘liq sxema<br><em>tayyor</em>",
            "ctaSub": "8-sahifali PDF qo‘llanma va 7 ta avto-javob shablonini bepul yuklab oling:",
        },
        "slide5_cta": {
            "headlineHtml": "Izohda <em>«TIZIM»</em><br>deb yozing",
            "subtext": "Avval @diyor.ctr sahifasiga obuna bo‘ling — Aqlli Follow-Gate qo‘llanmani 3 soniyada Direct’ga yuboradi.",
            "perks": [
                "8-sahifali to‘liq AI + Follow-Gate sxemasi (PDF)",
                "7 ta yuqori konversiyali avto-javob skripti",
                "Claude MCP orqali mijoz saralash shabloni",
            ],
        },
        "reel_hook": {
            "behindWord": "AVTOPILOT",
            "kicker": "SHAXSIY BREND · AI REEL",
            "headlineHtml": "Direct’da mijoz <em>yo‘qotmang</em>",
            "subtext": "3 soniyada javob beruvchi Claude + Follow-Gate voronkasi.",
            "callouts": [
                {"label": "JAVOB TEZLIGI", "value": "0.4 soniya"},
                {"label": "FOLLOW-GATE", "value": "+310% obuna"},
            ],
        },
        "caption": (
            "Mijoz Direct’ga yozganda 15 daqiqa kechiksangiz — issiq sotuvlarning 78% raqobatchiga ketadi. ⚡️\n\n"
            "Shu muammoni yopish uchun men Instagram sahifamda Claude AI + Aqlli Follow-Gate tizimini yig‘dim:\n"
            "1️⃣ Mijoz izohda bitta kalit so‘z yozadi\n"
            "2️⃣ Tizim obuna bo‘lganini Graph API orqali tekshiradi (+310% obuna)\n"
            "3️⃣ 3 soniyada PDF qo‘llanma + saralovchi savol yuborib, tayyor lidni ajratib beradi\n\n"
            "🎁 8-sahifali to‘liq arxitektura va 7 ta skriptni bepul olish uchun:\n"
            "1. @diyor.ctr sahifamga obuna bo‘ling\n"
            "2. Izohda TIZIM deb yozing — bot 3 soniyada Direct’ingizga yuboradi! 👇"
        ),
    },
    "xodim": {
        "slug": "viral_mix_02_xodim",
        "title": "02 · AI Xodim vs 500$ Menejer (Claude MCP + CRM)",
        "keyword": "XODIM",
        "theme": "warm",
        "slide1_photo": {
            "behindWord": "AI XODIM",
            "kicker": "CLAUDE MCP · AVTOMATIZATSIYA",
            "headlineHtml": "Bitta AI xodim <em>3 ta menejer</em> o‘rnini bosadi",
            "subtext": "Tungi soat 03:00 da ham charchamasdan mijozga javob beruvchi va CRM to‘ldiruvchi tizim.",
            "topicTag": "01 / 05 · suring →",
            "callouts": [
                {"label": "XARAJAT", "value": "-82% tejash"},
                {"label": "ISH TARTIBI", "value": "24/7 · 0 xato"},
            ],
        },
        "slide2_motion": {
            "topicTag": "02 / 05 · tezlik va aniqlik",
            "scenes": [
                {
                    "type": "hook_stat",
                    "duration": 3.4,
                    "eyebrow": "ODDIY MENEJER VS CLAUDE AI",
                    "headlineHtml": "Xarajatlarni<br><em>82 foizga</em> qisqartiring",
                    "subtext": "Inson omili tufayli yo‘qotiladigan yozishmalar va unutilgan lidlarga nuqta qo‘ying.",
                    "statLabel": "AVTOMATLASHTIRILGAN MUROJAATLAR",
                    "statValue": 97,
                    "statSuffix": "%",
                    "barPercent": 97,
                },
                {
                    "type": "pipeline_dm",
                    "duration": 4.2,
                    "eyebrow": "AI XODIM QANDAY ISHLAYDI?",
                    "headlineHtml": "To‘liq <em>CRM va Direct</em><br>integratsiyasi",
                    "steps": [
                        {"tag": "01 · QABUL", "title": "Direct, Telegram va saytdan xabarni ushlaydi", "meta": "0.3 soniya"},
                        {"tag": "02 · DIALOG", "title": "Bilimlar bazasi asosida aniq narx va yechim aytadi", "meta": "Claude 4 · UZ"},
                        {"tag": "03 · CRM", "title": "Telefon raqamni olib amoCRM / Sheets’ga yozadi", "meta": "Avto-bildirish"},
                    ],
                },
            ],
        },
        "slide3_arch": {
            "eyebrow": "AI XODIM ARXITEKTURASI",
            "headlineHtml": " Uchta bo‘g‘inli<br><em>aqlli ofis</em> sxemasi",
            "nodes": [
                {"num": "01", "tag": "KIRISH KANALLARI", "title": "Instagram Direct + Izohlar + Telegram", "desc": "Barcha kanallardan kelgan savollar yagona webhook orqali yo‘qotishlarsiz yig‘iladi."},
                {"num": "02", "tag": "MIYA · CLAUDE SKILLS", "title": "Sizning uslubingizda javob beruvchi AI Xodim", "desc": "Skript emas — biznesingiz narxlari, keyslari va e’tirozlarni yopish qoidalarini biladi."},
                {"num": "03", "tag": "NATIJA · SOTUV BO‘LIMI", "title": "Faqat issiq va saralangan mijoz uzatiladi", "desc": "Sotuv menejeri vaqtini salom-alik emas, faqat tayyor to‘lov qiluvchi mijozga sarflaydi."},
            ],
        },
        "slide4_score": {
            "eyebrow": "AI XODIM ROI KO‘RSATKICHLARI",
            "headlineHtml": "Bir oyda<br><em>o‘zini oqlaydi</em>",
            "ringScore": 99,
            "metrics": [
                {"label": "Oylik ish haqi va operatsion tejash", "val": 82, "suffix": "%", "pct": 86},
                {"label": "Bir vaqtda xizmat ko‘rsatiladigan mijozlar", "val": 500, "suffix": "+", "pct": 95},
                {"label": "Sotuv qo‘ng‘irog‘iga yozilish o‘sishi", "val": 240, "suffix": "%", "pct": 88},
            ],
            "ctaHead": "AI xodimni<br><em>ishga tushiring</em>",
            "ctaSub": "Tayyor promptlar va CRM ulash sxemasini hoziroq Direct’dan oling:",
        },
        "slide5_cta": {
            "headlineHtml": "Izohda <em>«XODIM»</em><br>deb yozing",
            "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — AI Xodim arxitekturasi va prompt shablonini 3 soniyada yuboraman.",
            "perks": [
                "Claude MCP asosidagi AI Xodim tizim prompti",
                "Instagram Direct + amoCRM / Google Sheets ulash sxemasi",
                "500$ tejovchi 24/7 mijoz saralash algoritmi",
            ],
        },
        "reel_hook": {
            "behindWord": "AI XODIM",
            "kicker": "CLAUDE MCP · 24/7 XODIM",
            "headlineHtml": "Uxlamaydigan <em>AI menejer</em>",
            "subtext": "Direct va Telegram’da mijozlarni o‘zi saralab CRM’ga yozadi.",
            "callouts": [
                {"label": "TEJASH", "value": "-82% xarajat"},
                {"label": "CLAUDE AI", "value": "500+ chat/kun"},
            ],
        },
        "caption": (
            "Soat tungi 23:30 da yozgan mijozga ertasi kuni tushda javob bersangiz — u allaqachon boshqadan sotib olgan bo‘ladi. 📉\n\n"
            "Bitta Claude AI Xodim esa:\n"
            "• 24/7 dam olishsiz 0.4 soniyada javob beradi\n"
            "• Mijozning muammosi va budjetini muloyim aniqlaydi\n"
            "• Tayyor telefon raqamni to‘g‘ri CRM yoki Telegram guruhingizga uzatadi\n\n"
            "🎁 AI Xodim prompti va to‘liq ulash sxemasini bepul olish uchun:\n"
            "1. @diyor.ctr sahifamga obuna bo‘ling\n"
            "2. Izohda XODIM deb yozing — bot 3 soniyada Direct’ga yuboradi! 👇"
        ),
    },
    "sotuv": {
        "slug": "viral_mix_03_sotuv",
        "title": "03 · Obunachidan Xaridgacha: Mixed-Media 2.33% ER + AI Sotuv",
        "keyword": "SOTUV",
        "theme": "lotion",
        "slide1_photo": {
            "behindWord": "KONVERSIYA",
            "kicker": "2026 ALGORITM · AI SOTUV",
            "headlineHtml": "Obunachi ko‘p, lekin <em>sotuv kammi?</em>",
            "subtext": "Qamrovni haqiqiy to‘lovga aylantiruvchi Mixed-Media + Direct AI sotuv tizimi.",
            "topicTag": "01 / 05 · suring →",
            "callouts": [
                {"label": "MIXED-MEDIA", "value": "2.33% ER Rekord"},
                {"label": "DIRECT SOTUV", "value": "+34% konversiya"},
            ],
        },
        "slide2_motion": {
            "topicTag": "02 / 05 · 2026 algoritm siri",
            "scenes": [
                {
                    "type": "hook_stat",
                    "duration": 3.4,
                    "eyebrow": "2026 INSTAGRAM ALGORITM TAHLILI",
                    "headlineHtml": "Foto + Video =<br><em>2.33% faollik</em>",
                    "subtext": "Oddiy Reels 0.50% faollik bersa, Mixed-Media karusel Instagram’da 4.6 barobar ko‘p muloqot ochadi.",
                    "statLabel": "IKKINCHI IMKONIYAT (RE-SERVE) QAMROVI",
                    "statValue": 233,
                    "statSuffix": "%",
                    "barPercent": 93,
                },
                {
                    "type": "pipeline_dm",
                    "duration": 4.2,
                    "eyebrow": "QAMROVDAN TO‘LOVGACHA 3 QADAM",
                    "headlineHtml": "Direct ichida<br><em>muloyim sotuv</em>",
                    "steps": [
                        {"tag": "01 · QARMAQ", "title": "Mixed-Media karusel saqlash va izoh yig‘adi", "meta": "Saves 4.8%"},
                        {"tag": "02 · DIAGNOSTIKA", "title": "Follow-Gate orqali sovg‘a + 2 ta savol beriladi", "meta": "DM suhbat"},
                        {"tag": "03 · XARID", "title": "Issiq mijoz razbor yoki xaridga yoziladi", "meta": "34% konversiya"},
                    ],
                },
            ],
        },
        "slide3_arch": {
            "eyebrow": "DIRECT AI SOTUV SKRIPTI",
            "headlineHtml": "Bosimsiz sotuvchi<br><em>3 ta xabar</em> formulasi",
            "nodes": [
                {"num": "01", "tag": "1-XABAR · QIYMAT + FOLLOW-GATE", "title": "Foydali PDF yoki chek-listni 3 soniyada bering", "desc": "Mijoz darhol real foyda oladi va sizga bo‘lgan ishonch birinchi soniyadanoq oshadi."},
                {"num": "02", "tag": "2-XABAR · OG‘RIQNI ANIQLASH", "title": "«Hozir asosiy maqsadingiz qamrovmi yoki tizimli sotuv?»", "desc": "Ikki variantli yengil savol Direct’da 58% javob qaytarish ko‘rsatkichini beradi."},
                {"num": "03", "tag": "3-XABAR · ANIQ TAKLIF", "title": "Mijoz javobiga mos shaxsiy yechim va qo‘ng‘iroq", "desc": "Sovuq reklama emas, mijozning o‘z muammosiga aniq yechim taklif qilingani uchun xarid yengil yopiladi."},
            ],
        },
        "slide4_score": {
            "eyebrow": "SOTUV VORONKASI METRIKALARI",
            "headlineHtml": "Har bir post —<br><em>sotuv mashinasi</em>",
            "ringScore": 96,
            "metrics": [
                {"label": "Mixed-Media orqali organik qamrov o‘sishi", "val": 233, "suffix": "%", "pct": 91},
                {"label": "Direct’da ikki tomonlama suhbatga kirish", "val": 58, "suffix": "%", "pct": 82},
                {"label": "Saralangan lidlardan xaridga o‘tish", "val": 34, "suffix": "%", "pct": 74},
            ],
            "ctaHead": "Tayyor sotuv<br><em>skriptini oling</em>",
            "ctaSub": "Direct’da mijozni xaridga olib boruvchi 7 ta skript bepul:",
        },
        "slide5_cta": {
            "headlineHtml": "Izohda <em>«SOTUV»</em><br>deb yozing",
            "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — Direct AI sotuv skriptlari va Mixed-Media shablonini yuboraman.",
            "perks": [
                "Direct’da 58% javob oluvchi 3-qadamli skriptlar",
                "Mixed-Media (Foto + Motion) post reja jadvali",
                "E’tirozlarni muloyim yopuvchi AI javob andozalari",
            ],
        },
        "reel_hook": {
            "behindWord": "KONVERSIYA",
            "kicker": "AI SOTUV · 2.33% ER",
            "headlineHtml": "Qamrovni <em>sotuvga</em> aylantiring",
            "subtext": "Mixed-Media karusel + Direct AI sotuv voronkasi siri.",
            "callouts": [
                {"label": "FAOLLIK", "value": "2.33% Mixed ER"},
                {"label": "KONVERSIYA", "value": "34% xarid"},
            ],
        },
        "caption": (
            "Ko‘pchilik Reels million ko‘rilsa sotuv bo‘ladi deb o‘ylaydi — lekin voronkasiz qamrov pul keltirmaydi. 💡\n\n"
            "2026-yilda Instagram’da eng yuqori natija berayotgan formula:\n"
            "1️⃣ Mixed-Media Karusel (Shaxsiy foto + Claude Motion video = 2.33% ER)\n"
            "2️⃣ Aqlli Follow-Gate (tekin qiymat evaziga obuna + Direct muloqot)\n"
            "3️⃣ 3-xabarli AI Diagnostika (bosimsiz issiq sotuv)\n\n"
            "🎁 Tayyor Direct sotuv skriptlarini bepul olish uchun:\n"
            "1. @diyor.ctr sahifamga obuna bo‘ling\n"
            "2. Izohda SOTUV deb yozing — bot 3 soniyada yuboradi! 👇"
        ),
    },
}


async def ensure_clawd_cached_or_hydrated() -> None:
    """Restores `clawd_sprites_v1.zip` from Cloud/Telegram if available, otherwise renders once & uploads!"""
    init_vault_dirs()
    manifest = load_manifest()
    zip_dest = VAULT_MEDIA / "clawd_sprites_v1.zip"
    hook_dir = CLAWD_SPRITE_BANK / "hook"

    if not (hook_dir.exists() and len(list(hook_dir.glob("f*.png"))) >= 24):
        info = manifest.get("items", {}).get("clawd_sprites_v1.zip")
        if info:
            tg_fids = info.get("telegram_file_ids") or []
            if tg_fids and not zip_dest.exists():
                from telegram_vault_bot import download_from_telegram_vault
                download_from_telegram_vault(tg_fids, zip_dest)
            if zip_dest.exists():
                with zipfile.ZipFile(zip_dest, "r") as zf:
                    zf.extractall(CLAWD_SPRITE_BANK.parent)

    bank = await ensure_clawd_sprite_bank(sprite_fps=10, clip_dur=2.4)
    if not zip_dest.exists():
        with zipfile.ZipFile(zip_dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for fp in sorted(bank.rglob("*.png")):
                zf.write(fp, fp.relative_to(bank.parent))
        upload_file_to_cloud(zip_dest, key="clawd_sprites_v1.zip")


async def build_viral_mix_series(
    preset_key: str = "tizim",
    photo_path: Path = Path("/home/user/uploads/IMG_2860.jpeg"),
) -> dict[str, Any]:
    init_vault_dirs()
    await ensure_clawd_cached_or_hydrated()

    p = PRESETS[preset_key]
    pack_slug = p["slug"]
    theme = p["theme"]
    kw = p["keyword"]
    out_dir = VAULT_MEDIA / pack_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    if preset_key == "tizim":
        ws_link = Path("/home/user/viral_mix_diyor_pt")
        if ws_link.is_symlink():
            ws_link.unlink()
        if not ws_link.exists():
            ws_link.symlink_to(out_dir)

    s1_png = out_dir / "01_muqova_shaxsiy_brend_4x5.png"
    print(f"[{pack_slug} 1/6] Slide 1 CV Brand Photo...", flush=True)
    s1_res = await render_brand_photo_slide(photo_path, s1_png, config={**p["slide1_photo"], "handle": "@DIYOR.CTR"}, aspect="4:5")

    s2_mp4 = out_dir / "02_motion_isbot_4x5_clawd.mp4"
    print(f"[{pack_slug} 2/6] Slide 2 Motion + Clawd + -14.5 LUFS...", flush=True)
    s2_res = await render_diyor_motion_mp4(
        {"aspect": "4:5", "theme": theme, "handle": "@DIYOR.CTR", **p["slide2_motion"]},
        s2_mp4, fps=30, with_clawd=True,
    )

    s3_png = out_dir / "03_arxitektura_sxema_4x5.png"
    print(f"[{pack_slug} 3/6] Slide 3 Architecture Blueprint...", flush=True)
    await render_static_editorial_slide(
        {"aspect": "4:5", "theme": theme, "kind": "architecture", "slideIndex": "03 / 05", "topicTag": "03 / 05 · arxitektura", "handle": "@DIYOR.CTR", **p["slide3_arch"]},
        s3_png,
    )

    s4_mp4 = out_dir / "04_motion_natija_scorecard_4x5.mp4"
    print(f"[{pack_slug} 4/6] Slide 4 Scorecard Motion + -14.5 LUFS...", flush=True)
    sc = p["slide4_score"]
    s4_res = await render_diyor_motion_mp4(
        {
            "aspect": "4:5",
            "theme": theme,
            "topicTag": "04 / 05 · real natijalar",
            "handle": "@DIYOR.CTR",
            "scenes": [
                {"type": "scorecard_bars", "duration": 3.8, "eyebrow": sc["eyebrow"], "headlineHtml": sc["headlineHtml"], "ringScore": sc["ringScore"], "metrics": sc["metrics"]},
                {"type": "cta_terminal", "duration": 2.8, "eyebrow": "KEYINGI SLAYDDA OLING", "headlineHtml": sc["ctaHead"], "subtext": sc["ctaSub"], "keyword": kw},
            ],
        },
        s4_mp4, fps=30, with_clawd=False,
    )

    s5_png = out_dir / f"05_cta_{kw.lower()}_4x5.png"
    print(f"[{pack_slug} 5/6] Slide 5 Follow-Gate CTA ({kw})...", flush=True)
    await render_static_editorial_slide(
        {"aspect": "4:5", "theme": theme, "kind": "cta", "slideIndex": "05 / 05", "keyword": kw, "topicTag": "05 / 05 · izoh qoldiring", "handle": "@DIYOR.CTR", **p["slide5_cta"]},
        s5_png,
    )

    reel_mp4 = out_dir / "BONUS_hybrid_reel_9x16_clawd.mp4"
    print(f"[{pack_slug} 6/6] BONUS 9:16 Hybrid Reel (2.5D Parallax + Clawd)...", flush=True)
    hook_frames = await render_brand_photo_parallax_frames(
        photo_path, config={**p["reel_hook"], "topicTag": f"ai · {kw.lower()}", "handle": "@DIYOR.CTR"}, aspect="9:16", duration=2.5, fps=30
    )
    reel_res = await render_diyor_motion_mp4(
        {
            "aspect": "9:16",
            "theme": theme,
            "topicTag": f"ai · {kw.lower()} · 2026",
            "handle": "@DIYOR.CTR",
            "scenes": [
                p["slide2_motion"]["scenes"][1],
                {"type": "cta_terminal", "duration": 2.9, "eyebrow": "BEPUL QO‘LLANMA · DIRECT", "headlineHtml": f"Izohda <em>«{kw}»</em><br>deb yozing", "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — bot 3 soniyada Direct’ga yuboradi!", "keyword": kw},
            ],
        },
        reel_mp4, fps=30, with_clawd=True, prepend_rgb_frames=hook_frames,
    )

    cap_md = out_dir / "POST_MATNI_VA_QOLLANMA.md"
    cap_md.write_text(f"# 🚀 {p['title']} (@diyor.ctr)\n\n## Tayyor Post Matni (Caption)\n\n{p['caption']}\n", encoding="utf-8")

    zip_path = VAULT_MEDIA / f"{pack_slug}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in sorted(out_dir.iterdir()):
            if fp.is_file():
                zf.write(fp, f"{pack_slug}/{fp.name}")

    print(f"[{pack_slug} Cloud] Uploading ZIP + MP4s to Cloud & Telegram (@diyor937373839337bot)...", flush=True)
    cloud_zip = upload_file_to_cloud(zip_path, key=f"{pack_slug}.zip")

    summary = {
        "preset": preset_key,
        "pack_slug": pack_slug,
        "title": p["title"],
        "keyword": kw,
        "theme": theme,
        "caption": p["caption"],
        "files": {
            "s1": s1_png.name,
            "s2": s2_mp4.name,
            "s3": s3_png.name,
            "s4": s4_mp4.name,
            "s5": s5_png.name,
            "reel": reel_mp4.name,
        },
        "cloud_zip": cloud_zip,
        "s1_telemetry": s1_res["telemetry"],
        "s2_meta": s2_res,
        "s4_meta": s4_res,
        "reel_meta": reel_res,
    }
    (out_dir / "pack_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="+", default=["xodim", "sotuv"], choices=list(PRESETS.keys()))
    args = ap.parse_args()
    for sk in args.series:
        out = asyncio.run(build_viral_mix_series(sk))
        print(f"✓ Completed {out['pack_slug']} -> {out['cloud_zip'].get('gofile_page')}")
    print(json.dumps(workspace_health_report(), indent=2, ensure_ascii=False))
