#!/usr/bin/env python3
"""
🎞️ @diyor.ctr — Hyper-Exact Topic Image, Real Video & 3-Shot Cinema Montage Engine (`topic_media_engine.py`)
=============================================================================================================
Automatically pulls 100% topic-specific visual media ($0.00, zero API key required):
  1. Exact Real-World Press & Product HD Photos (`Bing HD Photo Search` -> `News og:image` -> `Wikimedia 1280px` -> `Flux`):
     - Deduplicated across every scene via `avoid_urls` so every card shows a DIFFERENT real photo!
     - Strict watermark/clipart/template domain blocker.
  2. Hyper-Relevant Moving HD B-Roll Videos (`.mp4`):
     - Optional Pexels HD Video API (`PEXELS_API_KEY`)
     - Wikimedia Commons Real Topic Video (`filetype:video` `.webm`/`.mp4` -> `720p` H.264)
     - Smart Exact-Subject Mixkit HD `720p` (NEVER blind-falls back to generic unrelated office clips!)
     - 3-Shot Cinema Press Documentary Montage (`build_cinema_press_montage_mp4` — 3 distinct real press photos
       animated at `30fps` with optical zoom, pan, and documentary shutter cuts for exact brands/CEOs/gadgets!).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import html as _html
import io
import os
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

MEDIA_CACHE_DIR = Path("/home/user/.cache/diyor_vault/topic_media_cache")

_BLOCKED_IMG_TOKENS = (
    "shutterstock", "istockphoto", "gettyimages", "depositphotos", "123rf",
    "dreamstime", "vecteezy", "alamy", "bigstock", "canstock", "clipart",
    "worksheet", "template", "coloring", "pinterest.", "svg", ".gif", "logo-png",
    "magnific", "freepik", "stockcake", "watermark", "preview",
)

_SPECIFIC_ENTITY_TOKENS = {
    "openai", "altman", "chatgpt", "gpt", "sora", "apple", "iphone", "ipad", "macbook",
    "airpods", "siri", "tesla", "optimus", "cybertruck", "robotaxi", "elon", "musk",
    "spacex", "starlink", "neuralink", "nvidia", "blackwell", "rubin", "huang", "tsmc",
    "deepseek", "anthropic", "claude", "google", "gemini", "deepmind", "microsoft",
    "copilot", "meta", "zuckerberg", "instagram", "whatsapp", "telegram", "durov",
    "tiktok", "samsung", "galaxy", "xiaomi", "huawei", "byd", "amazon", "netflix",
    "bitcoin", "uzbekistan", "tashkent", "toshkent", "dubai",
}

_PHYSICAL_VIDEO_SUBJECT_MAP: list[tuple[tuple[str, ...], str]] = [
    (("optimus", "humanoid", "robot", "robotics", "boston dynamics", "android robot"), "humanoid robot"),
    (("chip", "microchip", "semiconductor", "wafer", "processor", "gpu", "tsmc", "nvidia", "blackwell"), "microchip processor"),
    (("iphone", "smartphone", "mobile phone", "galaxy", "xiaomi", "ios", "android", "telegram", "instagram", "tiktok"), "smartphone screen"),
    (("tesla", "cybertruck", "robotaxi", "byd", "electric car", "autonomous car", "driving"), "electric car"),
    (("spacex", "starlink", "rocket", "satellite", "orbit", "mars", "nasa", "space"), "space rocket"),
    (("server", "data center", "cloud", "supercomputer", "cluster"), "server data center"),
    (("drone", "uav", "flying"), "drone flight"),
    (("neuralink", "brain", "medical", "surgery", "dna", "health", "hospital"), "medical laboratory"),
    (("bitcoin", "crypto", "stock", "trading", "trillion", "billion", "market", "finance"), "financial stock market"),
    (("code", "coding", "python", "developer", "programming", "software", "github"), "software developer coding"),
]


def _slug_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:14]


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_version() and imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def image_file_to_editorial_data_url(img_path: Path, target_w: int = 960, target_h: int = 560) -> str:
    im = Image.open(img_path).convert("RGB")
    im = ImageOps.fit(im, (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.38))
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(0.98)).enhance(1.05)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=91)
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


def _is_clean_photo_url(u: str) -> bool:
    lo = u.lower()
    if not lo.startswith(("http://", "https://")):
        return False
    return not any(tok in lo for tok in _BLOCKED_IMG_TOKENS)


async def fetch_bing_hd_topic_images(
    english_query: str,
    max_count: int = 3,
    avoid_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Pulls up to `max_count` distinct, real-world press/product/keynote HD photos directly from
    Bing Image Search (`form=HDRSC2`) with watermark/clipart filtering and `avoid_urls` deduplication.
    """
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    avoid = avoid_urls if avoid_urls is not None else set()
    q_clean = re.sub(r"[^A-Za-z0-9 \-]+", " ", (english_query or "technology")).strip() or "technology news"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    search_u = (
        f"https://www.bing.com/images/search?q={urllib.parse.quote_plus(q_clean)}"
        "&qft=+filterui:photo-photo+filterui:imagesize-large&form=HDRSC2&first=1"
    )
    results: list[dict[str, Any]] = []
    timeout = aiohttp.ClientTimeout(total=9.0)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(search_u, headers=headers) as rs:
                if rs.status != 200:
                    return []
                raw_html = await rs.text(errors="ignore")

            murls = [_html.unescape(u) for u in re.findall(r"murl&quot;:&quot;(https?://[^&]+?)&quot;", raw_html)]
            if len(murls) < max_count:
                # Retry without strict size filter if query was super niche
                u2 = f"https://www.bing.com/images/search?q={urllib.parse.quote_plus(q_clean)}&form=HDRSC2&first=1"
                async with sess.get(u2, headers=headers) as rs2:
                    if rs2.status == 200:
                        h2 = await rs2.text(errors="ignore")
                        for extra_u in re.findall(r"murl&quot;:&quot;(https?://[^&]+?)&quot;", h2):
                            eu = _html.unescape(extra_u)
                            if eu not in murls:
                                murls.append(eu)

            for img_u in murls[:22]:
                if len(results) >= max_count:
                    break
                if img_u in avoid or not _is_clean_photo_url(img_u):
                    continue
                cached_jpg = MEDIA_CACHE_DIR / f"bimg_{_slug_hash(img_u)}.jpg"
                dom = urllib.parse.urlparse(img_u).netloc.replace("www.", "")[:22] or "Press HD"
                if cached_jpg.exists() and cached_jpg.stat().st_size >= 16_000:
                    avoid.add(img_u)
                    results.append({
                        "ok": True,
                        "path": str(cached_jpg),
                        "url": img_u,
                        "data_url": image_file_to_editorial_data_url(cached_jpg),
                        "source": dom,
                    })
                    continue

                try:
                    async with sess.get(img_u, headers=headers, timeout=aiohttp.ClientTimeout(total=4.5)) as ri:
                        if ri.status != 200:
                            continue
                        ctype = (ri.headers.get("Content-Type") or "").lower()
                        if "svg" in ctype or "gif" in ctype or "html" in ctype:
                            continue
                        raw_b = await ri.read()
                        if len(raw_b) < 18_000:
                            continue
                        im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                        if im.width < 560 or im.height < 330:
                            continue
                        # Reject near-blank solid white/black placeholder images
                        extrema = im.resize((32, 32)).getextrema()
                        if all((hi - lo) < 18 for (lo, hi) in extrema):
                            continue
                        im.save(cached_jpg, format="JPEG", quality=92)
                        avoid.add(img_u)
                        results.append({
                            "ok": True,
                            "path": str(cached_jpg),
                            "url": img_u,
                            "data_url": image_file_to_editorial_data_url(cached_jpg),
                            "source": dom,
                        })
                except Exception:
                    continue
    except Exception:
        pass

    return results


