#!/usr/bin/env python3
"""
MODULE 2 (v5 Scale-Up Edition): @diyor.ctr Multi-Aspect Claude TechBrief Motion Engine
======================================================================================
Upgraded for Larger Projects at $0 Cost:
- Supports FOUR native formats from a single scene JSON schema:
  1. `4:5` (`1080×1350`) — Instagram Mixed-Media Carousel Motion Slides
  2. `9:16` (`1080×1920`) — Instagram Reels / YouTube Shorts (safe zone `y: 250..1670`)
  3. `16:9` (`1920×1080`) — `claude-wide` Two-Column Widescreen YouTube / Long-Form Presentations
  4. `split-top` (`1080×960`) — Top half of `50/50 Split-Screen` Real Camera + Claude Motion Reels
- Parallel Multi-Worker Chunked Rendering (`workers=3..4` concurrent isolated Playwright pages +
  lossless FFmpeg concat) for ~3x faster local rendering with <220 MB RAM footprint, plus seamless
  delegation to Modal.com Serverless Cloud (`$0/mo` Starter — `$30/mo` free credits) when configured!
- Preserves all authored `claude-techbrief` craft rules:
  `#FAF9F5` `--lotion` paper + `Fraunces` + `Inter 800` + `JetBrains Mono` + corner brackets + `@DIYOR.CTR`,
  shared `power2.inOut` easing, `svgOrigin`, vector checkmarks, pure-`t` deterministic timelines,
  `p5.brush` watercolour `Clawd` (zero text inside `Clawd`), and cut-locked `-14.5 LUFS` FX audio.
"""
from __future__ import annotations

import asyncio
import base64
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


def async_playwright():
    try:
        from playwright.async_api import async_playwright as _apw
    except ImportError:
        import subprocess
        subprocess.run(["python3", "/home/user/tashqi_xotira/bootstrap_env.py"], check=False)
        from playwright.async_api import async_playwright as _apw
    return _apw()

TB_ROOT = Path("/home/user/claude-techbrief")
SHARED_FONTS = TB_ROOT / "shared" / "fonts"
SHARED_VENDOR = TB_ROOT / "shared" / "vendor"
CLAWD_ROOT = TB_ROOT / "manba" / "clawd"

VAULT_ROOT = Path("/home/user/.cache/diyor_vault")
VAULT_TMP = VAULT_ROOT / "tmp"
CLAWD_SPRITE_BANK = VAULT_ROOT / "clawd_sprites_v1"
VAULT_TMP.mkdir(parents=True, exist_ok=True)


def resolve_dimensions(aspect: str) -> tuple[int, int]:
    if aspect == "16:9":
        return 1920, 1080
    if aspect == "split-top":
        return 1080, 960
    if aspect == "4:5":
        return 1080, 1350
    return 1080, 1920


def _safe_alpha_composite(base_im: Image.Image, spr_im: Image.Image, dx: int, dy: int) -> None:
    """Safely alpha-composites `spr_im` onto `base_im` at `(dx, dy)` even when negative or overflowing."""
    bw, bh = base_im.size
    sw, sh = spr_im.size
    src_x0 = max(0, -dx)
    src_y0 = max(0, -dy)
    dst_x0 = max(0, dx)
    dst_y0 = max(0, dy)
    copy_w = min(sw - src_x0, bw - dst_x0)
    copy_h = min(sh - src_y0, bh - dst_y0)
    if copy_w <= 0 or copy_h <= 0:
        return
    cropped = spr_im.crop((src_x0, src_y0, src_x0 + copy_w, src_y0 + copy_h))
    base_im.alpha_composite(cropped, dest=(dst_x0, dst_y0))


async def ensure_clawd_sprite_bank(sprite_fps: int = 10, clip_dur: float = 2.4) -> Path:
    """
    Renders authentic `p5.js` + `p5.brush.js` watercolour `Clawd` (`hook` + `outro` transparent RGBA frames)
    ONCE at hand-drawn boil rate (`10 fps`, 24 frames each = 48 frames total) into SSD Vault cache.
    """
    hook_dir = CLAWD_SPRITE_BANK / "hook"
    outro_dir = CLAWD_SPRITE_BANK / "outro"
    hook_dir.mkdir(parents=True, exist_ok=True)
    outro_dir.mkdir(parents=True, exist_ok=True)
    n_frames = int(round(clip_dur * sprite_fps))

    if len(list(hook_dir.glob("f*.png"))) >= n_frames and len(list(outro_dir.glob("f*.png"))) >= n_frames:
        return CLAWD_SPRITE_BANK

    print(f"[Clawd Bank] Pre-rendering {n_frames*2} watercolour RGBA sprites to SSD Vault (one-time)...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=[
            "--no-sandbox", "--allow-file-access-from-files",
            "--ignore-gpu-blocklist", "--use-angle=gl-egl", "--enable-gpu-rasterization",
        ])
        pg = await browser.new_page(viewport={"width": 1200, "height": 1000})
        c_url = f"file://{CLAWD_ROOT}/custom_overlay.html?render&variant=feed&dur=9.0&hook=0.30&outro=5.50"
        await pg.goto(c_url)
        for _ in range(45):
            if await pg.evaluate("window.ready === true"):
                break
            await pg.wait_for_timeout(150)

        for clip_name, t_base, out_d in [("hook", 0.30, hook_dir), ("outro", 5.50, outro_dir)]:
            for i in range(n_frames):
                fp = out_d / f"f{i:03d}.png"
                if fp.exists() and fp.stat().st_size > 400:
                    continue
                t = round(t_base + (i + 0.5) / float(sprite_fps), 3)
                durl = await pg.evaluate("t => window.renderAt(t, 'image/png')", t)
                fp.write_bytes(base64.b64decode(durl.split(",", 1)[1]))
            print(f"  ✓ Clawd '{clip_name}' {n_frames} RGBA sprites cached!", flush=True)

        await browser.close()
    return CLAWD_SPRITE_BANK


if str(TB_ROOT / "vositalar") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "vositalar"))
from _fxbed import build_fx_for_cuts  # noqa: E402


def get_ffmpeg_bin() -> str:
    f = shutil.which("ffmpeg")
    if f:
        return f
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    bins = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux")))
    return bins[-1] if bins else "ffmpeg"


