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


def build_autopilot_blueprint(topic: str, keyword: str = "SKILL", target_duration: float = 10.0) -> dict[str, Any]:
    """Builds coherent Uzbek Hook, TechBrief Motion Scenes (short 10s OR full 40s+ 6-scene story), Voiceover Script, and Caption."""
    clean_topic = re.sub(r"\s+", " ", (topic or "Bir kishilik AI-Imperiya").strip())
    kw = re.sub(r"[^A-Za-z0-9_]", "", (keyword or "SKILL").upper())[:14] or "SKILL"
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
    bp = build_autopilot_blueprint(topic, keyword, target_duration=target_duration)
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
    min_floor = max(float(target_duration or 10.0), 42.0) if is_long else 7.2
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
    hook_dur = 3.2 if is_long else 2.5
    rem_dur = max(38.8 if is_long else 4.6, round(vo_dur - hook_dur, 2))

    whisper_task = asyncio.create_task(transcribe_uzbek_via_modal(vo_16k))
    cover_task = asyncio.create_task(
        render_brand_photo_slide(portrait, cover_4x5_png, config=bp["hook_config"], aspect="4:5")
    )
    hook_frames_task = asyncio.create_task(
        render_brand_photo_parallax_frames(portrait, config=bp["hook_config"], aspect="9:16", duration=hook_dur, fps=30)
    )

    w_res, _, hook_frames = await asyncio.gather(whisper_task, cover_task, hook_frames_task)
    vo_16k.unlink(missing_ok=True)

    # 3. Render 9:16 Full-Frame v4 Hook + Claude TechBrief Multi-Scene Story + Clawd
    await _emit("🎬 <b>5-qadam:</b> 9:16 Claude TechBrief ko‘p-sahnali kadrlar render qilinmoqda...")
    raw_mp4 = out_dir / "tmp_raw_reel.mp4"
    s1 = bp["scene1"]

    if is_long:
        # 6 rich authored TechBrief chapters after 3.2s v4 3D Hook = 7 distinct visual chapters (~43-47s total!)
        d1 = round(rem_dur * 0.16, 2)
        d2 = round(rem_dur * 0.19, 2)
        d3 = round(rem_dur * 0.17, 2)
        d4 = round(rem_dur * 0.18, 2)
        d5 = round(rem_dur * 0.14, 2)
        d6 = round(rem_dur - (d1 + d2 + d3 + d4 + d5), 2)
        scenes_payload = [
            {
                "type": "hook_stat",
                "duration": d1,
                "eyebrow": s1["eyebrow"],
                "headlineHtml": s1["headlineHtml"],
                "subtext": s1["subtext"],
                "statLabel": s1["statLabel"],
                "statValue": s1["statValue"],
                "statSuffix": "%",
                "barPercent": s1["statValue"],
            },
            {
                "type": "pipeline_dm",
                "duration": d2,
                "eyebrow": "02 · AVTONOM ZANJIR",
                "headlineHtml": "3 bosqichli <em>AI-imperiya</em><br>ishlash arxitekturasi",
                "steps": [
                    {
                        "num": "01 · Ssenariy va Strategiya",
                        "title": "Claude AI g‘oya va kontent rejasini tuzadi",
                        "desc": "Auditoriya og‘rig‘ini topib, viral ssenariy yaratadi",
                        "accent": False,
                    },
                    {
                        "num": "02 · Vibe Coding MVP",
                        "title": "Dasturchisiz 48 soatda tayyor raqamli tizim",
                        "desc": "Claude Skills kod va dizaynni avtonom yig‘adi",
                        "accent": False,
                    },
                    {
                        "num": f"03 · Aqlli Follow-Gate («{kw}»)",
                        "title": "Har bir izohga 3 soniyada Direct javob",
                        "desc": "Obunani tekshiradi va qo‘llanmani avto-yuboradi",
                        "accent": True,
                    },
                ],
            },
            {
                "type": "code_architecture",
                "duration": d3,
                "eyebrow": "03 · VIBE CODING · $0 STACK",
                "headlineHtml": "Kod yozmasdan <em>48 soatda</em><br>tayyor mahsulot",
                "fileName": f"imperiya_{kw.lower()}.py · $0 STACK",
                "codeLines": [
                    "# @diyor.ctr · 1-Kishilik AI-Imperiya",
                    "agent = ClaudeSkill(model='sonnet-4.6')",
                    "mvp = agent.vibe_build(hours=48, cost=0)",
                    f"gate = SmartFollowGate(keyword='{kw}')",
                    "gate.run_24_7(reply_sec=3, auto_dm=True)",
                ],
                "subtext": "Server va jamoa xarajatisiz 24/7 bulutli avtopilot.",
            },
            {
                "type": "scorecard_bars",
                "duration": d4,
                "eyebrow": "04 · SAMARADORLIK TAHLILI",
                "headlineHtml": "Natija <em>raqamlarda</em>:<br>to‘liq avtopilot kuchi",
                "score": 98,
                "bars": [
                    {"label": "Ishga tushirish tezligi (48s)", "value": 96},
                    {"label": "Direct avto-javob aniqligi", "value": 99},
                    {"label": "Jamoa xarajati tejalishi", "value": s1["statValue"]},
                ],
            },
            {
                "type": "hook_stat",
                "duration": d5,
                "eyebrow": "05 · 24/7 MASSHTAB",
                "headlineHtml": "Uxlayotganingizda ham<br><em>sotuv to‘xtamaydi</em>",
                "subtext": "Har bir izoh va obunachi bilan 3 soniyada shaxsiy muloqot.",
                "statLabel": "KECHAYU KUNDUZ AVTOPILOT REJIMI",
                "statValue": 24,
                "statSuffix": "/7",
                "barPercent": 100,
            },
            {
                "type": "cta_terminal",
                "duration": d6,
                "eyebrow": "06 · BEPUL QO‘LLANMA · DIRECT",
                "headlineHtml": f"Izohda <em>«{kw}»</em><br>deb yozing",
                "subtext": "@diyor.ctr sahifasiga obuna bo‘ling — 3 soniyada Direct’ga yuboriladi!",
                "keyword": kw,
            },
        ]
    else:
        s1_dur = round(rem_dur * 0.56, 2)
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
            "theme": "lotion",
            "topicTag": f"ai · {kw.lower()} · @diyor.ctr",
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