async def fetch_topic_editorial_image(
    english_query: str,
    candidate_page_urls: list[str] | None = None,
    avoid_urls: set[str] | None = None,
) -> dict[str, Any]:
    """
    Returns `{"ok": True, "path": str, "data_url": str, "source": str}` for the topic's editorial photo card:
      Tier 1: Bing Real-World Press/Product HD Photo Search (`avoid_urls`-deduplicated!)
      Tier 2: Live article OpenGraph `og:image`
      Tier 3: Wikimedia Commons `1280px` photography
      Tier 4: Pollinations Flux HD fallback
    """
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    avoid = avoid_urls if avoid_urls is not None else set()
    q_clean = re.sub(r"[^A-Za-z0-9 \-]+", " ", (english_query or "artificial intelligence technology")).strip() or "technology business"

    # Tier 1: Exact Real-World Press/Product HD Photo via Bing Image Search
    bing_hits = await fetch_bing_hd_topic_images(q_clean, max_count=1, avoid_urls=avoid)
    if bing_hits:
        return bing_hits[0]

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) DiyorStudio/2.0"}
    timeout = aiohttp.ClientTimeout(total=8.0)
    fallback_jpg = MEDIA_CACHE_DIR / f"img_{_slug_hash(q_clean + '_' + str(len(avoid)))}.jpg"

    async with aiohttp.ClientSession(timeout=timeout) as sess:
        # Tier 2: Live News `og:image`
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
                        if img_u in avoid:
                            continue
                        async with sess.get(img_u, headers=headers) as ri:
                            if ri.status == 200:
                                raw_b = await ri.read()
                                if len(raw_b) >= 18_000:
                                    im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                                    if im.width >= 480 and im.height >= 280:
                                        im.save(fallback_jpg, format="JPEG", quality=92)
                                        avoid.add(img_u)
                                        dom = urllib.parse.urlparse(page_u).netloc.replace("www.", "")
                                        return {
                                            "ok": True,
                                            "path": str(fallback_jpg),
                                            "data_url": image_file_to_editorial_data_url(fallback_jpg),
                                            "source": dom[:24] or "Web News",
                                        }
            except Exception:
                continue

        # Tier 3: Wikimedia Commons `1280px` photography
        for attempt_q in (q_clean, " ".join(q_clean.split()[:2])):
            if not attempt_q:
                continue
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
                            if tu and tu not in avoid and w_px >= 600 and h_px >= 360 and not str(tu).lower().endswith(".svg"):
                                async with sess.get(tu, headers={"User-Agent": "DiyorStudio/2.0 (https://diyor.ctr)"}) as ri:
                                    if ri.status == 200:
                                        raw_b = await ri.read()
                                        if len(raw_b) >= 15_000:
                                            im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                                            im.save(fallback_jpg, format="JPEG", quality=92)
                                            avoid.add(tu)
                                            return {
                                                "ok": True,
                                                "path": str(fallback_jpg),
                                                "data_url": image_file_to_editorial_data_url(fallback_jpg),
                                                "source": "Wikimedia HD",
                                            }
            except Exception:
                continue

        # Tier 4: Pollinations Flux HD Editorial Image Fallback
        try:
            seed_n = 42 + len(avoid) * 17
            flux_prompt = urllib.parse.quote(f"editorial photojournalism of {q_clean}, realistic photography, natural lighting, high detail, no text")
            pol_u = f"https://image.pollinations.ai/prompt/{flux_prompt}?width=1024&height=600&nologo=true&seed={seed_n}"
            async with sess.get(pol_u, headers=headers) as rp:
                if rp.status == 200:
                    raw_b = await rp.read()
                    if len(raw_b) >= 15_000:
                        im = Image.open(io.BytesIO(raw_b)).convert("RGB")
                        im.save(fallback_jpg, format="JPEG", quality=92)
                        avoid.add(pol_u)
                        return {
                            "ok": True,
                            "path": str(fallback_jpg),
                            "data_url": image_file_to_editorial_data_url(fallback_jpg),
                            "source": "AI Visual · HD",
                        }
        except Exception:
            pass

    _make_fallback_editorial_graphic(q_clean, fallback_jpg)
    return {
        "ok": True,
        "path": str(fallback_jpg),
        "data_url": image_file_to_editorial_data_url(fallback_jpg),
        "source": "@diyor.ctr Visual",
    }