def _theme_tokens(theme: str = "lotion") -> dict[str, str]:
    if theme == "warm":
        return {
            "bg": "#f4ede3",
            "surface": "#faf5ee",
            "surface2": "#ede3d4",
            "border": "#dfd2bf",
            "ink": "#141413",
            "ink2": "#2c2b26",
            "muted": "#666258",
            "accent": "#d97757",
            "accent_deep": "#a04a2c",
            "accent_soft": "#f5dfcf",
            "sage": "#2e6b52",
            "sage_soft": "#dfeee6",
        }
    return {
        "bg": "#faf9f5",
        "surface": "#f3f1ea",
        "surface2": "#ebe7dc",
        "border": "#e3dacc",
        "ink": "#141413",
        "ink2": "#2c2b26",
        "muted": "#666258",
        "accent": "#d97757",
        "accent_deep": "#a04a2c",
        "accent_soft": "#f6e4db",
        "sage": "#2e6b52",
        "sage_soft": "#dfeee6",
    }


def _common_head_css(W: int, H: int, aspect: str, tokens: dict[str, str]) -> str:
    fonts_dir = f"file://{SHARED_FONTS}"
    gsap_src = f"file://{SHARED_VENDOR}/gsap.min.js"

    if aspect == "16:9":
        pad_top, pad_bot, pad_x = 104, 114, 124
        corner_top, corner_bot, corner_side = 48, 48, 68
        h_size = 72
        sub_size = 24
        scene_layout_css = """
          display: grid; grid-template-columns: 1.02fr 0.98fr; gap: 74px; align-items: center;
        """
    elif aspect == "split-top":
        pad_top, pad_bot, pad_x = 46, 54, 62
        corner_top, corner_bot, corner_side = 26, 26, 36
        h_size = 56
        sub_size = 21
        scene_layout_css = "display: flex; flex-direction: column; justify-content: center;"
    elif aspect == "4:5":
        pad_top, pad_bot, pad_x = 86, 110, 76
        corner_top, corner_bot, corner_side = 48, 48, 56
        h_size = 76
        sub_size = 25
        scene_layout_css = "display: flex; flex-direction: column; justify-content: center;"
    else:  # 9:16
        pad_top, pad_bot, pad_x = 270, 420, 84
        corner_top, corner_bot, corner_side = 248, 380, 56
        h_size = 82
        sub_size = 25
        scene_layout_css = "display: flex; flex-direction: column; justify-content: center;"

    hud_left = corner_side + 26
    return f"""<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8" />
  <script src="{gsap_src}"></script>
  <style>
    @font-face {{ font-family: "Fraunces"; font-style: normal; font-weight: 100 900; src: url("{fonts_dir}/Fraunces-var-normal.woff2") format("woff2"); }}
    @font-face {{ font-family: "Fraunces"; font-style: italic; font-weight: 100 900; src: url("{fonts_dir}/Fraunces-var-italic.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-style: normal; font-weight: 400; src: url("{fonts_dir}/Inter-400.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-style: normal; font-weight: 500; src: url("{fonts_dir}/Inter-500.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-style: normal; font-weight: 600; src: url("{fonts_dir}/Inter-600.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-style: normal; font-weight: 700; src: url("{fonts_dir}/Inter-700.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-style: normal; font-weight: 800; src: url("{fonts_dir}/Inter-800.woff2") format("woff2"); }}
    @font-face {{ font-family: "JetBrains Mono"; font-style: normal; font-weight: 400; src: url("{fonts_dir}/JetBrainsMono-400.woff2") format("woff2"); }}
    @font-face {{ font-family: "JetBrains Mono"; font-style: normal; font-weight: 500; src: url("{fonts_dir}/JetBrainsMono-500.woff2") format("woff2"); }}

    :root {{
      --bg: {tokens['bg']}; --surface: {tokens['surface']}; --surface2: {tokens['surface2']};
      --border: {tokens['border']}; --ink: {tokens['ink']}; --ink2: {tokens['ink2']};
      --muted: {tokens['muted']}; --accent: {tokens['accent']}; --accent-deep: {tokens['accent_deep']};
      --accent-soft: {tokens['accent_soft']}; --sage: {tokens['sage']}; --sage-soft: {tokens['sage_soft']};
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{
      width: {W}px; height: {H}px; overflow: hidden; background: var(--bg); color: var(--ink);
      font-family: "Inter", sans-serif; -webkit-font-smoothing: antialiased;
    }}
    #root {{
      position: relative; width: {W}px; height: {H}px; overflow: hidden;
      background:
        radial-gradient(960px 660px at 32% 20%, rgba(217,119,87,0.11), transparent 64%),
        radial-gradient(880px 640px at 82% 84%, rgba(106,155,204,0.08), transparent 66%),
        var(--bg);
    }}
    .grid-bg {{
      position: absolute; inset: 0; pointer-events: none; z-index: 1;
      background-image:
        linear-gradient(to right, rgba(20,20,19,0.032) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(20,20,19,0.032) 1px, transparent 1px);
      background-size: 72px 72px;
      mask-image: radial-gradient(ellipse 84% 76% at 50% 48%, #000 45%, transparent 96%);
    }}
    .scene {{
      position: absolute; inset: 0; z-index: 3;
      padding: {pad_top}px {pad_x}px {pad_bot}px {pad_x}px;
      {scene_layout_css}
      opacity: 0; visibility: hidden;
    }}
    .col-l, .col-r {{ min-width: 0; width: 100%; }}
    .eyebrow {{
      display: inline-flex; align-items: center; gap: 12px; align-self: flex-start;
      padding: 8px 18px; border-radius: 999px; background: var(--surface); border: 1.5px solid var(--border);
      font-family: "JetBrains Mono", monospace; font-size: {14 if aspect == 'split-top' else 16}px; font-weight: 500;
      letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent-deep); margin-bottom: {16 if aspect == 'split-top' else 24}px;
    }}
    .eyebrow .dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--accent); }}
    .h-serif {{
      font-family: "Fraunces", Georgia, serif; font-weight: 520;
      font-variation-settings: "opsz" 144, "SOFT" 28, "WONK" 0;
      font-size: {h_size}px; line-height: 0.98; letter-spacing: -0.028em; color: var(--ink);
    }}
    .h-serif em {{ font-style: italic; font-weight: 480; color: #c1613f; padding-right: 0.12em; }}
    .sub-p {{
      margin-top: {12 if aspect == 'split-top' else 18}px; font-size: {sub_size}px; line-height: 1.42; color: var(--ink2); font-weight: 500; max-width: 880px;
    }}
    .card {{
      background: var(--surface); border: 1.5px solid var(--border); border-radius: 24px;
      padding: {20 if aspect == 'split-top' else 28}px {24 if aspect == 'split-top' else 32}px; box-shadow: 0 18px 44px rgba(20,20,19,0.06);
    }}
    .hud {{ position: absolute; inset: 0; z-index: 12; pointer-events: none; font-family: "JetBrains Mono", monospace; }}
    .corner {{ position: absolute; width: 24px; height: 24px; border: 1.5px solid rgba(20,20,19,0.28); }}
    .c-tl {{ left: {corner_side}px; top: {corner_top}px; border-right: 0; border-bottom: 0; }}
    .c-tr {{ right: {corner_side}px; top: {corner_top}px; border-left: 0; border-bottom: 0; }}
    .c-bl {{ left: {corner_side}px; bottom: {corner_bot}px; border-right: 0; border-top: 0; }}
    .c-br {{ right: {corner_side}px; bottom: {corner_bot}px; border-left: 0; border-top: 0; }}
    .hud-bot {{
      position: absolute; left: {hud_left}px; right: {hud_left}px; bottom: {corner_bot + 6}px;
      display: flex; justify-content: space-between; align-items: center;
      font-size: {15 if aspect == 'split-top' else 18}px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted);
    }}
    .hud-bot .sw {{ color: var(--accent-deep); font-weight: 500; }}
"""


