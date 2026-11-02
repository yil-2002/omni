#!/usr/bin/env python3
"""
🎞️ @diyor.ctr — Topic-Aware Editorial Image & HD B-Roll Video Fetcher (`topic_media_engine.py`)
===============================================================================================
Automatically pulls topic-relevant visual media ($0.00, zero API key required out of the box,
plus optional Pexels/Pixabay API key support):
  1. Moving HD B-Roll Videos (`.mp4`):
     - Optional Pexels / Pixabay HD Vertical/Horizontal Video API (if env key set)
     - Mixkit Free Commercial-Safe Stock HD MP4 (`assets.mixkit.co` 720p/1080p — zero key!)
     - Wikimedia Commons Free Video API fallback
  2. Topic Editorial Images (`.jpg` / `.png` -> base64 data URI):
     - Live article OpenGraph (`og:image`) from top web results
     - Wikimedia Commons / Wikipedia `1280px` real photography
     - Pollinations Flux HD editorial visual fallback
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

MEDIA_CACHE_DIR = Path("/home/user/.cache/diyor_vault/topic_media_cache")


def _slug_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:14]


def image_file_to_editorial_data_url(img_path: Path, target_w: int = 960, target_h: int = 560) -> str:
    im = Image.open(img_path).convert("RGB")
    im = ImageOps.fit(im, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.42))
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(0.96)).enhance(1.05)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _make_fallback_editorial_graphic(query: str, out_jpg: Path, w: int = 960, h: int = 560) -> Path:
    im = Image.new("RGB", (w, h), (24, 23, 21))
    d = ImageDraw.Draw(im)
    for x in range(0, w, 48):
        d.line([(x, 0), (x, h)], fill=(38, 36, 33), width=1)
    for y in range(0, h, 48):
        d.line([(0, y), (w, y)], fill=(38, 36, 33), width=1)
    d.ellipse([w // 2 - 220, h // 2 - 180, w // 2 + 220, h // 2 + 180], outline=(217, 119, 87), width=3)
    d.ellipse([w // 2 - 130, h // 2 - 100, w // 2 + 130, h // 2 + 100], outline=(46, 107, 82), width=2)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_jpg, format="JPEG", quality=90)
    return out_jpg


async def fetch_topic_editorial_image(
    english_query: str,
    candidate_page_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Returns `{"ok": True, "path": str, "data_url": str, "source": str}` for the topic's editorial photo card.
    """
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    q_clean = re.sub(r"[^A-Za-z0-9 \-]+", " ", (english_query or "artificial intelligence technology")).strip() or "technology business"
    cached_jpg = MEDIA_CACHE_DIR / f"img_{_slug_hash(q_clean)}.jpg"
    if cached_jpg.exists() and cached_jpg.stat().st_size > 8_000:
        return {
            "ok": True,
            "path": str(cached_jpg),
            "data_url": image_file_to_editorial_data_url(cached_jpg),
            "source": "Cache · HD",
        }

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) DiyorStudio/2.0"}
    timeout = aiohttp.ClientTimeout(total=8.0)

    async with aiohttp.ClientSession(timeout=timeout) as sess:
        # 1. Try real OpenGraph `og:image` from top live article URLs first (authentic breaking-news visual!)
        for page_u in (candidate_page_urls or [])[:3]:
            try:
                async with sess.get(page_u, headers=headers) as rp:
                    if rp.status != 200:
                        continue
                    ht = await rp.text(errors="ignore")
                    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']', ht, flags=re.I)
                    if not m:
                        m = re.search(r'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image["\']', ht, flags=re.I)
                    if m:
                        img_u = m.group(1)
                        async with sess.get(img_u, headers=headers) as ri:
                            if ri.status == 200:
                                raw_b = await ri.read()
                                if len(raw_b) >= 18_000:
                                    im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                                    if im.width >= 480 and im.height >= 280:
                                        im.save(cached_jpg, format="JPEG", quality=92)
                                        dom = urllib.parse.urlparse(page_u).netloc.replace("www.", "")
                                        return {
                                            "ok": True,
                                            "path": str(cached_jpg),
                                            "data_url": image_file_to_editorial_data_url(cached_jpg),
                                            "source": dom[:24] or "Web News",
                                        }
            except Exception:
                continue

        # 2. Try Wikimedia Commons `1280px` real photography
        for attempt_q in (q_clean, " ".join(q_clean.split()[:2]), "modern technology computer"):
            try:
                wm_u = (
                    "https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6"
                    f"&gsrsearch={urllib.parse.quote('filetype:bitmap ' + attempt_q)}&gsrlimit=6"
                    "&prop=imageinfo&iiprop=url|size&iiurlwidth=1280&format=json"
                )
                async with sess.get(wm_u, headers={"User-Agent": "DiyorStudio/2.0 (https://diyor.ctr)"}) as rw:
                    if rw.status == 200:
                        wd = await rw.json()
                        pages = list((wd.get("query") or {}).get("pages", {}).values())
                        for p in pages:
                            info = (p.get("imageinfo") or [{}])[0]
                            tu = info.get("thumburl") or info.get("url")
                            w_px, h_px = int(info.get("width") or 0), int(info.get("height") or 0)
                            if tu and w_px >= 600 and h_px >= 360 and not str(tu).lower().endswith(".svg"):
                                async with sess.get(tu, headers={"User-Agent": "DiyorStudio/2.0 (https://diyor.ctr)"}) as ri:
                                    if ri.status == 200:
                                        raw_b = await ri.read()
                                        if len(raw_b) >= 15_000:
                                            im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                                            im.save(cached_jpg, format="JPEG", quality=92)
                                            return {
                                                "ok": True,
                                                "path": str(cached_jpg),
                                                "data_url": image_file_to_editorial_data_url(cached_jpg),
                                                "source": "Wikimedia HD",
                                            }
            except Exception:
                continue

        # 3. Pollinations Flux HD Editorial Image Fallback ($0, zero key)
        try:
            flux_prompt = urllib.parse.quote(f"editorial minimalist photography of {q_clean}, warm natural studio lighting, high detail, no text")
            pol_u = f"https://image.pollinations.ai/prompt/{flux_prompt}?width=1024&height=600&nologo=true&seed=42"
            async with sess.get(pol_u, headers=headers) as rp:
                if rp.status == 200:
                    raw_b = await rp.read()
                    if len(raw_b) >= 15_000:
                        im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                        im.save(cached_jpg, format="JPEG", quality=92)
                        return {
                            "ok": True,
                            "path": str(cached_jpg),
                            "data_url": image_file_to_editorial_data_url(cached_jpg),
                            "source": "AI Visual · HD",
                        }
        except Exception:
            pass

    _make_fallback_editorial_graphic(q_clean, cached_jpg)
    return {
        "ok": True,
        "path": str(cached_jpg),
        "data_url": image_file_to_editorial_data_url(cached_jpg),
        "source": "@diyor.ctr Visual",
    }