def _render_press_montage_sync(
    image_paths: list[str],
    out_mp4: Path,
    w: int = 1280,
    h: int = 720,
    duration: float = 4.5,
    fps: int = 30,
) -> Path:
    """
    Streams a 3-shot dynamic cinema documentary B-Roll MP4 (`30fps` optical zoom + pan + crisp
    2-frame shutter cut) directly to FFmpeg stdin using `< 10 MB` RAM!
    """
    ffmpeg_bin = _get_ffmpeg()
    valid_imgs = [Image.open(p).convert("RGB") for p in image_paths if Path(p).exists()]
    if not valid_imgs:
        return out_mp4

    # Pre-fit each shot to 1.18x overscan so per-frame crop is instant and razor-sharp
    OW, OH = int(round(w * 1.18)), int(round(h * 1.18))
    overscanned = [
        ImageEnhance.Contrast(
            ImageOps.fit(im, (OW, OH), method=Image.Resampling.LANCZOS, centering=(0.5, 0.36))
        ).enhance(1.05)
        for im in valid_imgs
    ]

    total_frames = max(45, int(round(duration * fps)))
    n_shots = len(overscanned)
    frames_per_shot = max(15, total_frames // n_shots)

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            ffmpeg_bin, "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out_mp4),
        ],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    try:
        for f_idx in range(total_frames):
            s_idx = min(n_shots - 1, f_idx // frames_per_shot)
            local_f = f_idx - s_idx * frames_per_shot
            prog = min(1.0, local_f / max(1, frames_per_shot - 1))
            src = overscanned[s_idx]

            # Alternate optical motion per shot: Shot 0 push-in right, Shot 1 pull-out left, Shot 2 center push-in
            if s_idx % 3 == 0:
                zoom = 1.00 + 0.12 * prog
                pan_x, pan_y = 0.35 + 0.30 * prog, 0.38
            elif s_idx % 3 == 1:
                zoom = 1.13 - 0.11 * prog
                pan_x, pan_y = 0.65 - 0.30 * prog, 0.42
            else:
                zoom = 1.01 + 0.13 * prog
                pan_x, pan_y = 0.50, 0.52 - 0.18 * prog

            cw = max(w, min(OW, int(round(OW / zoom))))
            ch = max(h, min(OH, int(round(OH / zoom))))
            x0 = int(round((OW - cw) * pan_x))
            y0 = int(round((OH - ch) * pan_y))
            frame_im = src.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.Resampling.BILINEAR)

            # Crisp 2-frame documentary shutter flash on cut transitions (`s_idx > 0` and `local_f < 2`)
            if s_idx > 0 and local_f < 2:
                boost = 1.22 if local_f == 0 else 1.10
                frame_im = ImageEnhance.Brightness(frame_im).enhance(boost)

            if proc.stdin:
                proc.stdin.write(frame_im.tobytes())
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()

    return out_mp4


