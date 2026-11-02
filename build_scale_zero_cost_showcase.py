#!/usr/bin/env python3
"""
🚀 @diyor.ctr — $0-Cost Scale-Up E2E Showcase Builder (`build_scale_zero_cost_showcase.py`)
==========================================================================================
Ovoz klonisiz ($0 xarajat!) yangi parallel render dvigateli, `16:9` YouTube Widescreen va
`50/50 Split-Screen` formatlarini E2E render qilib:
1. 19 GB SSD Vault'ga saqlaydi (`scale_zero_cost_v5/`);
2. GoFile + Litterbox Direct HTTPS CDN'ga yuklaydi;
3. `@diyor937373839337bot` (Telegram Cloud-Vault) ga yuboradi!
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

TB_ROOT = Path("/home/user/claude-techbrief")
TX_ROOT = Path("/home/user/tashqi_xotira")
for p in (TB_ROOT / "engine", TB_ROOT / "vositalar", TX_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from motion_engine import render_diyor_motion_mp4, get_ffmpeg_bin  # noqa: E402
from split_screen_composer import compose_split_screen_reel  # noqa: E402
from cloud_vault import ensure_hydrated, upload_file_to_cloud, VAULT_MEDIA  # noqa: E402
from telegram_vault_bot import load_tg_secret, upload_to_telegram_vault, tg_send_message  # noqa: E402


async def main() -> None:
    print("☁️ [0/4] Zaruriy oldingi public stack fayllari SSD Vault'ga tiklanmoqda...")
    await asyncio.to_thread(ensure_hydrated)

    out_dir = VAULT_MEDIA / "scale_zero_cost_v5"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. 16:9 YOUTUBE / PRESENTATION WIDESCREEN (`1920x1080`, 4 SCENES, PARALLEL ENGINE)
    # ------------------------------------------------------------------
    wide_mp4 = out_dir / "01_YOUTUBE_WIDE_ai_imperiya_16x9_clawd.mp4"
    wide_spec = {
        "aspect": "16:9",
        "theme": "lotion",
        "topicTag": "youtube · 16:9 · solo ai imperiya",
        "handle": "@DIYOR.CTR",
        "scenes": [
            {
                "type": "hook_stat",
                "duration": 3.5,
                "eyebrow": "YOUTUBE & PREZENTATSIYA · 16:9 WIDESCREEN",
                "headlineHtml": "10 kishilik jamoa emas —<br><em>1 kishi + Claude</em>",
                "subtext": "Katta loyihalar va YouTube tahlillar uchun ikki ustunli Claude-Wide 1920×1080 arxitekturasi.",
                "statLabel": "JAMOA XARAJATI TEJALISHI",
                "statValue": 92,
                "statSuffix": "%",
                "barPercent": 92,
            },
            {
                "type": "code_architecture",
                "duration": 3.8,
                "eyebrow": "02 · $0 BULUT ARXITEKTURASI",
                "headlineHtml": "Modal Parallel +<br><em>Cloudflare R2</em> CDN",
                "subtext": "Har oy $30 bepul Modal krediti va 10 GB bepul R2 xotirasi — abonent to‘lovisiz ($0/oy) ishlaydi.",
                "fileName": "diyor_ctr_zero_cost_stack.py",
                "badge": "$0 / OY STACK",
                "codeLines": [
                    "from modal_render_worker import render_slice_worker",
                    "from cloud_render_bridge import upload_to_cloudflare_r2",
                    "",
                    "# 40 ta parallel konteyner · $0/oy Starter tier",
                    "slices  = render_slice_worker.map(timeline_chunks)",
                    "cdn_url = await upload_to_cloudflare_r2('reel_1080p.mp4')",
                    "publish_to_instagram('@diyor.ctr', cdn_url, kw='SKILL')",
                ],
            },
            {
                "type": "scorecard_bars",
                "duration": 3.4,
                "eyebrow": "03 · KATTA VIDEO RENDER TEZLIGI",
                "headlineHtml": "Parallel bo‘laklab<br><em>3.4x tezroq</em> render",
                "subtext": "Sahna kadrlarini mustaqil oqimlarga bo‘lib yig‘ish va -14.5 LUFS cut-locked ovoz.",
                "ringValue": 96,
                "ringSuffix": "%",
                "ringLabel": "SIFAT & ANIQ VAQT",
                "bars": [
                    {"label": "Lokal 3-oqimli Parallel Chromium", "display": "3.2x tez ($0)", "percent": 86},
                    {"label": "Modal.com 40-konteyner Bulut ($30 bepul)", "display": "10x tez ($0)", "percent": 98},
                    {"label": "Cloudflare R2 + Meta Graph API", "display": "$0 Egress & Post", "percent": 100},
                ],
            },
            {
                "type": "cta_terminal",
                "duration": 3.1,
                "eyebrow": "04 · AVTOMATIK FOLLOW-GATE",
                "headlineHtml": "Izohda <em>«SKILL»</em><br>deb qoldiring",
                "subtext": "@diyor.ctr obunachilariga 3 soniyada to‘liq AI-Imperiya arsenali Direct’ga boradi!",
                "keyword": "SKILL",
            },
        ],
    }

    t0 = time.time()
    print("🎬 [1/4] 16:9 YouTube Widescreen (1920×1080, 4 sahna, Parallel Workers=3) render qilinmoqda...")
    wide_meta = await render_diyor_motion_mp4(wide_spec, wide_mp4, fps=30, with_clawd=True, parallel_workers=3)
    wide_elapsed = round(time.time() - t0, 1)
    print(f"   ✓ 16:9 tayyor ({wide_elapsed}s): {wide_mp4.name} ({wide_mp4.stat().st_size/(1024*1024):.2f} MB)")

    # ------------------------------------------------------------------
    # 2. 9:16 50/50 SPLIT-SCREEN REEL (`1080x1920`, $0 NO VOICE CLONE!)
    # ------------------------------------------------------------------
    split_mp4 = out_dir / "02_SPLIT_SCREEN_50x50_diyor_ctr_9x16.mp4"
    split_spec = {
        "theme": "lotion",
        "topicTag": "split · 50/50 · @diyor.ctr",
        "handle": "@DIYOR.CTR",
        "scenes": [
            {
                "type": "hook_stat",
                "duration": 3.4,
                "eyebrow": "50/50 SPLIT-SCREEN · JONLI EKSPERT",
                "headlineHtml": "Ovoz klonisiz <em>100% tabiiy</em><br>ekspert + animatsiya",
                "subtext": "Yuqorida Claude TechBrief isboti — pastda real kamera yoki 2.5D studiya!",
                "statLabel": "AUDITORIYA ISHONCHI",
                "statValue": 98,
                "statSuffix": "%",
                "barPercent": 98,
            },
            {
                "type": "pipeline_dm",
                "duration": 3.4,
                "eyebrow": "$0 AVTOMATLASHTIRISH ZANJIRI",
                "headlineHtml": "Kamera -> Bot -> <em>Split Reel</em>",
                "subtext": "@diyor937373839337bot ga video yuboring — tayyor 50/50 Reel qaytadi!",
                "steps": [
                    {"num": "01", "tag": "TELEFON KAMERA", "text": "15–30 soniya jonli fikr yozasiz (ovoz kloni kerak emas!)"},
                    {"num": "02", "tag": "CLAUDE MOTION", "text": "Yuqori 1080×960 ekranda raqamlar + Clawd sinxron chiqadi"},
                    {"num": "03", "tag": "FOLLOW-GATE", "text": "Izohda «SKILL» yozgan obunachiga 3s ichida Direct ketadi ✓", "active": True},
                ],
            },
            {
                "type": "cta_terminal",
                "duration": 2.8,
                "eyebrow": "BEPUL ARSENAL · @DIYOR.CTR",
                "headlineHtml": "Izohda <em>«SKILL»</em><br>deb yozing",
                "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — 3 soniyada Direct’ga yuboriladi!",
                "keyword": "SKILL",
            },
        ],
    }

    t1 = time.time()
    print("✂️ [2/4] 9:16 50/50 Split-Screen Reel (1080×1920, $0 ovoz klonisiz) render qilinmoqda...")
    split_meta = await compose_split_screen_reel(
        split_spec,
        split_mp4,
        camera_video_path=None,  # Uses v4 sharp DIYOR PT 2.5D breathing portrait; accepts any real camera .mp4 too!
        speaker_title="Diyor · @diyor.ctr",
        role_sub="AI & VIBE CODING ARXITEKTORI",
        fps=30,
        with_clawd=True,
    )
    split_elapsed = round(time.time() - t1, 1)
    print(f"   ✓ 50/50 Split-Screen tayyor ({split_elapsed}s): {split_mp4.name} ({split_mp4.stat().st_size/(1024*1024):.2f} MB)")

    # Extract verification PNG frames into SSD Vault so we can visually inspect!
    ffmpeg_bin = get_ffmpeg_bin()
    wide_f1 = out_dir / "verify_wide_s1_hook_clawd.png"
    wide_f2 = out_dir / "verify_wide_s2_code_arch.png"
    split_f1 = out_dir / "verify_split_50x50_clawd.png"
    subprocess.run([ffmpeg_bin, "-y", "-ss", "1.6", "-i", str(wide_mp4), "-frames:v", "1", str(wide_f1)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([ffmpeg_bin, "-y", "-ss", "6.8", "-i", str(wide_mp4), "-frames:v", "1", str(wide_f2)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([ffmpeg_bin, "-y", "-ss", "1.6", "-i", str(split_mp4), "-frames:v", "1", str(split_f1)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Create ZIP bundle in SSD Vault
    zip_path = VAULT_MEDIA / "scale_zero_cost_v5.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(wide_mp4, wide_mp4.name)
        zf.write(split_mp4, split_mp4.name)

    # ------------------------------------------------------------------
    # 3. UPLOAD TO GOFILE + LITTERBOX CDN & PUSH TO @diyor937373839337bot
    # ------------------------------------------------------------------
    print("☁️ [3/4] GoFile + Litterbox CDN va @diyor937373839337bot ga yuklanmoqda...")
    c_wide = await asyncio.to_thread(upload_file_to_cloud, wide_mp4, f"scale_zero_cost_v5/{wide_mp4.name}")
    c_split = await asyncio.to_thread(upload_file_to_cloud, split_mp4, f"scale_zero_cost_v5/{split_mp4.name}")
    c_zip = await asyncio.to_thread(upload_file_to_cloud, zip_path, "scale_zero_cost_v5.zip")

    sec = load_tg_secret()
    cid = sec.get("chat_id")
    if cid:
        await asyncio.to_thread(
            tg_send_message,
            cid,
            "⚡ <b>@diyor.ctr — $0-Cost Tashqi Render & Katta Formatlar (v5) Tayyor!</b>\n\n"
            "✅ <b>1. Parallel Render + Modal.com ($0/oy, $30 bepul kredit)</b> ko‘prigi o‘rnatildi\n"
            "✅ <b>2. 16:9 YouTube / Widescreen (1920×1080)</b> ikki ustunli + jonli kod terilishi (`code_architecture`) + `Clawd`\n"
            "✅ <b>3. 9:16 50/50 Split-Screen Reel (1080×1920)</b> — ovoz klonisiz ($0!), yuqorida Claude Motion, pastda jonli kamera yoki v4 2.5D studiya\n"
            "✅ <b>4. Cloudflare R2 ($0 / 10GB) + Meta Content Publishing API ($0)</b> avtomatik ko‘prigi ulandi!\n"
            "⏸ <i>Ovoz klonlash (ElevenLabs) topshirig‘ingizga binoan keyingi bosqichga qoldirildi.</i>\n\n"
            "👇 Quyida ikkala yangi formatdagi tayyor videolarni qabul qiling:"
        )
        await asyncio.to_thread(
            upload_to_telegram_vault,
            wide_mp4,
            f"scale_zero_cost_v5/{wide_mp4.name}",
            "🖥 16:9 YouTube / Prezentatsiya Widescreen (1920×1080 · 3-oqimli Parallel Render · Clawd · -14.5 LUFS)",
            cid,
            True,
        )
        await asyncio.to_thread(
            upload_to_telegram_vault,
            split_mp4,
            f"scale_zero_cost_v5/{split_mp4.name}",
            "✂️ 9:16 50/50 Split-Screen Reel (1080×1920 · Ovoz klonisiz $0 · Yuqorida Claude Motion + Pastda 2.5D Studiya)\n💡 Botga istalgan kamera video + izohda `split Sarlavha | SKILL` yuborsangiz, ovozingiz bilan 50/50 Reel yasab qaytaradi!",
            cid,
            True,
        )

    summary = {
        "wide_16x9": {**wide_meta, "elapsed_sec": wide_elapsed, "cdn": c_wide.get("direct_cdn_url"), "gofile": c_wide.get("gofile_page")},
        "split_9x16": {**split_meta, "elapsed_sec": split_elapsed, "cdn": c_split.get("direct_cdn_url"), "gofile": c_split.get("gofile_page")},
        "bundle_zip_gofile": c_zip.get("gofile_page"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("✅ [4/4] BARCHASI MUVAFFAQIYATLI YAKUNLANDI!")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