async def fetch_topic_broll_video(english_query: str, avoid_urls: set[str] | None = None) -> dict[str, Any] | None:
    """
    Downloads a real commercial-safe 720p/1080p MP4 B-roll video matching `english_query` ($0, zero key!):
      1. Optional Pexels API (if `PEXELS_API_KEY` env var is present)
      2. Mixkit Free Stock HD MP4 (`assets.mixkit.co/videos/...-720.mp4` — zero key!)
    """
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    avoid = avoid_urls or set()
    q_clean = re.sub(r"[^A-Za-z0-9 \-]+", " ", (english_query or "technology laptop coding")).strip() or "technology laptop"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    timeout = aiohttp.ClientTimeout(total=14.0)

    candidate_queries = [
        q_clean,
        " ".join(q_clean.split()[:2]),
        "artificial intelligence technology",
        "business office laptop",
    ]

    async with aiohttp.ClientSession(timeout=timeout) as sess:
        # 1. Optional Pexels Video API if user configured `PEXELS_API_KEY`
        px_key = os.getenv("PEXELS_API_KEY", "").strip()
        if px_key:
            try:
                px_u = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(q_clean)}&per_page=5&orientation=landscape"
                async with sess.get(px_u, headers={"Authorization": px_key}) as rpx:
                    if rpx.status == 200:
                        pd = await rpx.json()
                        for v in (pd.get("videos") or []):
                            for vf in (v.get("video_files") or []):
                                link = vf.get("link") or ""
                                if link and link not in avoid and vf.get("file_type") == "video/mp4" and 540 <= int(vf.get("width") or 0) <= 1920:
                                    out_mp4 = MEDIA_CACHE_DIR / f"broll_{_slug_hash(link)}.mp4"
                                    if not out_mp4.exists() or out_mp4.stat().st_size < 40_000:
                                        async with sess.get(link, headers=headers) as dl:
                                            if dl.status == 200:
                                                out_mp4.write_bytes(await dl.read())
                                    if out_mp4.exists() and out_mp4.stat().st_size >= 40_000:
                                        avoid.add(link)
                                        return {"ok": True, "path": str(out_mp4), "url": link, "source": "Pexels HD B-Roll"}
            except Exception:
                pass

        # 2. Zero-key Mixkit Free Stock HD MP4 (`assets.mixkit.co`)
        for cq in candidate_queries:
            if not cq:
                continue
            try:
                search_u = f"https://mixkit.co/free-stock-video/search/?q={urllib.parse.quote_plus(cq)}"
                async with sess.get(search_u, headers=headers) as rs:
                    if rs.status != 200:
                        continue
                    ht = await rs.text(errors="ignore")
                    # Prefer 720p MP4 (fast 3-7 MB download, razor-sharp inside 912x510 card!) then 1080p/large
                    hits_720 = re.findall(r"https://assets\.mixkit\.co/videos/\d+/\d+-720\.mp4", ht)
                    hits_other = re.findall(r"https://assets\.mixkit\.co/videos/\d+/\d+-(?:1080|large|360)\.mp4", ht)
                    seen_u: list[str] = []
                    for u in hits_720 + hits_other:
                        if u not in seen_u and u not in avoid:
                            seen_u.append(u)
                    for chosen_u in seen_u[:3]:
                        out_mp4 = MEDIA_CACHE_DIR / f"broll_{_slug_hash(chosen_u)}.mp4"
                        if not out_mp4.exists() or out_mp4.stat().st_size < 40_000:
                            async with sess.get(chosen_u, headers=headers) as dl:
                                if dl.status == 200:
                                    data = await dl.read()
                                    if len(data) >= 40_000:
                                        out_mp4.write_bytes(data)
                        if out_mp4.exists() and out_mp4.stat().st_size >= 40_000:
                            avoid.add(chosen_u)
                            return {"ok": True, "path": str(out_mp4), "url": chosen_u, "source": "HD B-Roll"}
            except Exception:
                continue
    return None