async def build_cinema_press_montage_mp4(
    english_query: str,
    avoid_urls: set[str] | None = None,
    w: int = 1280,
    h: int = 720,
    duration: float = 4.5,
) -> dict[str, Any] | None:
    """
    Fetches 3 distinct real-world press/product HD photos for `english_query` and renders
    a 30fps 3-Shot Cinema Documentary B-Roll MP4 (`KINO-XRONIKA · HD`).
    """
    avoid = avoid_urls if avoid_urls is not None else set()
    hits = await fetch_bing_hd_topic_images(english_query, max_count=3, avoid_urls=avoid)
    if len(hits) < 2:
        # Supplement with secondary angle query if needed
        extra = await fetch_bing_hd_topic_images(f"{english_query} press photo", max_count=3 - len(hits), avoid_urls=avoid)
        hits.extend(extra)
    if not hits:
        return None

    img_paths = [h_item["path"] for h_item in hits if h_item.get("path")]
    key_sig = "_".join(img_paths) + f"_{w}x{h}"
    out_mp4 = MEDIA_CACHE_DIR / f"montage_{_slug_hash(key_sig)}.mp4"
    if not out_mp4.exists() or out_mp4.stat().st_size < 35_000:
        await asyncio.to_thread(_render_press_montage_sync, img_paths, out_mp4, w, h, duration, 30)

    if out_mp4.exists() and out_mp4.stat().st_size >= 35_000:
        return {
            "ok": True,
            "path": str(out_mp4),
            "url": f"montage://{_slug_hash(key_sig)}",
            "source": f"REAL KADR · {len(img_paths)} FOTO",
        }
    return None


def _extract_physical_video_subject(query: str) -> str | None:
    lo = query.lower()
    for triggers, mapped_q in _PHYSICAL_VIDEO_SUBJECT_MAP:
        if any(t in lo for t in triggers):
            return mapped_q
    return None


