#!/usr/bin/env python3
"""
🚀 @diyor.ctr — PUBLIC INSTAGRAM MIXED-MEDIA STACK:
«Bir kishilik AI-Imperiya (Vibe Coding + Claude Skills + MCP)» (Kalit so‘z: SKILL)
==================================================================================
100% yangilangan v4 Clean-Plate dvigateli asosida:
- `DIYOR PT` devordagi studiya yozuvi 100% kesilmasdan, xiralashmasdan va usti yopilmasdan ko‘rinadi!
- Bosh, soch va quloq atrofida ikkilanish (ghosting) yoki oq hoshiya (halo) 0%!
- Instagram Public (Ommaviy) lenta uchun tartiblangan 6-slaydli Mixed-Media Karusel (`4:5`)
  + alohida 9:16 Gibrid Reel + tayyor Caption va Pinned Comment Telegram botga yuboriladi!
"""
import asyncio
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if "/home/user/tashqi_xotira" not in sys.path:
    sys.path.insert(0, "/home/user/tashqi_xotira")

from photo_brand_engine import (  # noqa: E402
    VAULT_TMP,
    render_brand_photo_parallax_frames,
    render_brand_photo_slide,
)
from motion_engine import (  # noqa: E402
    ensure_clawd_sprite_bank,
    get_ffmpeg_bin,
    render_diyor_motion_mp4,
    render_static_editorial_slide,
)
from cloud_vault import (  # noqa: E402
    VAULT_MEDIA,
    init_vault_dirs,
    upload_file_to_cloud,
    workspace_health_report,
)
from telegram_vault_bot import (  # noqa: E402
    load_tg_secret,
    tg_send_message,
    upload_to_telegram_vault,
)


PUBLIC_CAPTION = """2022-yilda bitta raqamli servis yoki IT-mahsulot chiqarish uchun 15,000$ budjet, 3 oy vaqt va 6 kishilik jamoa kerak edi.

2026-yilda esa «Bir kishilik AI-Imperiya» davri boshlandi. ⚡️

Bugun bitta asoschi noutbuk oldida o‘tirib, dasturlash tilini yodlamasdan 48 soat ichida to‘liq ishlovchi mahsulot qurmoqda. Buning ortida 3 ta texnologiya turibdi:

1️⃣ Claude Skills — har safar noldan prompt yozmaysiz. O‘z arxitekturangiz, dizayn standartingiz va biznes qoidalaringizni bitta doimiy ko‘nikma fayliga muhrlaysiz.
2️⃣ Vibe Coding (Cursor + Claude Code) — vazifani o‘z tilingizda tushuntirasiz, AI esa frontend, backend va dizaynni o‘zi yig‘ib, xatolarini o‘zi tekshiradi.
3️⃣ MCP Protokollar — mahsulotingizni Telegram bot, ma’lumotlar bazasi va to‘lov tizimlariga avtomatik ulaydi.

Karuselni oxirigacha suring — 48 soatda g‘oyadan ishchi MVP’gacha chiqish xaritasini joyladim 👉

🎁 Siz uchun «Solo AI-Imperiya» boshlang‘ich to‘plamini (5 ta eng kuchli Claude Skills shabloni + 48 soatlik Vibe Coding yo‘l xaritasi + MCP vositalar ro‘yxati) tayyorlab qo‘ydim:

1. @diyor.ctr sahifamga obuna bo‘ling
2. Izohda SKILL deb yozing — Aqlli Follow-Gate tizimim to‘plamni 3 soniyada Direct’ingizga yuboradi! 👇

#diyorpt #suniyintellekt #vibecoding #claudeai #shaxsiybrend #startap #ituzbekistan #biznesavtomatizatsiya"""

PINNED_COMMENT = """📌 Birinchi qadam: @diyor.ctr sahifasiga obuna bo‘ling va shu izoh ostiga SKILL so‘zini qoldiring — 5 ta tayyor Claude Skills shabloni va 48 soatlik Vibe Coding xaritasini 3 soniyada Direct’ingizga jo‘nataman! 🚀"""