def _wrap_scene_layout(aspect: str, sid: str, left_html: str, right_html: str) -> str:
    """In `16:9` (`claude-wide`), places narrative on the left column and evidence on the right column."""
    if aspect == "16:9":
        return f"""
        <section class="scene" id="{sid}">
          <div class="col-l">{left_html}</div>
          <div class="col-r">{right_html}</div>
        </section>
        """
    return f"""
    <section class="scene" id="{sid}">
      {left_html}
      {right_html}
    </section>
    """


def build_diyor_motion_html(spec: dict[str, Any]) -> tuple[str, list[float], float]:
    """
    Builds a deterministic GSAP `window.__timelines.main` motion HTML composition.
    Returns `(html_string, cut_timestamps, total_duration)`.
    """
    aspect = spec.get("aspect", "4:5")
    W, H = resolve_dimensions(aspect)
    is_wide = aspect == "16:9"
    is_compact = aspect == "split-top"
    tokens = _theme_tokens(spec.get("theme", "lotion"))
    topic_tag = spec.get("topicTag", "ai · avtopilot")
    handle = spec.get("handle", "@DIYOR.CTR")
    scenes = spec.get("scenes", [])

    cur_t = 0.0
    cuts: list[float] = []
    scene_html_blocks: list[str] = []
    js_blocks: list[str] = []

    for idx, sc in enumerate(scenes):
        dur = float(sc.get("duration", 2.8))
        t0 = round(cur_t, 3)
        t1 = round(cur_t + dur, 3)
        if idx > 0:
            cuts.append(t0)
        sid = f"sc_{idx}"
        stype = sc.get("type", "hook_stat")

        js_blocks.append(f'tl.set("#{sid}", {{ autoAlpha: 1 }}, {t0});')
        if idx < len(scenes) - 1:
            js_blocks.append(f'tl.set("#{sid}", {{ autoAlpha: 0 }}, {t1});')

        if stype == "hook_stat":
            val_num = float(sc.get("statValue", 94))
            val_suffix = sc.get("statSuffix", "%")
            bar_pct = min(100, max(12, int(sc.get("barPercent", val_num))))
            card_w = "100%" if is_wide else ("84%" if is_compact else "78%")
            card_mt = "0px" if is_wide else ("22px" if is_compact else "34px")
            left_h = f"""
              <div class="eyebrow"><span class="dot"></span>{sc.get("eyebrow", "MUAMMO VA YECHIM")}</div>
              <h1 class="h-serif s-hd">{sc.get("headlineHtml", "Mijoz yozganda<br><em>3 soniyada</em> javob")}</h1>
              <p class="sub-p s-sub">{sc.get("subtext", "Kechikkan har daqiqa — raqobatchiga ketgan issiq sotuv.")}</p>
            """
            right_h = f"""
              <div class="card s-card" style="margin-top:{card_mt}; width: {card_w};">
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:14px;">
                  <span style="font-family:'JetBrains Mono',monospace; font-size:15px; letter-spacing:0.16em; color:var(--muted); text-transform:uppercase;">{sc.get("statLabel", "KONVERSIYA SAQLANISHI")}</span>
                  <span style="font-family:'Inter',sans-serif; font-weight:800; font-size:{78 if is_wide else (52 if is_compact else 64)}px; letter-spacing:-0.04em; color:var(--ink);">
                    <span id="{sid}_num">0</span>{val_suffix}
                  </span>
                </div>
                <div style="height:16px; border-radius:999px; background:var(--surface2); overflow:hidden;">
                  <div id="{sid}_bar" style="width:0%; height:100%; border-radius:999px; background:linear-gradient(90deg, var(--accent), var(--accent-deep));"></div>
                </div>
              </div>
            """
            scene_html_blocks.append(_wrap_scene_layout(aspect, sid, left_h, right_h))
            js_blocks.append(f"""
              tl.fromTo("#{sid} .s-hd", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.42, ease: "power3.out" }}, {t0 + 0.04});
              tl.fromTo("#{sid} .s-sub", {{ y: 20, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.38, ease: "power3.out" }}, {t0 + 0.16});
              tl.fromTo("#{sid} .s-card", {{ y: 26, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.40, ease: "power3.out" }}, {t0 + 0.24});
              countNum("{sid}_num", {val_num}, {max(0.8, min(1.35, dur * 0.52)):.2f}, {t0 + 0.30});
              tl.to("#{sid}_bar", {{ width: "{bar_pct}%", duration: {max(0.8, min(1.35, dur * 0.52)):.2f}, ease: "power2.inOut" }}, {t0 + 0.30});
            """)

        elif stype == "pipeline_dm":
            steps = sc.get("steps", [
                {"tag": "01 · IZOH", "title": "Mijoz post ostiga «SKILL» deb yozadi", "meta": "Webhook · 0.4 soniya"},
                {"tag": "02 · FOLLOW-GATE", "title": "Obuna holati Graph API orqali tekshiriladi", "meta": "is_user_follow_business = true"},
                {"tag": "03 · DIRECT PDF", "title": "Qo‘llanma + AI saralash savoli yuboriladi", "meta": "24/7 Avtopilot · 0 xodim"},
            ])
            row_pad = "16px 20px" if is_compact else "22px 26px"
            row_mb = "12px" if is_compact else "16px"
            rows_html = []
            for r_i, st in enumerate(steps):
                rows_html.append(f"""
                <div class="card p-row p-r{r_i}" style="display:flex; align-items:center; gap:20px; padding:{row_pad}; margin-bottom:{row_mb};">
                  <div style="width:{44 if is_compact else 52}px; height:{44 if is_compact else 52}px; border-radius:14px; background:var(--sage-soft); display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <svg width="26" height="26" viewBox="0 0 28 28" fill="none">
                      <path id="{sid}_chk_{r_i}" d="M6 14.5L11.5 20L22 8.5" stroke="#2e6b52" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="32" stroke-dashoffset="32"/>
                    </svg>
                  </div>
                  <div style="flex:1;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:13px; letter-spacing:0.16em; color:var(--accent-deep); margin-bottom:3px;">{st.get('tag', f'0{r_i+1} · BOSQICH')}</div>
                    <div style="font-size:{20 if is_compact else 23}px; font-weight:700; letter-spacing:-0.02em; color:var(--ink);">{st.get('title') or st.get('text', '')}</div>
                  </div>
                  <div style="font-family:'JetBrains Mono',monospace; font-size:13px; color:var(--sage); background:var(--sage-soft); padding:6px 12px; border-radius:999px; white-space:nowrap;">{st.get('meta', '✓ FAOL')}</div>
                </div>
                """)
            left_h = f"""
              <div class="eyebrow"><span class="dot"></span>{sc.get("eyebrow", "AQLLI FOLLOW-GATE OQIMI")}</div>
              <h2 class="h-serif s-hd" style="font-size:{66 if is_wide else (50 if is_compact else 64)}px; margin-bottom:{0 if is_wide else (18 if is_compact else 28)}px;">{sc.get("headlineHtml", "Uch qadamli<br><em>avtomatik voronka</em>")}</h2>
              {f'<p class="sub-p s-sub">{sc.get("subtext", "")}</p>' if (is_wide and sc.get("subtext")) else ''}
            """
            right_h = f"<div>{''.join(rows_html)}</div>"
            scene_html_blocks.append(_wrap_scene_layout(aspect, sid, left_h, right_h))
            js_blocks.append(f'tl.fromTo("#{sid} .s-hd", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.36, ease: "power3.out" }}, {t0 + 0.04});')
            for r_i in range(len(steps)):
                rt = round(t0 + 0.22 + r_i * 0.38, 3)
                js_blocks.append(f"""
                  tl.fromTo("#{sid} .p-r{r_i}", {{ x: -28, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.36, ease: "power3.out" }}, {rt});
                  tl.to("#{sid}_chk_{r_i}", {{ strokeDashoffset: 0, duration: 0.34, ease: "power2.out" }}, {round(rt + 0.16, 3)});
                """)

        elif stype == "scorecard_bars":
            metrics = sc.get("metrics", [
                {"label": "Obunachi o‘sishi (Follow-Gate)", "val": 310, "suffix": "%", "pct": 92},
                {"label": "Javob tezligi (Direct AI)", "val": 3, "suffix": " soniya", "pct": 96},
                {"label": "Sotuvga tayyor issiq lidlar", "val": 42, "suffix": "%", "pct": 78},
            ])
            ring_score = int(sc.get("ringScore", 98))
            circum = 440
            target_off = round(circum * (1.0 - ring_score / 100.0), 1)
            m_rows = []
            for m_i, m in enumerate(metrics):
                m_rows.append(f"""
                <div style="margin-bottom:{14 if is_compact else 20}px;">
                  <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:7px;">
                    <span style="font-size:{18 if is_compact else 21}px; font-weight:600; color:var(--ink2);">{m['label']}</span>
                    <span style="font-family:'Inter',sans-serif; font-size:{24 if is_compact else 30}px; font-weight:800; color:var(--ink);"><span id="{sid}_mv_{m_i}">0</span>{m['suffix']}</span>
                  </div>
                  <div style="height:13px; border-radius:999px; background:var(--surface2); overflow:hidden;">
                    <div id="{sid}_mb_{m_i}" style="width:0%; height:100%; border-radius:999px; background:linear-gradient(90deg, var(--accent), #2e6b52);"></div>
                  </div>
                </div>
                """)
            ring_card = f"""
                <div class="card" style="padding:14px 20px; display:inline-flex; align-items:center; gap:16px; margin-top:{24 if is_wide else 0}px;">
                  <svg width="{96 if is_compact else 116}" height="{96 if is_compact else 116}" viewBox="0 0 180 180">
                    <circle cx="90" cy="90" r="70" stroke="var(--surface2)" stroke-width="14" fill="none"/>
                    <circle id="{sid}_ring" cx="90" cy="90" r="70" stroke="var(--accent)" stroke-width="14" stroke-linecap="round" fill="none" stroke-dasharray="{circum}" stroke-dashoffset="{circum}"/>
                    <text x="90" y="99" text-anchor="middle" font-family="Inter" font-weight="800" font-size="38" fill="var(--ink)" id="{sid}_rtxt">0</text>
                  </svg>
                  <div>
                    <div style="font-family:'JetBrains Mono',monospace; font-size:13px; letter-spacing:0.15em; color:var(--muted);">TIZIM BALLI</div>
                    <div style="font-size:22px; font-weight:800; color:var(--sage);">PRO · 24/7</div>
                  </div>
                </div>
            """
            if is_wide:
                left_h = f"""
                  <div class="eyebrow"><span class="dot"></span>{sc.get("eyebrow", "30 KUNLIK NATIJA · SCORECARD")}</div>
                  <h2 class="h-serif s-hd" style="font-size:66px;">{sc.get("headlineHtml", "Raqamlar<br><em>aldamaydi</em>")}</h2>
                  {ring_card}
                """
                right_h = f'<div class="card" style="width:100%;">{"".join(m_rows)}</div>'
            else:
                left_h = f"""
                  <div class="eyebrow"><span class="dot"></span>{sc.get("eyebrow", "30 KUNLIK NATIJA · SCORECARD")}</div>
                  <div style="display:flex; justify-content:space-between; align-items:center; gap:24px; margin-bottom:{16 if is_compact else 26}px;">
                    <h2 class="h-serif s-hd" style="font-size:{50 if is_compact else 62}px;">{sc.get("headlineHtml", "Raqamlar<br><em>aldamaydi</em>")}</h2>
                    {ring_card}
                  </div>
                """
                right_h = f'<div class="card" style="width:{92 if is_compact else 82}%;">{"".join(m_rows)}</div>'

            scene_html_blocks.append(_wrap_scene_layout(aspect, sid, left_h, right_h))
            js_blocks.append(f"""
              gsap.set("#{sid}_ring", {{ svgOrigin: "90 90", rotation: -90 }});
              tl.fromTo("#{sid} .s-hd", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.36, ease: "power3.out" }}, {t0 + 0.04});
              countNum("{sid}_rtxt", {ring_score}, 1.15, {t0 + 0.18});
              tl.to("#{sid}_ring", {{ strokeDashoffset: {target_off}, duration: 1.15, ease: "power2.inOut" }}, {t0 + 0.18});
            """)
            for m_i, m in enumerate(metrics):
                mt = round(t0 + 0.24 + m_i * 0.18, 3)
                js_blocks.append(f"""
                  countNum("{sid}_mv_{m_i}", {m['val']}, 1.05, {mt});
                  tl.to("#{sid}_mb_{m_i}", {{ width: "{m['pct']}%", duration: 1.05, ease: "power2.inOut" }}, {mt});
                """)

        elif stype == "code_architecture":
            import re as _re
            raw_lines = sc.get("codeLines", [
                "# @diyor.ctr — $0 Cloud Render + Follow-Gate Stack",
                "from modal_render_worker import render_slice_worker",
                "from cloud_render_bridge import upload_to_cloudflare_r2",
                "",
                "# 40 ta parallel konteyner · $0/oy Starter tier",
                "slices  = render_slice_worker.map(timeline_chunks)",
                "cdn_url = await upload_to_cloudflare_r2('reel_1080p.mp4')",
                "publish_to_instagram('@diyor.ctr', cdn_url, kw='SKILL')",
            ])
            clean_lines = [_re.sub(r"<[^>]+>", "", ln) for ln in raw_lines]
            full_code_str = "\n".join(clean_lines)
            steps_arr = ", ".join(json.dumps(full_code_str[:k]) for k in range(4, len(full_code_str) + 1, max(1, len(full_code_str) // 36)))
            if not steps_arr.endswith(json.dumps(full_code_str)):
                steps_arr += (", " if steps_arr else "") + json.dumps(full_code_str)
            left_h = f"""
              <div class="eyebrow"><span class="dot"></span>{sc.get("eyebrow", "CLOUD RENDER ARXITEKTURASI")}</div>
              <h2 class="h-serif s-hd" style="font-size:{66 if is_wide else (50 if is_compact else 68)}px;">{sc.get("headlineHtml", "Yengil kod —<br><em>bulutli quvvat</em>")}</h2>
              <p class="sub-p s-sub">{sc.get("subtext", "Og‘ir video render va saqlash 0$ bepul bulut API’larga taqsimlanadi.")}</p>
            """
            right_h = f"""
              <div class="card s-term" style="margin-top:{0 if is_wide else 24}px; width:{'100%' if is_wide else '90%'}; background:#141413; color:#faf9f5; border-color:#2c2b26; padding:26px 30px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                  <div style="display:flex; gap:8px;">
                    <span style="width:11px; height:11px; border-radius:50%; background:#d97757;"></span>
                    <span style="width:11px; height:11px; border-radius:50%; background:#d4a27f;"></span>
                    <span style="width:11px; height:11px; border-radius:50%; background:#2e6b52;"></span>
                  </div>
                  <span style="font-family:'JetBrains Mono',monospace; font-size:13px; letter-spacing:0.15em; color:#a8a299;">{sc.get("fileName", "pipeline.py")} · {sc.get("badge", "$0 STACK")}</span>
                </div>
                <pre id="{sid}_code" style="font-family:'JetBrains Mono',monospace; font-size:{18 if is_wide else 16}px; line-height:1.58; color:#f3f1ea; white-space:pre-wrap; min-height:170px;"></pre>
              </div>
            """
            scene_html_blocks.append(_wrap_scene_layout(aspect, sid, left_h, right_h))
            js_blocks.append(f"""
              tl.fromTo("#{sid} .s-hd", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.36, ease: "power3.out" }}, {t0 + 0.04});
              tl.fromTo("#{sid} .s-term", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.38, ease: "power3.out" }}, {t0 + 0.16});
              typeCode("{sid}_code", [{steps_arr}], {max(0.9, dur * 0.58):.2f}, {t0 + 0.22});
            """)

        else:  # cta_terminal
            kw = sc.get("keyword", "SKILL")
            term_w = "100%" if is_wide else ("84%" if is_compact else "74%")
            left_h = f"""
              <div class="eyebrow"><span class="dot"></span>{sc.get("eyebrow", "BEPUL ARXITEKTURA · DIRECT")}</div>
              <h2 class="h-serif s-hd">{sc.get("headlineHtml", "Tayyor sxemani<br><em>Direct’dan</em> oling")}</h2>
              <p class="sub-p s-sub" style="max-width:740px;">{sc.get("subtext", "Avval @diyor.ctr sahifasiga obuna bo‘ling va izohda maxfiy so‘zni qoldiring:")}</p>
            """
            right_h = f"""
              <div class="card s-term" style="margin-top:{0 if is_wide else (20 if is_compact else 30)}px; width: {term_w}; background:#141413; color:#faf9f5; border-color:#2c2b26; padding:{22 if is_compact else 30}px 34px;">
                <div style="font-family:'JetBrains Mono',monospace; font-size:14px; letter-spacing:0.18em; color:#a8a299; margin-bottom:14px;">🔒 FOLLOW-GATE · AVTO-JAVOB TERMINAL</div>
                <div style="display:flex; align-items:center; gap:14px; font-family:'JetBrains Mono',monospace; font-size:{38 if is_compact else 44}px; font-weight:500; color:#faf9f5;">
                  <span style="color:#d97757;">❯</span>
                  <span id="{sid}_kw"></span><span style="display:inline-block; width:18px; height:{38 if is_compact else 44}px; background:#d97757;"></span>
                </div>
              </div>
            """
            scene_html_blocks.append(_wrap_scene_layout(aspect, sid, left_h, right_h))
            chars_js = ", ".join(json.dumps(kw[: i + 1]) for i in range(len(kw)))
            js_blocks.append(f"""
              tl.fromTo("#{sid} .s-hd", {{ y: 24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.36, ease: "power3.out" }}, {t0 + 0.04});
              tl.fromTo("#{sid} .s-term", {{ y: 24, opacity: 0, scale: 0.97 }}, {{ y: 0, opacity: 1, scale: 1.0, duration: 0.38, ease: "power3.out" }}, {t0 + 0.18});
              typeKw("{sid}_kw", [{chars_js}], 0.65, {t0 + 0.34});
            """)

        cur_t += dur

    total_dur = round(cur_t, 3)
    head_css = _common_head_css(W, H, aspect, tokens)
    full_html = f"""{head_css}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{total_dur}" data-width="{W}" data-height="{H}">
    <div class="grid-bg"></div>
    {"".join(scene_html_blocks)}
    <div class="hud">
      <div class="corner c-tl"></div><div class="corner c-tr"></div>
      <div class="corner c-bl"></div><div class="corner c-br"></div>
      <div class="hud-bot">
        <span class="sw">↗ {topic_tag}</span>
        <span>{handle}</span>
      </div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    function countNum(id, toVal, dur, startT) {{
      const el = document.getElementById(id), proxy = {{ _v: 0 }};
      Object.defineProperty(proxy, "v", {{ get() {{ return this._v; }}, set(x) {{ this._v = x; if (el) el.textContent = Math.round(x); }} }});
      tl.to(proxy, {{ v: toVal, duration: dur, ease: "power2.inOut" }}, startT);
    }}
    function typeKw(id, steps, dur, startT) {{
      const el = document.getElementById(id), proxy = {{ _v: 0 }};
      Object.defineProperty(proxy, "v", {{
        get() {{ return this._v; }},
        set(x) {{
          this._v = x;
          const k = Math.min(steps.length, Math.max(0, Math.ceil(x)));
          if (el) el.textContent = k > 0 ? steps[k - 1] : "";
        }}
      }});
      tl.to(proxy, {{ v: steps.length, duration: dur, ease: "none" }}, startT);
    }}
    function colorizePy(raw) {{
      return raw.split("\\n").map(line => {{
        const esc = line.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
        if (esc.trim().startsWith("#")) return '<span style="color:#8f8a80;">' + esc + '</span>';
        return esc
          .replace(/('[^']*'|"[^"]*")/g, '<span style="color:#7bc4a4;">$1</span>')
          .replace(/\\b(from|import|await|async|def|return)\\b/g, '<span style="color:#e89072;font-weight:600;">$1</span>');
      }}).join("\\n");
    }}
    function typeCode(id, steps, dur, startT) {{
      const el = document.getElementById(id);
      const proxy = {{ _v: 0 }};
      Object.defineProperty(proxy, "v", {{
        get() {{ return this._v; }},
        set(x) {{
          this._v = x;
          const k = Math.min(steps.length, Math.max(0, Math.ceil(x)));
          if (el) el.innerHTML = k > 0 ? colorizePy(steps[k - 1]) : "";
        }}
      }});
      tl.to(proxy, {{ v: steps.length, duration: dur, ease: "none" }}, startT);
    }}
    {"".join(js_blocks)}
    window.__timelines = {{ main: tl }};
  </script>
</body>
</html>"""
    return full_html, cuts, total_dur


def _clawd_dest_for_canvas(W: int, H: int) -> tuple[int, int]:
    """Computes clean `(dx, dy)` for the `1080×1350` Clawd RGBA sprite across all 4 canvas sizes."""
    if W >= 1800:  # 16:9 (1920x1080)
        return 740, -125
    if H <= 1000:  # split-top (1080x960) -> sits cleanly at y=665..877 below stat card & above @DIYOR.CTR!
        return -10, -175
    if H <= 1400:  # 4:5 (1080x1350)
        return 0, 36
    return 0, 435  # 9:16 (1080x1920)


async def _render_frame_chunk_to_mp4(
    playwright_instance: Any,
    html_url: str,
    W: int,
    H: int,
    f_start: int,
    f_end: int,
    fps: int,
    chunk_mp4: Path,
    ffmpeg_bin: str,
    with_clawd: bool,
    hook_t: float,
    outro_start: float,
    clip_dur: float,
    sprite_fps: int,
    hook_paths: list[Path],
    outro_paths: list[Path],
    clawd_dx: int,
    clawd_dy: int,
) -> Path:
    browser = await playwright_instance.chromium.launch(args=[
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
    ])
    try:
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        page = await ctx.new_page()
        await page.goto(html_url, wait_until="networkidle")
        await page.evaluate("document.fonts.ready")

        cmd = [
            ffmpeg_bin, "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
            str(chunk_mp4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        last_spr_path: Path | None = None
        last_spr_im: Image.Image | None = None
        for f_idx in range(f_start, f_end):
            t = f_idx / float(fps)
            await page.evaluate("t => { const tl = window.__timelines.main; tl.pause(); tl.seek(t, false); }", t)
            jpg_bytes = await page.screenshot(type="jpeg", quality=92)
            base_im = Image.open(io.BytesIO(jpg_bytes))

            if with_clawd:
                sp: Path | None = None
                if hook_t <= t < hook_t + clip_dur and hook_paths:
                    si = min(len(hook_paths) - 1, int((t - hook_t) * sprite_fps))
                    sp = hook_paths[si]
                elif outro_start <= t < outro_start + clip_dur and outro_paths:
                    si = min(len(outro_paths) - 1, int((t - outro_start) * sprite_fps))
                    sp = outro_paths[si]
                if sp is not None:
                    if sp != last_spr_path:
                        last_spr_path = sp
                        last_spr_im = Image.open(sp).convert("RGBA")
                    if last_spr_im is not None:
                        base_im = base_im.convert("RGBA")
                        _safe_alpha_composite(base_im, last_spr_im, clawd_dx, clawd_dy)

            proc.stdin.write(base_im.convert("RGB").tobytes())

        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        rc = proc.wait()
        await ctx.close()
        if rc != 0:
            raise RuntimeError(f"Chunk encode failed ({rc}): {err[-300:]}")
        return chunk_mp4
    finally:
        await browser.close()


async def render_html_timeline_to_mp4(
    html_path: Path,
    out_mp4: Path,
    cuts: list[float] | None = None,
    fps: int = 30,
    with_clawd: bool = False,
    hook_t: float = 0.30,
    outro_t: float | None = None,
    prepend_rgb_frames: list[bytes] | None = None,
    parallel_workers: int = 3,
    lufs_target: float = -14.5,
) -> dict[str, Any]:
    """
    Parallel Multi-Worker GSAP + optional Clawd watercolour RGBA overlay + `-14.5 LUFS` FX muxer.
    Automatically delegates to Modal.com Serverless Cloud (`$0/mo` Starter) if configured via
    `cloud_render_bridge`, otherwise distributes frames across `parallel_workers` concurrent Chromium
    contexts locally with lossless FFmpeg stream-concat!
    """
    # Optional Modal Cloud delegation if user connected a Modal Webhook URL
    try:
        from cloud_render_bridge import try_modal_webhook_render
        modal_res = await try_modal_webhook_render(
            html_path=html_path,
            out_mp4=out_mp4,
            cuts=cuts or [],
            fps=fps,
            with_clawd=with_clawd,
            prepend_rgb_frames=prepend_rgb_frames,
            lufs_target=lufs_target,
        )
        if modal_res is not None:
            return modal_res
    except Exception:
        pass

    ffmpeg_bin = get_ffmpeg_bin()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    html_url = f"file://{html_path.resolve()}"

    async with async_playwright() as p:
        probe_browser = await p.chromium.launch(args=[
            "--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage", "--disable-gpu",
        ])
        probe_pg = await probe_browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        await probe_pg.goto(html_url, wait_until="networkidle")
        meta = await probe_pg.evaluate("""() => {
            const root = document.getElementById('root');
            const tl = window.__timelines && window.__timelines.main;
            const dsDur = root && root.dataset.duration ? parseFloat(root.dataset.duration) : 0;
            const tlDur = tl ? tl.duration() : 5.0;
            const dur = (dsDur > 0) ? dsDur : (tlDur < 3600 ? tlDur : 10.0);
            const w = root && root.dataset.width ? parseInt(root.dataset.width, 10) : 1080;
            const h = root && root.dataset.height ? parseInt(root.dataset.height, 10) : 1350;
            return { dur, w, h };
        }""")
        await probe_browser.close()

        W, H, html_dur = int(meta["w"]), int(meta["h"]), float(meta["dur"])
        prep_frames = prepend_rgb_frames or []
        prep_dur = len(prep_frames) / float(fps)
        total_dur = round(prep_dur + html_dur, 3)

        sprite_fps = 10
        clip_dur = 2.4
        hook_paths: list[Path] = []
        outro_paths: list[Path] = []
        outro_start = outro_t if outro_t is not None else max(3.0, html_dur - clip_dur - 0.15)
        if with_clawd:
            bank = await ensure_clawd_sprite_bank(sprite_fps=sprite_fps, clip_dur=clip_dur)
            hook_paths = sorted((bank / "hook").glob("f*.png"))
            outro_paths = sorted((bank / "outro").glob("f*.png"))
        clawd_dx, clawd_dy = _clawd_dest_for_canvas(W, H)

        n_html_frames = int(round(html_dur * fps))
        cpu_cap = max(1, os.cpu_count() or 2)
        n_workers = max(1, min(int(parallel_workers), cpu_cap, max(1, n_html_frames // 45)))
        shifted_cuts = ([round(prep_dur, 3)] if prep_dur > 0 else []) + [round(prep_dur + c, 3) for c in (cuts or [])]

        with tempfile.TemporaryDirectory(prefix="tb_par_", dir=str(VAULT_TMP)) as tmpdir:
            tdir = Path(tmpdir)
            chunk_files: list[Path] = []

            if prep_frames:
                prep_mp4 = tdir / "chunk_000_prep.mp4"
                pcmd = [
                    ffmpeg_bin, "-y",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                    "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                    str(prep_mp4),
                ]
                pproc = subprocess.Popen(pcmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                assert pproc.stdin is not None
                for item in prep_frames:
                    if len(item) == W * H * 3:
                        pproc.stdin.write(item)
                    else:
                        pproc.stdin.write(Image.open(io.BytesIO(item)).convert("RGB").tobytes())
                pproc.stdin.close()
                if pproc.wait() != 0:
                    raise RuntimeError("Prepend chunk encode failed")
                chunk_files.append(prep_mp4)

            tasks = []
            step = max(1, (n_html_frames + n_workers - 1) // n_workers)
            for w_idx in range(n_workers):
                f0 = w_idx * step
                f1 = min(n_html_frames, (w_idx + 1) * step)
                if f0 >= f1:
                    continue
                c_mp4 = tdir / f"chunk_{w_idx + 1:03d}.mp4"
                chunk_files.append(c_mp4)
                tasks.append(
                    _render_frame_chunk_to_mp4(
                        p, html_url, W, H, f0, f1, fps, c_mp4, ffmpeg_bin,
                        with_clawd, hook_t, outro_start, clip_dur, sprite_fps,
                        hook_paths, outro_paths, clawd_dx, clawd_dy,
                    )
                )

            await asyncio.gather(*tasks)

            wav_path = str(tdir / "fx.wav")
            build_fx_for_cuts(total_dur, shifted_cuts, wav_path, lufs_target=lufs_target)

            concat_txt = tdir / "chunks.txt"
            concat_txt.write_text("\n".join(f"file '{cf.resolve()}'" for cf in chunk_files) + "\n", encoding="utf-8")

            mux_cmd = [
                ffmpeg_bin, "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-i", wav_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", "-shortest",
                str(out_mp4),
            ]
            subprocess.run(mux_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    return {
        "output": str(out_mp4),
        "width": W,
        "height": H,
        "duration": total_dur,
        "fps": fps,
        "workers_used": n_workers,
        "render_backend": "local_parallel_chromium",
        "with_clawd": with_clawd,
        "lufs": lufs_target,
        "cuts": shifted_cuts,
    }


async def render_diyor_motion_mp4(
    spec: dict[str, Any],
    out_mp4: Path,
    fps: int = 30,
    with_clawd: bool = True,
    prepend_rgb_frames: list[bytes] | None = None,
    parallel_workers: int = 3,
) -> dict[str, Any]:
    html_str, cuts, _ = build_diyor_motion_html(spec)
    tmp_html = VAULT_TMP / f".tmp_diyor_motion_{os.getpid()}_{id(spec)}.html"
    tmp_html.write_text(html_str, encoding="utf-8")
    try:
        return await render_html_timeline_to_mp4(
            tmp_html,
            out_mp4,
            cuts=cuts,
            fps=fps,
            with_clawd=with_clawd,
            prepend_rgb_frames=prepend_rgb_frames,
            parallel_workers=parallel_workers,
        )
    finally:
        tmp_html.unlink(missing_ok=True)


async def render_static_editorial_slide(slide_spec: dict[str, Any], out_png: Path) -> str:
    """
    Renders a static `4:5` (`1080×1350`), `9:16` (`1080×1920`), or `16:9` (`1920×1080`) editorial slide.
    """
    aspect = slide_spec.get("aspect", "4:5")
    W, H = resolve_dimensions(aspect)
    tokens = _theme_tokens(slide_spec.get("theme", "lotion"))
    head_css = _common_head_css(W, H, aspect, tokens)
    kind = slide_spec.get("kind", "architecture")
    slide_idx = slide_spec.get("slideIndex", "03 / 05")
    topic_tag = slide_spec.get("topicTag", "tizim · sxema")
    handle = slide_spec.get("handle", "@DIYOR.CTR")

    if kind == "architecture":
        nodes = slide_spec.get("nodes", [
            {"num": "01", "tag": "TRIGGER · REELS / POST", "title": "Mijoz izohda kalit so‘zni yozadi", "desc": "Masalan: «SKILL» yoki «TIZIM» — algoritm izohlar soni hisobiga postni Explore’ga itaradi."},
            {"num": "02", "tag": "TEKSHIRUV · GRAPH API", "title": "Aqlli Follow-Gate obunani tekshiradi", "desc": "Obuna bo‘lmagan foydalanuvchiga shaxsiy tugma chiqadi — obunaga konversiya 3.1x oshadi."},
            {"num": "03", "tag": "KONVERSIYA · CLAUDE MCP", "title": "PDF qo‘llanma + 2 savolli AI saralash", "desc": "Claude mijoz budjeti va muammosini aniqlab, tayyor issiq lidni CRM’ga uzatadi."},
        ])
        cards = []
        for i, nd in enumerate(nodes):
            arrow = '<div style="text-align:center; color:var(--accent); font-size:24px; margin:6px 0;">↓</div>' if i < len(nodes) - 1 else ""
            cards.append(f"""
            <div class="card" style="display:flex; gap:22px; align-items:flex-start; padding:24px 28px;">
              <div style="width:54px; height:54px; border-radius:16px; background:var(--accent-soft); color:var(--accent-deep); font-family:'JetBrains Mono',monospace; font-weight:700; font-size:20px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">{nd['num']}</div>
              <div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:13px; letter-spacing:0.16em; color:var(--accent-deep); margin-bottom:4px;">{nd['tag']}</div>
                <div style="font-size:25px; font-weight:800; letter-spacing:-0.02em; color:var(--ink); margin-bottom:6px;">{nd['title']}</div>
                <div style="font-size:19px; line-height:1.42; color:var(--ink2);">{nd['desc']}</div>
              </div>
            </div>{arrow}
            """)
        body_inner = f"""
        <div class="scene" style="opacity:1; visibility:visible; display:flex; flex-direction:column; justify-content:center;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; width:100%;">
            <div class="eyebrow" style="margin-bottom:0;"><span class="dot"></span>{slide_spec.get("eyebrow", "TIZIM ARXITEKTURASI")}</div>
            <span style="font-family:'JetBrains Mono',monospace; font-size:16px; letter-spacing:0.18em; color:var(--muted);">{slide_idx}</span>
          </div>
          <h1 class="h-serif" style="font-size:66px; margin-bottom:26px;">{slide_spec.get("headlineHtml", "Bitta postdan<br><em>issiq sotuvgacha</em> yo‘l")}</h1>
          <div style="width:100%;">{"".join(cards)}</div>
        </div>
        """
    else:  # cta slide
        kw = slide_spec.get("keyword", "SKILL")
        perks = slide_spec.get("perks", [
            "8-sahifali to‘liq AI + Follow-Gate sxemasi (PDF)",
            "7 ta yuqori konversiyali avto-javob skripti",
            "Claude MCP orqali mijoz saralash shabloni",
        ])
        perk_rows = "".join([
            f"""<div style="display:flex; align-items:center; gap:14px; margin-bottom:14px; font-size:22px; font-weight:600; color:var(--ink2);">
              <svg width="26" height="26" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="13" fill="#dfeee6"/><path d="M8 14.5L12.2 18.8L20 10.2" stroke="#2e6b52" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span>{pk}</span>
            </div>""" for pk in perks
        ])
        body_inner = f"""
        <div class="scene" style="opacity:1; visibility:visible; display:flex; flex-direction:column; justify-content:center;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; width:100%;">
            <div class="eyebrow" style="margin-bottom:0;"><span class="dot"></span>{slide_spec.get("eyebrow", "BEPUL QO‘LLANMA · DIRECT")}</div>
            <span style="font-family:'JetBrains Mono',monospace; font-size:16px; letter-spacing:0.18em; color:var(--muted);">{slide_idx}</span>
          </div>
          <h1 class="h-serif" style="font-size:72px; margin-bottom:18px;">{slide_spec.get("headlineHtml", "Izohda <em>«SKILL»</em><br>deb yozing")}</h1>
          <p class="sub-p" style="margin-top:0; margin-bottom:28px;">{slide_spec.get("subtext", "Avval @diyor.ctr sahifasiga obuna bo‘ling — Aqlli Follow-Gate qo‘llanmani 3 soniyada Direct’ga yuboradi.")}</p>
          <div class="card" style="margin-bottom:26px; width:100%;">{perk_rows}</div>
          <div class="card" style="width:100%; background:#141413; color:#faf9f5; border-color:#2c2b26; display:flex; justify-content:space-between; align-items:center; padding:26px 32px;">
            <div>
              <div style="font-family:'JetBrains Mono',monospace; font-size:13px; letter-spacing:0.18em; color:#a8a299; margin-bottom:6px;">MAXFIY SO‘ZNI IZOHDA QOLDIRING</div>
              <div style="font-family:'JetBrains Mono',monospace; font-size:42px; font-weight:700; color:#faf9f5;"><span style="color:#d97757;">❯</span> {kw}</div>
            </div>
            <div style="background:#d97757; color:#faf9f5; font-weight:800; font-size:20px; padding:16px 26px; border-radius:16px;">Saqlab qo‘ying ↗</div>
          </div>
        </div>
        """

    html_doc = f"""{head_css}
  </style>
</head>
<body>
  <div id="root">
    <div class="grid-bg"></div>
    {body_inner}
    <div class="hud">
      <div class="corner c-tl"></div><div class="corner c-tr"></div>
      <div class="corner c-bl"></div><div class="corner c-br"></div>
      <div class="hud-bot">
        <span class="sw">↗ {topic_tag}</span>
        <span>{handle}</span>
      </div>
    </div>
  </div>
</body>
</html>"""

    out_png.parent.mkdir(parents=True, exist_ok=True)
    tmp_html = VAULT_TMP / f".tmp_static_{os.getpid()}_{id(slide_spec)}.html"
    tmp_html.write_text(html_doc, encoding="utf-8")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
            page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            await page.goto(f"file://{tmp_html}", wait_until="networkidle")
            await page.evaluate("document.fonts.ready")
            await page.screenshot(path=str(out_png), type="png")
            await browser.close()
    finally:
        tmp_html.unlink(missing_ok=True)

    return str(out_png)