def _has_specific_entity(query: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    return bool(tokens & _SPECIFIC_ENTITY_TOKENS)


async def _try_wikimedia_topic_video(
    sess: aiohttp.ClientSession,
    query: str,
    avoid: set[str],
) -> dict[str, Any] | None:
    """Searches Wikimedia Commons `filetype:video` for real research/press/hardware clips and converts to H.264 MP4."""
    try:
        wm_u = (
            "https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6"
            f"&gsrsearch={urllib.parse.quote('filetype:video ' + query)}&gsrlimit=5"
            "&prop=imageinfo&iiprop=url|size|mime&format=json"
        )
        async with sess.get(wm_u, headers={"User-Agent": "DiyorStudio/2.0 (https://diyor.ctr)"}) as rw:
            if rw.status != 200:
                return None
            wd = await rw.json()
            pages = list((wd.get("query") or {}).get("pages", {}).values())
            for p in pages:
                title_lo = str(p.get("title") or "").lower()
                if any(bad in title_lo for bad in ("ai generated", "animation test", "logo", "spoken")):
                    continue
                info = (p.get("imageinfo") or [{}])[0]
                vu = info.get("url") or ""
                sz = int(info.get("size") or 0)
                if not vu or vu in avoid or sz < 150_000 or sz > 24_000_000:
                    continue
                out_mp4 = MEDIA_CACHE_DIR / f"wmv_{_slug_hash(vu)}.mp4"
                if not out_mp4.exists() or out_mp4.stat().st_size < 40_000:
                    raw_ext = ".webm" if ".webm" in vu.lower() else ".ogv"
                    tmp_in = MEDIA_CACHE_DIR / f"tmp_wm_{_slug_hash(vu)}{raw_ext}"
                    async with sess.get(vu, headers={"User-Agent": "DiyorStudio/2.0 (https://diyor.ctr)"}, timeout=aiohttp.ClientTimeout(total=10.0)) as dl:
                        if dl.status != 200:
                            continue
                        tmp_in.write_bytes(await dl.read())
                    ff = _get_ffmpeg()
                    subprocess.run(
                        [
                            ff, "-y", "-i", str(tmp_in), "-t", "7.0",
                            "-an", "-vf", "fps=30,scale=1280:-2",
                            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                            str(out_mp4),
                        ],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=18,
                    )
                    tmp_in.unlink(missing_ok=True)
                if out_mp4.exists() and out_mp4.stat().st_size >= 40_000:
                    avoid.add(vu)
                    return {"ok": True, "path": str(out_mp4), "url": vu, "source": "Wikimedia Video · HD"}
    except Exception:
        pass
    return None


async def fetch_topic_broll_video(
    english_query: str,
    avoid_urls: set[str] | None = None,
    prefer_press_montage: bool = False,
    portrait_hook: bool = False,
) -> dict[str, Any] | None:
    """
    Fetches a 100% topic-relevant 720p/1080p MP4 B-roll video ($0, zero key!):
      1. If `prefer_press_montage=True` (or specific named entity like `Apple iPhone 17`, `Sam Altman`,
         `Tesla Optimus` when stock footage wouldn't show the real product/person): builds a 3-Shot
         Real-World Press Cinema Montage MP4 (`REAL KADR · 3 FOTO`)!
      2. Optional Pexels HD Video API (if `PEXELS_API_KEY` set)
      3. Wikimedia Commons Real Video (`filetype:video`)
      4. Exact-Subject Mixkit Free HD Stock MP4 (NEVER blind-falls back to generic unrelated office stock!)
      5. Guaranteed 3-Shot Real-World Press Cinema Montage fallback!
    """
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    avoid = avoid_urls if avoid_urls is not None else set()
    q_clean = re.sub(r"[^A-Za-z0-9 \-]+", " ", (english_query or "technology")).strip() or "technology"
    mw, mh = (1080, 1920) if portrait_hook else (1280, 720)

    # When `prefer_press_montage=True`, immediately build a 3-shot real press documentary reel of the exact topic!
    if prefer_press_montage:
        pm = await build_cinema_press_montage_mp4(q_clean, avoid_urls=avoid, w=mw, h=mh, duration=4.6)
        if pm:
            return pm

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    timeout = aiohttp.ClientTimeout(total=12.0)

    # Build ONLY topic-faithful video search queries (ZERO generic 'business office laptop' pollution!)
    phys_subj = _extract_physical_video_subject(q_clean)
    exact_mixkit_queries: list[str] = []
    if not _has_specific_entity(q_clean):
        exact_mixkit_queries.append(q_clean)
    if phys_subj and phys_subj not in exact_mixkit_queries:
        exact_mixkit_queries.append(phys_subj)

    async with aiohttp.ClientSession(timeout=timeout) as sess:
        # 1. Optional Pexels Video API if configured
        px_key = os.getenv("PEXELS_API_KEY", "").strip()
        if px_key:
            try:
                orient = "portrait" if portrait_hook else "landscape"
                px_u = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(phys_subj or q_clean)}&per_page=6&orientation={orient}"
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

        # 2. If query names a specific real-world brand/CEO/product AND it's the Hero Hook (`portrait_hook=True`),
        #    show the ACTUAL real-world product/person in a 3-Shot Cinema Press Montage first!
        if portrait_hook and _has_specific_entity(q_clean):
            pm_hero = await build_cinema_press_montage_mp4(q_clean, avoid_urls=avoid, w=mw, h=mh, duration=3.6)
            if pm_hero:
                return pm_hero

        # 3. Wikimedia Commons Real Topic Video (`filetype:video`)
        wm_vid = await _try_wikimedia_topic_video(sess, q_clean, avoid)
        if wm_vid:
            return wm_vid

        # 4. Exact-Subject Mixkit HD Stock MP4 (only when physical visual subject matches!)
        for cq in exact_mixkit_queries:
            if not cq:
                continue
            try:
                search_u = f"https://mixkit.co/free-stock-video/search/?q={urllib.parse.quote_plus(cq)}"
                async with sess.get(search_u, headers=headers) as rs:
                    if rs.status != 200:
                        continue
                    ht = await rs.text(errors="ignore")
                    # Extract only card blocks whose title/slug actually matches at least one query word!
                    q_words = [w for w in re.findall(r"[a-z0-9]{3,}", cq.lower()) if w not in ("the", "and", "for", "video", "screen")]
                    card_blocks = re.findall(r'item-grid-card.*?</div>\s*</div>', ht, flags=re.S | re.I) or [ht[:12000]]
                    seen_u: list[str] = []
                    for blk in card_blocks:
                        blk_lo = blk.lower()
                        if q_words and not any(qw in blk_lo for qw in q_words):
                            continue
                        for u in re.findall(r"https://assets\.mixkit\.co/videos/\d+/\d+-(?:720|1080|large)\.mp4", blk):
                            if u not in seen_u and u not in avoid:
                                seen_u.append(u)
                    for chosen_u in seen_u[:4]:
                        out_mp4 = MEDIA_CACHE_DIR / f"broll_{_slug_hash(chosen_u)}.mp4"
                        if not out_mp4.exists() or out_mp4.stat().st_size < 40_000:
                            async with sess.get(chosen_u, headers=headers) as dl:
                                if dl.status == 200:
                                    data = await dl.read()
                                    if len(data) >= 40_000:
                                        out_mp4.write_bytes(data)
                        if out_mp4.exists() and out_mp4.stat().st_size >= 40_000:
                            avoid.add(chosen_u)
                            return {"ok": True, "path": str(out_mp4), "url": chosen_u, "source": "JONLI LAVHA · HD"}
            except Exception:
                continue

    # 5. Guaranteed Exact-Topic 3-Shot Real-World Press Cinema Montage (ZERO generic office stock fallback!)
    return await build_cinema_press_montage_mp4(q_clean, avoid_urls=avoid, w=mw, h=mh, duration=4.5)