def build_rounded_alpha_mask_png(out_png: Path, w: int, h: int, radius: int = 24) -> Path:
    """Creates an 8x supersampled anti-aliased rounded-rectangle alpha mask for FFmpeg `alphamerge`."""
    scale = 4
    big = Image.new("L", (w * scale, h * scale), 0)
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([0, 0, w * scale - 1, h * scale - 1], radius=radius * scale, fill=255)
    mask = big.resize((w, h), resample=Image.Resampling.LANCZOS)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    mask.save(out_png, format="PNG")
    return out_png


def composite_broll_windows_onto_mp4(
    ffmpeg_bin: str,
    base_mp4: Path,
    out_mp4: Path,
    broll_windows: list[dict[str, Any]],
    fps: int = 30,
) -> Path:
    """
    Overlays one or more rounded-corner 30fps HD B-Roll video clips directly into their exact
    editorial card windows `(x, y, w, h, t_start, t_end)` on `base_mp4`!
    """
    valid = [w for w in broll_windows if w.get("video_path") and Path(w["video_path"]).exists()]
    if not valid:
        if base_mp4 != out_mp4:
            out_mp4.write_bytes(base_mp4.read_bytes())
        return out_mp4

    mask_dir = MEDIA_CACHE_DIR / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg_bin, "-y", "-i", str(base_mp4)]
    filter_parts: list[str] = []
    cur_v = "[0:v]"

    for idx, win in enumerate(valid):
        vp = str(win["video_path"])
        cx, cy = int(win["x"]), int(win["y"])
        cw, ch = int(win["w"]), int(win["h"])
        rad = int(win.get("radius", 24))
        t0 = max(0.0, float(win["t_start"]))
        t1 = max(t0 + 0.4, float(win["t_end"]))
        dur = round(t1 - t0 + 0.5, 2)

        mask_png = mask_dir / f"rmask_{cw}x{ch}_r{rad}.png"
        if not mask_png.exists():
            build_rounded_alpha_mask_png(mask_png, cw, ch, rad)

        # Input indices: base=0, then for each idx: broll=(1 + 2*idx), mask=(2 + 2*idx)
        in_v = 1 + 2 * idx
        in_m = 2 + 2 * idx
        cmd += ["-stream_loop", "-1", "-t", str(dur), "-i", vp, "-loop", "1", "-t", str(dur), "-i", str(mask_png)]

        # Center-crop B-roll to card size, subtle editorial contrast, shift PTS to `t0`, merge rounded alpha mask, fade in!
        filter_parts.append(
            f"[{in_v}:v]fps={fps},scale={cw}:{ch}:force_original_aspect_ratio=increase,"
            f"crop={cw}:{ch},eq=contrast=1.04:saturation=0.95,format=yuv420p[bv{idx}]"
        )
        filter_parts.append(f"[{in_m}:v]scale={cw}:{ch},format=gray[bm{idx}]")
        filter_parts.append(
            f"[bv{idx}][bm{idx}]alphamerge,fade=t=in:st=0:d=0.28:alpha=1,"
            f"setpts=PTS-STARTPTS+{t0:.3f}/TB[bov{idx}]"
        )
        nxt_v = f"[vo{idx}]"
        filter_parts.append(
            f"{cur_v}[bov{idx}]overlay={cx}:{cy}:enable='between(t,{t0:.3f},{t1:.3f})':eof_action=pass{nxt_v}"
        )
        cur_v = nxt_v

    cmd += [
        "-filter_complex", ";".join(filter_parts),
        "-map", cur_v, "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return out_mp4
