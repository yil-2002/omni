#!/usr/bin/env python3
"""
✂️ @diyor.ctr — $0-Cost 50/50 Split-Screen Real Camera + Claude Motion Composer
===============================================================================
Ovoz klonisiz ($0 xarajat!) haqiqiy jonli ekspert + dasturiy animatsiya formati:
- YUQORI YARIM (`1080×960`): `motion_engine.py` (`aspect="split-top"`) orqali `#FAF9F5` Claude TechBrief
  jonli hisoblagich, vektor sxema, kod yozilishi, SVG halqa va akvarel `Clawd` maskoti;
- PASTKI YARIM (`1080×960`):
  * Agar foydalanuvchi telefonda yozilgan haqiqiy `.mp4`/`.mov` kamera videosini bersa —
    uning haqiqiy ovozi 100% saqlanadi va ostiga `-21 dB` mayin TechBrief UI tovushlari qo‘shiladi!
  * Agar kamera videosi berilmasa — `IMG_2860.jpeg` asosida silliq `2.5D` nafas oluvchi studiya
    kadri (`v4` tiniq `DIYOR PT`) + `-14.5 LUFS` FX ovoz avtomatik yig‘iladi!
- O‘RTADA: `3px` terrakota (`#D97757`) ajratuvchi chiziq + pastda shishasimon `@DIYOR.CTR` spiker nishoni!
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if str(TB_ROOT / "vositalar") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "vositalar"))

from motion_engine import get_ffmpeg_bin, render_diyor_motion_mp4, VAULT_TMP  # noqa: E402
from photo_brand_engine import analyze_photo_layout  # noqa: E402


def _has_audio_stream(ffmpeg_bin: str, video_path: Path) -> bool:
    proc = subprocess.run([ffmpeg_bin, "-i", str(video_path)], capture_output=True, text=True)
    info = (proc.stderr or "") + (proc.stdout or "")
    return "Audio:" in info


def _build_speaker_badge_overlay(width: int = 1080, height: int = 1920, speaker_title: str = "Diyor · @diyor.ctr", role_sub: str = "AI & VIBE CODING ARXITEKTORI") -> Image.Image:
    """Builds a crisp RGBA overlay containing the 3px terracotta split line + bottom speaker glass pill."""
    ov = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)

    # 3px Terracotta split line at y = 960
    draw.rectangle([0, 958, width, 962], fill=(217, 119, 87, 255))

    # Subtle bottom gradient vignette so Instagram Reels caption/UI never clashes
    for y in range(1600, height):
        alpha = int(175 * ((y - 1600) / float(height - 1600)) ** 1.4)
        draw.line([(0, y), (width, y)], fill=(14, 14, 13, min(190, alpha)))

    # Speaker nameplate pill at y = 1752..1846 (centered over shirt chest, 100% below DIYOR PT wall letters!)
    bx0, by0, bx1, by1 = 270, 1752, 810, 1846
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=24, fill=(250, 249, 245, 238), outline=(227, 218, 204, 255), width=2)
    # Terracotta live dot
    draw.ellipse([bx0 + 24, by0 + 28, bx0 + 40, by0 + 44], fill=(217, 119, 87, 255))

    font_bold_path = TB_ROOT / "shared" / "fonts" / "Inter-800.woff2"
    try:
        # Pillow loads TTF/OTF; fallback gracefully if woff2 isn't supported by FreeType build
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 27)
        f_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    except Exception:
        f_title = ImageFont.load_default()
        f_sub = ImageFont.load_default()
    _ = font_bold_path

    draw.text((bx0 + 54, by0 + 18), speaker_title, fill=(20, 20, 19, 255), font=f_title)
    draw.text((bx0 + 54, by0 + 58), role_sub, fill=(160, 74, 44, 255), font=f_sub)
    return ov


def _build_bottom_portrait_mp4(
    photo_path: Path,
    duration: float,
    fps: int,
    out_bottom_mp4: Path,
    ffmpeg_bin: str,
) -> Path:
    """
    If no live camera `.mp4` is uploaded yet, creates a smooth `1080×960` 2.5D breathing studio bottom clip
    from Diyor's portrait (`v4` sharp `DIYOR PT` clean plate + subtle outward subject zoom).
    """
    clean_bg, cutout, _ = analyze_photo_layout(photo_path, aspect="4:5")
    # Crop 1080x1350 cleanly around Diyor's face & DIYOR PT wall (`y = 70..1030` -> `1080x960`)
    bg_960 = clean_bg.crop((0, 70, 1080, 1030)).convert("RGBA")
    fg_960 = cutout.crop((0, 70, 1080, 1030)).convert("RGBA")

    n_frames = max(1, int(round(duration * fps)))
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x960", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
        str(out_bottom_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    for i in range(n_frames):
        prog = i / float(max(1, n_frames - 1))
        # Smooth gentle breathing zoom 1.0 -> 1.032 on subject only (zero ghosting!)
        sc = 1.0 + 0.032 * prog
        nw, nh = int(round(1080 * sc)), int(round(960 * sc))
        fg_scaled = fg_960.resize((nw, nh), Image.Resampling.BILINEAR)
        ox = (nw - 1080) // 2
        oy = int((nh - 960) * 0.42)
        fg_crop = fg_scaled.crop((ox, oy, ox + 1080, oy + 960))
        comp = bg_960.copy()
        comp.alpha_composite(fg_crop)
        proc.stdin.write(comp.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("Bottom 2.5D portrait clip failed")
    return out_bottom_mp4


async def compose_split_screen_reel(
    scenes_spec: dict[str, Any],
    out_mp4: Path,
    camera_video_path: Path | None = None,
    photo_fallback_path: Path = Path("/home/user/uploads/IMG_2860.jpeg"),
    speaker_title: str = "Diyor · @diyor.ctr",
    role_sub: str = "AI & VIBE CODING ARXITEKTORI",
    fps: int = 30,
    with_clawd: bool = True,
) -> dict[str, Any]:
    """
    Renders top `1080×960` Claude TechBrief animation + stacks bottom `1080×960` camera/portrait video
    into a final `1080×1920` `30fps` Split-Screen Reel!
    """
    ffmpeg_bin = get_ffmpeg_bin()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="split_5050_", dir=str(VAULT_TMP)) as tmpdir:
        td = Path(tmpdir)
        top_mp4 = td / "top_motion_960.mp4"
        top_spec = {
            **scenes_spec,
            "aspect": "split-top",
            "handle": scenes_spec.get("handle", "@DIYOR.CTR"),
        }
        top_res = await render_diyor_motion_mp4(top_spec, top_mp4, fps=fps, with_clawd=with_clawd, parallel_workers=3)
        dur = float(top_res["duration"])

        overlay_png = td / "badge_overlay.png"
        _build_speaker_badge_overlay(1080, 1920, speaker_title=speaker_title, role_sub=role_sub).save(overlay_png)

        use_real_cam = camera_video_path is not None and camera_video_path.exists()
        cam_has_audio = use_real_cam and _has_audio_stream(ffmpeg_bin, camera_video_path)  # type: ignore[arg-type]

        if use_real_cam:
            bottom_input = str(camera_video_path)
            bottom_in_args = ["-stream_loop", "-1", "-i", bottom_input]
        else:
            bot_mp4 = td / "bottom_portrait_960.mp4"
            _build_bottom_portrait_mp4(photo_fallback_path, dur, fps, bot_mp4, ffmpeg_bin)
            bottom_in_args = ["-i", str(bot_mp4)]

        # Filter complex:
        # [0:v] is top 1080x960 motion (with audio [0:a] at -14.5 LUFS)
        # [1:v] is bottom camera/portrait -> scale/crop to 1080x960
        # [2:v] is crisp 1080x1920 RGBA divider + speaker badge
        v_filter = (
            f"[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,fps={fps},setsar=1[bot];"
            f"[0:v][bot]vstack=inputs=2[stacked];"
            f"[stacked][2:v]overlay=0:0:format=auto[vout]"
        )
        if cam_has_audio:
            # Keep speaker's real voice primary + duck TechBrief UI FX to -18 dB underneath!
            a_filter = "[0:a]volume=0.12[fx];[1:a]aresample=48000,volume=1.0[voice];[voice][fx]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            audio_map = ["-map", "[aout]"]
            full_filter = f"{v_filter};{a_filter}"
        else:
            full_filter = v_filter
            audio_map = ["-map", "0:a"]

        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(top_mp4),
            *bottom_in_args,
            "-i", str(overlay_png),
            "-filter_complex", full_filter,
            "-map", "[vout]",
            *audio_map,
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            str(out_mp4),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    return {
        "output": str(out_mp4),
        "width": 1080,
        "height": 1920,
        "duration": dur,
        "fps": fps,
        "mode": "real_camera_50_50" if use_real_cam else "portrait_2.5d_50_50",
        "workers_used": top_res.get("workers_used", 3),
    }