def build_rounded_alpha_mask_png(out_png: Path, w: int, h: int, radius: int = 24) -> Path:
    """Creates a 4x supersampled anti-aliased rounded-rectangle alpha mask for FFmpeg `alphamerge`."""
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

        in_v = 1 + 2 * idx
        in_m = 2 + 2 * idx
        cmd += ["-stream_loop", "-1", "-t", str(dur), "-i", vp, "-loop", "1", "-t", str(dur), "-i", str(mask_png)]

        filter_parts.append(
            f"[{in_v}:v]fps={fps},scale={cw}:{ch}:force_original_aspect_ratio=increase,"
            f"crop={cw}:{ch},eq=contrast=1.04:saturation=0.98,format=yuv420p[bv{idx}]"
        )
        filter_parts.append(f"[{in_m}:v]scale={cw}:{ch},format=gray[bm{idx}]")
        filter_parts.append(
            f"[bv{idx}][bm{idx}]alphamerge,fade=t=in:st=0:d=0.25:alpha=1,"
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


async def render_news_broll_hook_frames(
    ffmpeg_bin: str,
    broll_mp4: Path | None,
    fallback_image_data_url: str,
    hook_config: dict[str, Any],
    duration: float = 2.8,
    fps: int = 30,
) -> list[bytes]:
    """
    Mode 2 (`news` / high-views) Opening Hook:
    1-soniyadanoq to'liq ekranli (1080x1920) harakatlanuvchi Real-Kadr B-Roll video + sensatsion Fraunces sarlavhasi!
    Returns `list[bytes]` of HQ JPEG frames (`~15 MB` total RAM) for `prepend_rgb_frames`.
    """
    from playwright.async_api import async_playwright

    W, H = 1080, 1920
    n_frames = max(30, int(round(duration * fps)))
    fonts_css = (Path("/home/user/claude-techbrief/shared/fonts/fonts.css")).resolve().as_uri()
    kicker = str(hook_config.get("kicker") or "TEZKOR YANGILIK · 2026")
    head_html = str(hook_config.get("headlineHtml") or "Texnologiya olamida<br><em>yangi burilish</em>")
    sub_txt = str(hook_config.get("subtext") or "Eng muhim faktlar va real kadrlar — 30 soniyada.")
    callouts = hook_config.get("callouts") or []
    c1 = callouts[0] if len(callouts) >= 1 else {"label": "FAKT", "value": "2026 Trend"}
    c2 = callouts[1] if len(callouts) >= 2 else {"label": "MANBA", "value": "Global Tech"}

    overlay_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <link rel="stylesheet" href="{fonts_css}">
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{ width: {W}px; height: {H}px; background: transparent; font-family: 'Inter', sans-serif; overflow: hidden; }}
      .hud-wrap {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(14,13,12,0.52) 0%, rgba(14,13,12,0.06) 28%, rgba(14,13,12,0.22) 52%, rgba(12,12,11,0.88) 76%, rgba(10,10,9,0.97) 100%); }}
      .br {{ position: absolute; width: 26px; height: 26px; border-color: rgba(250,249,245,0.45); border-style: solid; }}
      .tl {{ top: 56px; left: 56px; border-width: 2px 0 0 2px; }}
      .tr {{ top: 56px; right: 56px; border-width: 2px 2px 0 0; }}
      .bl {{ bottom: 356px; left: 56px; border-width: 0 0 2px 2px; }}
      .br-r {{ bottom: 356px; right: 56px; border-width: 0 2px 2px 0; }}
      .top-bar {{ position: absolute; top: 68px; left: 88px; right: 88px; display: flex; justify-content: space-between; align-items: center; }}
      .live-pill {{ display: inline-flex; align-items: center; gap: 10px; background: rgba(217, 68, 52, 0.92); color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; letter-spacing: 0.14em; padding: 9px 18px; border-radius: 999px; box-shadow: 0 8px 24px rgba(217,68,52,0.38); }}
      .live-dot {{ width: 10px; height: 10px; border-radius: 50%; background: #fff; }}
      .top-tag {{ font-family: 'JetBrains Mono', monospace; font-size: 15px; letter-spacing: 0.16em; color: rgba(250,249,245,0.85); }}
      .bot-hud {{ position: absolute; bottom: 366px; left: 88px; right: 88px; display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 16px; letter-spacing: 0.16em; color: rgba(250,249,245,0.78); }}
      .card-zone {{ position: absolute; left: 68px; right: 68px; bottom: 425px; }}
      .pills-row {{ display: flex; gap: 14px; margin-bottom: 18px; }}
      .f-pill {{ background: rgba(25,24,22,0.82); border: 1px solid rgba(250,249,245,0.22); backdrop-filter: blur(12px); padding: 12px 20px; border-radius: 18px; color: #faf9f5; }}
      .f-lbl {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 0.15em; color: #ff8a5c; margin-bottom: 4px; }}
      .f-val {{ font-size: 21px; font-weight: 800; color: #ffffff; }}
      .news-box {{ background: rgba(250,249,245,0.96); border-radius: 30px; padding: 30px 34px; box-shadow: 0 26px 60px rgba(0,0,0,0.42); border: 1.5px solid rgba(255,255,255,0.6); }}
      .kicker {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; letter-spacing: 0.16em; color: #c85a38; margin-bottom: 12px; text-transform: uppercase; }}
      .headline {{ font-family: 'Fraunces', serif; font-size: 54px; font-weight: 720; line-height: 1.04; letter-spacing: -0.025em; color: #141413; margin-bottom: 14px; }}
      .headline em {{ font-style: italic; color: #c85a38; font-weight: 680; }}
      .sub {{ font-size: 21px; line-height: 1.38; color: #4a4740; font-weight: 500; }}
    </style></head><body>
      <div id="bg_hud" class="hud-wrap">
        <div class="br tl"></div><div class="br tr"></div><div class="br bl"></div><div class="br br-r"></div>
        <div class="top-bar">
          <div class="live-pill"><span class="live-dot"></span>{kicker}</div>
          <div class="top-tag">YANGILIK · HD</div>
        </div>
        <div class="bot-hud">
          <span style="color:#ff8a5c;">↗ YANGILIKLAR · @DIYOR.CTR</span>
          <span>@DIYOR.CTR</span>
        </div>
      </div>
      <div id="fg_card" class="card-zone">
        <div class="pills-row">
          <div class="f-pill"><div class="f-lbl">{c1.get('label','FAKT')}</div><div class="f-val">{c1.get('value','Muhim xabar')}</div></div>
          <div class="f-pill"><div class="f-lbl">{c2.get('label','TAHLIL')}</div><div class="f-val">{c2.get('value','Real kadrlar')}</div></div>
        </div>
        <div class="news-box">
          <div class="kicker">● MAXSUS TAHLIL · @DIYOR.CTR</div>
          <div class="headline">{head_html}</div>
          <div class="sub">{sub_txt}</div>
        </div>
      </div>
    </body></html>"""

    tmp_html = MEDIA_CACHE_DIR / f"tmp_news_hook_{os.getpid()}.html"
    tmp_html.write_text(overlay_html, encoding="utf-8")
    try:
        async with async_playwright() as p:
            br = await p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
            pg = await br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            await pg.goto(tmp_html.resolve().as_uri(), wait_until="networkidle")
            await pg.evaluate("document.getElementById('fg_card').style.display='none'")
            hud_png = await pg.screenshot(type="png", omit_background=True)
            await pg.evaluate("document.getElementById('bg_hud').style.display='none'; document.getElementById('fg_card').style.display='block'")
            card_png = await pg.screenshot(type="png", omit_background=True)
            await br.close()
    finally:
        tmp_html.unlink(missing_ok=True)

    hud_rgba = Image.open(io.BytesIO(hud_png)).convert("RGBA")
    card_rgba = Image.open(io.BytesIO(card_png)).convert("RGBA")

    entrance_cards: list[Image.Image] = []
    for idx in range(11):
        t_in = idx / 10.0
        ease = 1.0 - (1.0 - t_in) ** 3
        y_off = int(round(28 * (1.0 - ease)))
        r, g, b, a = card_rgba.split()
        a = a.point(lambda p, e=ease: int(p * e))
        shifted = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shifted.paste(Image.merge("RGBA", (r, g, b, a)), (0, y_off))
        entrance_cards.append(shifted)

    OW, OH = 1144, 2034
    out_jpg_frames: list[bytes] = []

    def _finish_frame(src_im: Image.Image, idx_f: int) -> bytes:
        prog = idx_f / max(1, n_frames - 1)
        dx = int(round((OW - W) * (0.5 - 0.32 * prog)))
        dy = int(round((OH - H) * (0.34 + 0.22 * prog)))
        cropped = src_im.crop((dx, dy, dx + W, dy + H)).convert("RGBA")
        cropped = Image.alpha_composite(cropped, hud_rgba)
        cropped = Image.alpha_composite(cropped, entrance_cards[idx_f] if idx_f < 11 else card_rgba)
        jb = io.BytesIO()
        cropped.convert("RGB").save(jb, format="JPEG", quality=94)
        return jb.getvalue()

    if broll_mp4 and broll_mp4.exists():
        proc = subprocess.Popen(
            [
                ffmpeg_bin, "-y", "-stream_loop", "-1", "-i", str(broll_mp4),
                "-frames:v", str(n_frames),
                "-vf", f"fps={fps},scale={OW}:{OH}:force_original_aspect_ratio=increase,crop={OW}:{OH},eq=contrast=1.05:saturation=1.03",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        frame_sz = OW * OH * 3
        last_im: Image.Image | None = None
        while len(out_jpg_frames) < n_frames:
            buf = proc.stdout.read(frame_sz) if proc.stdout else b""
            if len(buf) < frame_sz:
                break
            last_im = Image.frombytes("RGB", (OW, OH), buf)
            out_jpg_frames.append(_finish_frame(last_im, len(out_jpg_frames)))
        if proc.stdout:
            proc.stdout.close()
        proc.wait()
        while last_im is not None and len(out_jpg_frames) < n_frames:
            out_jpg_frames.append(_finish_frame(last_im, len(out_jpg_frames)))

    if not out_jpg_frames:
        if fallback_image_data_url.startswith("data:image"):
            b64_part = fallback_image_data_url.split(",", 1)[1]
            base_im = Image.open(io.BytesIO(base64.b64decode(b64_part))).convert("RGB")
        else:
            base_im = Image.new("RGB", (OW, OH), (24, 23, 21))
        s = max(OW / base_im.width, OH / base_im.height)
        resized = base_im.resize((int(base_im.width * s) + 2, int(base_im.height * s) + 2), Image.Resampling.LANCZOS)
        x0 = (resized.width - OW) // 2
        y0 = (resized.height - OH) // 2
        still = resized.crop((x0, y0, x0 + OW, y0 + OH))
        for idx_f in range(n_frames):
            out_jpg_frames.append(_finish_frame(still, idx_f))

    return out_jpg_frames


async def render_news_cover_slide(
    image_data_url: str,
    out_png: Path,
    hook_config: dict[str, Any],
) -> Path:
    """Renders a 4:5 (1080x1350) Editorial News Cover PNG for Mode 2 (`news`)."""
    from playwright.async_api import async_playwright

    W, H = 1080, 1350
    fonts_css = (Path("/home/user/claude-techbrief/shared/fonts/fonts.css")).resolve().as_uri()
    kicker = str(hook_config.get("kicker") or "TEZKOR YANGILIK · 2026")
    head_html = str(hook_config.get("headlineHtml") or "Texnologiya olamida<br><em>yangi burilish</em>")
    sub_txt = str(hook_config.get("subtext") or "@diyor.ctr — har kuni eng muhim texno va AI yangiliklar.")
    bg_tag = f'<img src="{image_data_url}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;" />' if image_data_url else ""

    html_doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <link rel="stylesheet" href="{fonts_css}">
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{ width: {W}px; height: {H}px; position: relative; overflow: hidden; background: #141413; font-family: 'Inter', sans-serif; }}
      .shade {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(14,13,12,0.45) 0%, rgba(14,13,12,0.12) 38%, rgba(12,12,11,0.92) 82%, rgba(10,10,9,0.98) 100%); }}
      .top {{ position: absolute; top: 54px; left: 64px; right: 64px; display: flex; justify-content: space-between; align-items: center; }}
      .pill {{ background: #d94434; color: #fff; font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; letter-spacing: 0.14em; padding: 9px 18px; border-radius: 999px; }}
      .card {{ position: absolute; left: 60px; right: 60px; bottom: 64px; background: rgba(250,249,245,0.97); border-radius: 30px; padding: 34px 38px; }}
      .hd {{ font-family: 'Fraunces', serif; font-size: 56px; font-weight: 720; line-height: 1.04; color: #141413; margin-bottom: 14px; }}
      .hd em {{ font-style: italic; color: #c85a38; }}
      .sb {{ font-size: 21px; color: #4a4740; line-height: 1.38; margin-bottom: 18px; }}
      .ft {{ display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 14px; letter-spacing: 0.15em; color: #7a7469; border-top: 1px solid #e2ddd3; padding-top: 14px; }}
    </style></head><body>
      {bg_tag}
      <div class="shade"></div>
      <div class="top">
        <div class="pill">● {kicker}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:15px;letter-spacing:0.16em;color:#faf9f5;">@DIYOR.CTR</div>
      </div>
      <div class="card">
        <div class="hd">{head_html}</div>
        <div class="sb">{sub_txt}</div>
        <div class="ft"><span>OBUNA BO‘LING · @DIYOR.CTR</span><span style="color:#c85a38;font-weight:700;">KUNLIK TAHLIL →</span></div>
      </div>
    </body></html>"""

    tmp_h = MEDIA_CACHE_DIR / f"tmp_news_cov_{os.getpid()}.html"
    tmp_h.write_text(html_doc, encoding="utf-8")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as p:
            br = await p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
            pg = await br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            await pg.goto(tmp_h.resolve().as_uri(), wait_until="networkidle")
            await pg.screenshot(path=str(out_png), type="png")
            await br.close()
    finally:
        tmp_h.unlink(missing_ok=True)
    return out_png