async def main() -> None:
    init_vault_dirs()
    photo_in = Path("/home/user/uploads/IMG_2860.jpeg")
    slug = "public_stack_solo_ai_imperiya"
    out_dir = VAULT_MEDIA / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Convenience workspace symlink
    ws_link = Path("/home/user/instagram_public_solo_ai_imperiya")
    if ws_link.is_symlink():
        ws_link.unlink()
    if not ws_link.exists():
        ws_link.symlink_to(out_dir)

    # Step 0: Ensure Clawd watercolour sprites are cached & backed up
    bank = await ensure_clawd_sprite_bank(sprite_fps=10, clip_dur=2.4)
    czip = VAULT_MEDIA / "clawd_sprites_v1.zip"
    if not czip.exists():
        with zipfile.ZipFile(czip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for fp in sorted(bank.rglob("*.png")):
                zf.write(fp, fp.relative_to(bank.parent))
        upload_file_to_cloud(czip, key="clawd_sprites_v1.zip")

    # -------------------------------------------------------------------------
    # SLIDE 1 (4:5 PNG): Personal Brand Cover — Razor-Sharp `DIYOR PT` + 3D `AI IMPERIYA`
    # -------------------------------------------------------------------------
    print("[1/7] Slide 1: 4:5 Personal Brand Cover (v4 Razor-Sharp DIYOR PT)...", flush=True)
    s1_png = out_dir / "01_KARUSEL_muqova_ai_imperiya_4x5.png"
    s1_res = await render_brand_photo_slide(
        photo_in,
        s1_png,
        config={
            "behindWord": "AI IMPERIYA",
            "kicker": "VIBE CODING · CLAUDE SKILLS",
            "headlineHtml": "Bir kishilik <em>AI-Imperiya</em> davri keldi",
            "subtext": "Dasturchi va dizaynersiz — g‘oyadan daromadli raqamli servisgacha 48 soat.",
            "topicTag": "01 / 06 · suring →",
            "handle": "@DIYOR.CTR",
            "callouts": [
                {"label": "JAMOA", "value": "1 kishi + AI"},
                {"label": "ISHGA TUSHISH", "value": "48 soatda MVP"},
            ],
        },
        aspect="4:5",
    )

    # -------------------------------------------------------------------------
    # SLIDE 2 (4:5 MP4): Second-Chance Re-Serve Motion Video + Clawd + -14.6 LUFS FX
    # -------------------------------------------------------------------------
    print("[2/7] Slide 2: 4:5 Motion Video + Clawd + -14.6 LUFS FX...", flush=True)
    s2_mp4 = out_dir / "02_KARUSEL_motion_arsenal_4x5_clawd.mp4"
    s2_spec = {
        "aspect": "4:5",
        "theme": "lotion",
        "topicTag": "02 / 06 · 2022 vs 2026",
        "handle": "@DIYOR.CTR",
        "scenes": [
            {
                "type": "hook_stat",
                "duration": 3.5,
                "eyebrow": "2022 VS 2026 HAQIQATI",
                "headlineHtml": "6 kishilik jamoa ishini<br><em>1 kishi + AI</em> bajarmoqda",
                "subtext": "Oldin 15,000$ va 3 oy ketgan IT-mahsulot bugun bitta noutbukda 2 kunda yig‘iladi.",
                "statLabel": "VAQT VA BUDJET TEJALISHI",
                "statValue": 92,
                "statSuffix": "%",
                "barPercent": 92,
            },
            {
                "type": "pipeline_dm",
                "duration": 4.2,
                "eyebrow": "SOLO-FOUNDER TEXNOLOGIK ZANJIRI",
                "headlineHtml": "Kod yozmasdan<br><em>mahsulot qurish</em> tizimi",
                "steps": [
                    {"tag": "01 · CLAUDE SKILLS", "title": "Arxitektura, dizayn va biznes mantiqni tuzadi", "meta": "Miya · UZ/EN"},
                    {"tag": "02 · VIBE CODING", "title": "Cursor + Claude Code tayyor ilova va botni yozadi", "meta": "0 qator qo‘lda kod"},
                    {"tag": "03 · MCP PROTOKOL", "title": "Baza, Telegram va to‘lov tizimini avto-ulaydi", "meta": "48 soatda MVP"},
                ],
            },
        ],
    }
    await render_diyor_motion_mp4(s2_spec, s2_mp4, fps=30, with_clawd=True)

    # -------------------------------------------------------------------------
    # SLIDE 3 (4:5 PNG): Save-Magnet 3 Pillars Blueprint
    # -------------------------------------------------------------------------
    print("[3/7] Slide 3: 4:5 Three Pillars Architecture PNG...", flush=True)
    s3_png = out_dir / "03_KARUSEL_uch_ustun_sxema_4x5.png"
    await render_static_editorial_slide(
        {
            "aspect": "4:5",
            "theme": "lotion",
            "kind": "architecture",
            "slideIndex": "03 / 06",
            "eyebrow": "SAQLAB QO‘YING · 3 TA USTUN",
            "headlineHtml": "Solo AI-Imperiyaning<br><em>uchta temir</em> quroli",
            "topicTag": "03 / 06 · texnologiyalar",
            "handle": "@DIYOR.CTR",
            "nodes": [
                {
                    "num": "01",
                    "tag": "STANDART · CLAUDE SKILLS",
                    "title": "Takrorlanuvchi tajribani Skill faylga muhrlang",
                    "desc": "Har gal uzun prompt yozmaysiz — dizayn, kopirayting va kod qoidangiz doim bir xil yuqori sifatda ishlaydi.",
                },
                {
                    "num": "02",
                    "tag": "QURILISH · VIBE CODING",
                    "title": "Sintaksis emas, tizimli fikrlash muhim",
                    "desc": "Siz mahsulot mantiqi va foydalanuvchi tajribasini boshqarasiz, Claude esa minglab qator toza kodni yozib tekshiradi.",
                },
                {
                    "num": "03",
                    "tag": "AVTOMATIKA · MCP SERVERLAR",
                    "title": "Barcha tashqi xizmatlar bitta markazda",
                    "desc": "Ma’lumotlar bazasi, analitika, CRM va Telegram botlar o‘zaro inson aralashuvisiz bog‘lanadi.",
                },
            ],
        },
        s3_png,
    )

    # -------------------------------------------------------------------------
    # SLIDE 4 (4:5 MP4): Animated Solo-Founder Scorecard + Terminal
    # -------------------------------------------------------------------------
    print("[4/7] Slide 4: 4:5 Solo-Founder Scorecard Motion MP4...", flush=True)
    s4_mp4 = out_dir / "04_KARUSEL_motion_scorecard_4x5.mp4"
    s4_spec = {
        "aspect": "4:5",
        "theme": "lotion",
        "topicTag": "04 / 06 · solo iqtisodiyot",
        "handle": "@DIYOR.CTR",
        "scenes": [
            {
                "type": "scorecard_bars",
                "duration": 3.9,
                "eyebrow": "SOLO AI-BIZNES MATEMATIKASI",
                "headlineHtml": "Tezlik — yangi<br><em>raqobat ustunligi</em>",
                "ringScore": 99,
                "metrics": [
                    {"label": "G‘oyadan birinchi ishchi prototipgacha (MVP)", "val": 48, "suffix": " soat", "pct": 94},
                    {"label": "Sof foyda marjasi (katta shtatsiz model)", "val": 88, "suffix": "%", "pct": 88},
                    {"label": "Tajriba va gipoteza sinash tezligi", "val": 10, "suffix": "x tez", "pct": 96},
                ],
            },
            {
                "type": "cta_terminal",
                "duration": 2.7,
                "eyebrow": "SHAXSIY ARSENALNI OLING",
                "headlineHtml": "Tayyor <em>Skills paket</em><br>sizni kutmoqda",
                "subtext": "Keyingi slaydda 48 soatlik amaliy reja va bepul yuklab olish kalit so‘zi:",
                "keyword": "SKILL",
            },
        ],
    }
    await render_diyor_motion_mp4(s4_spec, s4_mp4, fps=30, with_clawd=False)

    # -------------------------------------------------------------------------
    # SLIDE 5 (4:5 PNG): 48-Hour Actionable Step-by-Step Roadmap (High Save Rate!)
    # -------------------------------------------------------------------------
    print("[5/7] Slide 5: 48-Hour Actionable Roadmap PNG...", flush=True)
    s5_png = out_dir / "05_KARUSEL_48soat_yol_xaritasi_4x5.png"
    await render_static_editorial_slide(
        {
            "aspect": "4:5",
            "theme": "lotion",
            "kind": "architecture",
            "slideIndex": "05 / 06",
            "eyebrow": "AMALIY REJA · 48 SOATDA MVP",
            "headlineHtml": "Bugunoq <em>nimadan</em><br>boshlash kerak?",
            "topicTag": "05 / 06 · amaliy xarita",
            "handle": "@DIYOR.CTR",
            "nodes": [
                {
                    "num": "01",
                    "tag": "1–6 SOAT · MUAMMO VA PRD",
                    "title": "Bitta tor va og‘riqli muammoni tanlang",
                    "desc": "Claude bilan birga 1 sahifalik aniq texnik reja (PRD): foydalanuvchi kim, qanday natija oladi va 3 ta asosiy ekran.",
                },
                {
                    "num": "02",
                    "tag": "6–30 SOAT · VIBE CODING YIG‘ISH",
                    "title": "Asosiy funksiyani Cursor / Claude’da quring",
                    "desc": "Murakkab dizaynga chalg‘imang — bitta asosiy qiymat beruvchi oqimni (masalan, AI tahlil yoki avto-hisobot) ishga tushiring.",
                },
                {
                    "num": "03",
                    "tag": "30–48 SOAT · REAL SINOV VA SOTUV",
                    "title": "Instagram’da ko‘rsating va 10 ta mijozda sinang",
                    "desc": "Jarayonning o‘zini kontent qilib ulashing — birinchi foydalanuvchilar sizga eng to‘g‘ri yo‘nalishni aytib beradi.",
                },
            ],
        },
        s5_png,
    )

    # -------------------------------------------------------------------------
    # SLIDE 6 (4:5 PNG): Follow-Gate CTA (`SKILL`)
    # -------------------------------------------------------------------------
    print("[6/7] Slide 6: Follow-Gate CTA Slide (SKILL)...", flush=True)
    s6_png = out_dir / "06_KARUSEL_cta_skill_4x5.png"
    await render_static_editorial_slide(
        {
            "aspect": "4:5",
            "theme": "lotion",
            "kind": "cta",
            "slideIndex": "06 / 06",
            "eyebrow": "BEPUL ARSENAL · DIRECT",
            "headlineHtml": "Izohda <em>«SKILL»</em><br>deb yozing",
            "subtext": "Avval @diyor.ctr sahifasiga obuna bo‘ling — Aqlli Follow-Gate 3 soniyada to‘plamni Direct’ga yuboradi.",
            "keyword": "SKILL",
            "topicTag": "06 / 06 · izoh qoldiring",
            "handle": "@DIYOR.CTR",
            "perks": [
                "5 ta eng kuchli tayyor Claude Skills shabloni",
                "Vibe Coding orqali 48 soatda MVP qurish xaritasi",
                "MCP serverlar va bepul AI vositalar ro‘yxati",
            ],
        },
        s6_png,
    )

    # -------------------------------------------------------------------------
    # ASSET 7 (9:16 MP4): Standalone Public Hybrid Reel (v4 Razor-Sharp `DIYOR PT` Parallax + Clawd!)
    # -------------------------------------------------------------------------
    print("[7/7] Asset 7: 9:16 Public Hybrid Reel (v4 Sharp DIYOR PT + Clawd + -14.6 LUFS)...", flush=True)
    reel_mp4 = out_dir / "07_REELS_public_ai_imperiya_9x16_clawd.mp4"
    hook_frames = await render_brand_photo_parallax_frames(
        photo_in,
        config={
            "behindWord": "AI IMPERIYA",
            "kicker": "VIBE CODING · CLAUDE SKILLS",
            "headlineHtml": "Dasturchisiz <em>AI-biznes</em> quring",
            "subtext": "Claude Skills + Vibe Coding orqali 48 soatda g‘oyadan tayyor mahsulotgacha.",
            "topicTag": "ai · imperiya · 2026",
            "handle": "@DIYOR.CTR",
            "callouts": [
                {"label": "JAMOA", "value": "1 kishi + AI"},
                {"label": "NATIJA", "value": "48 soatda MVP"},
            ],
        },
        aspect="9:16",
        duration=2.6,
        fps=30,
    )
    reel_spec = {
        "aspect": "9:16",
        "theme": "lotion",
        "topicTag": "ai · skill · 2026",
        "handle": "@DIYOR.CTR",
        "scenes": [
            s2_spec["scenes"][1],
            {
                "type": "cta_terminal",
                "duration": 2.9,
                "eyebrow": "BEPUL CLAUDE SKILLS PAKETI",
                "headlineHtml": "Izohda <em>«SKILL»</em><br>deb yozing",
                "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — bot 3 soniyada Direct’ingizga yuboradi!",
                "keyword": "SKILL",
            },
        ],
    }
    await render_diyor_motion_mp4(reel_spec, reel_mp4, fps=30, with_clawd=True, prepend_rgb_frames=hook_frames)

    # Save copy-pasteable public post guide
    (out_dir / "INSTAGRAM_PUBLIC_POST_MATNI.txt").write_text(
        PUBLIC_CAPTION + "\n\n---\nQADALADIGAN IZOH (PINNED COMMENT):\n" + PINNED_COMMENT + "\n",
        encoding="utf-8",
    )

    # Extract QA verification frame from the encoded 9:16 Reel MP4!
    ff = get_ffmpeg_bin()
    qa_jpg = VAULT_TMP / "qa_public_reel_v4.jpg"
    subprocess.run([ff, "-y", "-ss", "1.25", "-i", str(reel_mp4), "-frames:v", "1", "-q:v", "2", str(qa_jpg)], check=True, capture_output=True)

    # Create full ZIP archive & sync to Cloud
    zip_path = VAULT_MEDIA / f"{slug}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in sorted(out_dir.iterdir()):
            if fp.is_file():
                zf.write(fp, f"{slug}/{fp.name}")
    cloud_zip = upload_file_to_cloud(zip_path, key=f"{slug}.zip")

    # -------------------------------------------------------------------------
    # SEND COMPLETE ORDERED INSTAGRAM PUBLIC STACK TO TELEGRAM BOT!
    # -------------------------------------------------------------------------
    cid = load_tg_secret().get("chat_id")
    if cid:
        print(f"[Telegram] Sending full ordered Instagram Public Stack to chat_id={cid}...", flush=True)
        tg_send_message(
            cid,
            "🔥 @diyor.ctr — INSTAGRAM PUBLIC UCHUN TAYYOR STACK!\n"
            "Mavzu: «Bir kishilik AI-Imperiya (Vibe Coding + Claude Skills)» · Kalit so‘z: SKILL\n"
            "✅ v4 Clean-Plate: Orqa fondagi «DIYOR PT» yozuvi 100% to‘liq va tiniq, bosh/soch kesimi ideal!\n\n"
            "👇 Quyidagi 01 dan 06 gacha fayllarni aynan shu ketma-ketlikda bitta Instagram Karusel postiga qo‘shing (Foto + Video aralash Mixed-Media):"
        )
        ordered_items = [
            (s1_png, "01/06 [FOTO] · Muqova — «Bir kishilik AI-Imperiya» (DIYOR PT 100% tiniq!)", False),
            (s2_mp4, "02/06 [VIDEO + CLAWD] · 2-slayd Re-Serve Motion (-14.6 LUFS ovozli)", True),
            (s3_png, "03/06 [FOTO] · Solo AI-Imperiyaning 3 ta temir quroli (Saqlash uchun)", False),
            (s4_mp4, "04/06 [VIDEO] · Solo AI-Biznes Matematikasi Scorecard (-14.6 LUFS)", True),
            (s5_png, "05/06 [FOTO] · 48 soatda MVP — Amaliy yo‘l xaritasi", False),
            (s6_png, "06/06 [FOTO · CTA] · Izohda «SKILL» deb yozing (Follow-Gate)", False),
        ]
        for fp, cap, is_vid in ordered_items:
            upload_to_telegram_vault(fp, key=f"{slug}_{fp.name}", caption=cap, chat_id=cid, as_video=is_vid)

        tg_send_message(cid, "🎬 Endi esa alohida Reels bo‘limiga joylash uchun tayyor 9:16 Gibrid Reel 👇")
        upload_to_telegram_vault(
            reel_mp4,
            key=f"{slug}_{reel_mp4.name}",
            caption="07 [9:16 REELS] · 2.5D Shaxsiy Foto Parallax (DIYOR PT tiniq!) + Claude TechBrief + Clawd",
            chat_id=cid,
            as_video=True,
        )

        tg_send_message(cid, "📝 TAYYOR INSTAGRAM POST MATNI (Nusxa olib to‘g‘ri qo‘ying):\n\n" + PUBLIC_CAPTION)
        tg_send_message(cid, PINNED_COMMENT)
        upload_to_telegram_vault(
            zip_path,
            key=f"{slug}_full_pack.zip",
            caption="📦 Barcha 7 ta original fayl + matnlar yagona ZIP arxivda (Sifatni yo‘qotmasdan kompyuterda ochish uchun)",
            chat_id=cid,
            as_video=False,
        )

    print("Cloud ZIP:", cloud_zip.get("gofile_page"), "| Raw CDN:", cloud_zip.get("direct_cdn_url"))
    print("Health:", json.dumps(workspace_health_report(), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
