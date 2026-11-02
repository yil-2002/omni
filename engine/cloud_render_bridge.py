#!/usr/bin/env python3
"""
🌐 @diyor.ctr — $0-Cost External Cloud Render, R2 CDN & Meta Auto-Publish Bridge
================================================================================
100% bepul ($0/oy) tashqi infratuzilma ko‘prigi:
1. Modal.com Serverless Render (`$0/oy` Starter — `$30/oy` bepul kredit, 40–100 parallel konteyner)
   -> Ulanmagan bo‘lsa avtomatik lokal multi-worker Chromium dvigatelida ishlaydi!
2. Cloudflare R2 S3-SigV4 (`$0/oy` — `10 GB` bepul + `$0` egress trafik, sof Python HMAC-SHA256, `boto3` kerak emas!)
   -> Ulanmagan bo‘lsa avtomatik Litterbox Direct HTTPS CDN + GoFile + Telegram Vault ishlatadi!
3. Meta Instagram Content Publishing API (`$0` rasmiy bepul API — `@diyor.ctr` ga Reels va 10-slaydli
   Mixed-Media Karusellarni to‘g‘ridan-to‘g‘ri joylash!)
"""
from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import hmac
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import aiohttp

VAULT_ROOT = Path("/home/user/.cache/diyor_vault")
CLOUD_SECRET_FILE = VAULT_ROOT / ".cloud_secrets.json"
MODAL_WORKER_PATH = Path("/home/user/claude-techbrief/engine/modal_render_worker.py")
MODAL_HUB_PATH = Path("/home/user/claude-techbrief/engine/modal_diyor_hub.py")
DIYOR_CLONE_WAV = VAULT_ROOT / "diyor_clone_ref_24k.wav"


def load_cloud_secrets() -> dict[str, str]:
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    defaults = {
        "modal_token_id": os.getenv("MODAL_TOKEN_ID", ""),
        "modal_token_secret": os.getenv("MODAL_TOKEN_SECRET", ""),
        "modal_webhook_url": os.getenv("MODAL_WEBHOOK_URL", "https://yoqubovmuhammadiyor--diyor-ctr-render-farm.us-east.modal.run"),
        "modal_voice_url": os.getenv("MODAL_VOICE_URL", "https://yoqubovmuhammadiyor--diyor-ctr-voice-gpu.us-east.modal.run"),
        "modal_photo_url": os.getenv("MODAL_PHOTO_URL", "https://yoqubovmuhammadiyor--diyor-ctr-photo-gpu.us-east.modal.run"),
        "modal_navoiy_webhook_url": os.getenv("MODAL_NAVOIY_URL", ""),
        "auto_modal_bariton": "1",
        "diyor_clone_ref_text": "",
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "hf_token": os.getenv("HF_TOKEN", ""),
        "r2_account_id": os.getenv("R2_ACCOUNT_ID", ""),
        "r2_access_key_id": os.getenv("R2_ACCESS_KEY_ID", ""),
        "r2_secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY", ""),
        "r2_bucket": os.getenv("R2_BUCKET", ""),
        "r2_public_domain": os.getenv("R2_PUBLIC_DOMAIN", ""),
        "ig_business_id": os.getenv("IG_BUSINESS_ID", ""),
        "meta_access_token": os.getenv("META_ACCESS_TOKEN", ""),
    }
    if CLOUD_SECRET_FILE.exists():
        try:
            saved = json.loads(CLOUD_SECRET_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                defaults.update({k: str(v) for k, v in saved.items() if v is not None})
        except Exception:
            pass
    return defaults


def save_cloud_secrets(updates: dict[str, Any]) -> dict[str, str]:
    cur = load_cloud_secrets()
    for k, v in updates.items():
        if v is not None:
            cur[k] = str(v).strip()
    CLOUD_SECRET_FILE.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(CLOUD_SECRET_FILE, 0o600)
    return cur


def cloud_bridge_status() -> dict[str, Any]:
    s = load_cloud_secrets()
    modal_render_ready = bool(s.get("modal_webhook_url"))
    modal_voice_ready = bool(s.get("modal_voice_url"))
    modal_photo_ready = bool(s.get("modal_photo_url"))
    modal_tokens_set = bool(s.get("modal_token_id") and s.get("modal_token_secret"))
    clone_ready = DIYOR_CLONE_WAV.exists() and DIYOR_CLONE_WAV.stat().st_size > 2000
    r2_ready = bool(
        s.get("r2_account_id")
        and s.get("r2_access_key_id")
        and s.get("r2_secret_access_key")
        and s.get("r2_bucket")
    )
    ig_pub_ready = bool(s.get("ig_business_id") and s.get("meta_access_token"))
    return {
        "modal_webhook_active": modal_render_ready,
        "modal_webhook_url": s.get("modal_webhook_url", ""),
        "modal_voice_active": modal_voice_ready,
        "modal_voice_url": s.get("modal_voice_url", ""),
        "modal_photo_active": modal_photo_ready,
        "modal_photo_url": s.get("modal_photo_url", ""),
        "modal_tokens_configured": modal_tokens_set,
        "diyor_clone_ready": clone_ready,
        "primary_voice": "Modal Cloud · Kino Bariton HD (Rubberband + Pedalboard C++)" if modal_voice_ready else "Sardor · Chuqur Kino Bariton (-6Hz, $0)",
        "active_render_engine": "Modal.com Serverless (Parallel Cloud Farm)" if modal_render_ready else "Local Multi-Worker Parallel Chromium (3–4x)",
        "active_photo_engine": "Modal Cloud 8-Core (ISNet HD + Clean-Plate)" if modal_photo_ready else "Local ISNet/U2Net + Clean-Plate",
        "r2_cdn_active": r2_ready,
        "r2_public_domain": s.get("r2_public_domain", ""),
        "active_cdn_tier": "Cloudflare R2 ($0 Egress) + Telegram + GoFile" if r2_ready else "Telegram Vault + GoFile + Litterbox HTTPS ($0)",
        "ig_direct_publish_ready": ig_pub_ready,
        "ig_handle": "@diyor.ctr",
    }


# ==============================================================================
# 1. MODAL.COM UNIFIED CLOUD HUB DEPLOYER (T4 VOICE + T4 PHOTO + 40x RENDER)
# ==============================================================================
async def deploy_modal_worker() -> dict[str, Any]:
    """
    Installs `modal` CLI if needed and deploys `modal_diyor_hub.py` (`diyor-ctr-cloud-hub`),
    automatically capturing all 3 live HTTPS endpoints:
      - `modal_voice_url`   (`...diyor-ctr-voice-gpu.modal.run`)
      - `modal_photo_url`   (`...diyor-ctr-photo-gpu.modal.run`)
      - `modal_webhook_url` (`...diyor-ctr-render-farm.modal.run`)
    """
    s = load_cloud_secrets()
    tid = s.get("modal_token_id", "")
    tsec = s.get("modal_token_secret", "")
    if not (tid and tsec):
        return {"ok": False, "error": "Avval MODAL_TOKEN_ID (ak-...) va MODAL_TOKEN_SECRET (as-...) kiriting (modal.com/settings -> API Tokens)."}

    def _run_deploy() -> dict[str, Any]:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "modal"], check=True)
        env = {**os.environ, "MODAL_TOKEN_ID": tid, "MODAL_TOKEN_SECRET": tsec}
        proc = subprocess.run(
            [sys.executable, "-m", "modal", "deploy", str(MODAL_HUB_PATH)],
            env=env, capture_output=True, text=True, timeout=600,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        if proc.returncode != 0:
            return {"ok": False, "error": out[-900:]}

        urls = re.findall(r"https://[a-zA-Z0-9._-]+modal\.run", out)
        updates: dict[str, str] = {}
        for u in urls:
            if "voice-gpu" in u:
                updates["modal_voice_url"] = u
            elif "photo-gpu" in u:
                updates["modal_photo_url"] = u
            elif "render-farm" in u or "render-webhook" in u:
                updates["modal_webhook_url"] = u
        if updates:
            save_cloud_secrets(updates)
        return {"ok": True, "endpoints": updates, "all_urls": urls, "log": out[-800:]}

    return await asyncio.to_thread(_run_deploy)


def call_modal_photo_cutout_sync(png_or_jpg_bytes: bytes) -> bytes | None:
    """Synchronous helper used by `photo_brand_engine.py`: offloads HD segmentation to Modal T4 GPU if active."""
    import urllib.request

    s = load_cloud_secrets()
    url = s.get("modal_photo_url", "").strip()
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"image_base64": base64.b64encode(png_or_jpg_bytes).decode("ascii")}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("ok") and d.get("fg_png_base64"):
                return base64.b64decode(d["fg_png_base64"])
    except Exception:
        return None
    return None


async def transcribe_uzbek_via_modal(audio_path: Path) -> dict[str, Any] | None:
    """Runs GPU `faster-whisper` (`large-v3-turbo`) word-level Uzbek transcription via `ModalVoiceGPU`."""
    s = load_cloud_secrets()
    url = s.get("modal_voice_url", "").strip()
    if not url or not audio_path.exists():
        return None
    payload = {
        "mode": "transcribe",
        "audio_base64": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as resp:
            if resp.status == 200:
                d = await resp.json(content_type=None)
                if d and d.get("ok"):
                    return d
    return None


async def post_modal_json(url: str, payload: dict[str, Any], timeout_sec: int = 300) -> dict[str, Any] | None:
    """
    Posts JSON to a Modal `@modal.fastapi_endpoint`, cleanly following Modal's `HTTP 303 See Other`
    result-polling redirects on cold starts or long-running multi-container jobs.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            allow_redirects=True,
            max_redirects=20,
            timeout=aiohttp.ClientTimeout(total=timeout_sec),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    return None


async def try_modal_webhook_render(
    html_path: Path,
    out_mp4: Path,
    cuts: list[float],
    fps: int = 30,
    with_clawd: bool = False,
    prepend_rgb_frames: list[bytes] | None = None,
    lufs_target: float = -14.5,
) -> dict[str, Any] | None:
    """
    If `modal_webhook_url` is configured and no local `prepend_rgb_frames` / local sprite overlay is required,
    dispatches the entire timeline to Modal's parallel cloud farm and writes `out_mp4`.
    Returns `None` if unconfigured or if local compositing is preferred.
    """
    s = load_cloud_secrets()
    webhook_url = s.get("modal_webhook_url", "").strip()
    if not webhook_url or prepend_rgb_frames or with_clawd:
        return None

    html_str = html_path.read_text(encoding="utf-8")
    m_w = re.search(r'data-width="(\d+)"', html_str)
    m_h = re.search(r'data-height="(\d+)"', html_str)
    m_d = re.search(r'data-duration="([0-9.]+)"', html_str)
    W = int(m_w.group(1)) if m_w else 1080
    H = int(m_h.group(1)) if m_h else 1920
    dur = float(m_d.group(1)) if m_d else 8.0

    payload = {
        "html": html_str,
        "width": W,
        "height": H,
        "duration": dur,
        "fps": fps,
        "cuts": cuts,
        "lufs_target": lufs_target,
    }
    try:
        data = await post_modal_json(webhook_url, payload, timeout_sec=300)
        if not data or not data.get("ok") or not data.get("mp4_base64"):
            return None
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(base64.b64decode(data["mp4_base64"]))
        return {
            "output": str(out_mp4),
            "width": W,
            "height": H,
            "duration": dur,
            "fps": fps,
            "workers_used": data.get("workers_used", 1),
            "render_backend": "modal_serverless_cloud",
            "with_clawd": False,
            "lufs": lufs_target,
            "cuts": cuts,
        }
    except Exception:
        return None


# ==============================================================================
# 2. PURE-PYTHON CLOUDFLARE R2 S3-SIGV4 UPLOADER ($0 — 10 GB FREE, $0 EGRESS)
# ==============================================================================
def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


async def upload_to_cloudflare_r2(file_path: Path, object_key: str | None = None) -> str:
    """
    Uploads `file_path` to Cloudflare R2 using pure-Python AWS Signature v4 (`PUT`).
    Returns the permanent public HTTPS URL (`https://<r2_public_domain>/<object_key>`) or `""` if R2 not set.
    """
    s = load_cloud_secrets()
    acc_id = s.get("r2_account_id", "")
    ak = s.get("r2_access_key_id", "")
    sk = s.get("r2_secret_access_key", "")
    bucket = s.get("r2_bucket", "")
    pub_dom = s.get("r2_public_domain", "").rstrip("/")
    if not (acc_id and ak and sk and bucket):
        return ""

    key = (object_key or file_path.name).lstrip("/")
    data = file_path.read_bytes()
    payload_hash = hashlib.sha256(data).hexdigest()
    ctype, _ = mimetypes.guess_type(str(file_path))
    content_type = ctype or "application/octet-stream"

    host = f"{acc_id}.r2.cloudflarestorage.com"
    canonical_uri = f"/{bucket}/" + urllib.parse.quote(key, safe="/-_.~")
    endpoint = f"https://{host}{canonical_uri}"

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    region = "auto"
    service = "s3"

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = f"PUT\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        f"{algorithm}\n{amz_date}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    )
    signing_key = _get_signature_key(sk, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"{algorithm} Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Content-Type": content_type,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Authorization": auth_header,
    }
    async with aiohttp.ClientSession() as session:
        async with session.put(endpoint, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status not in (200, 201):
                return ""
    if pub_dom:
        return f"{pub_dom}/{urllib.parse.quote(key, safe='/-_.~')}"
    return endpoint


async def ensure_public_https_url(file_path: Path) -> str:
    """
    Guarantees a direct public HTTPS URL required by Meta Instagram Content Publishing API ($0 cost):
    1. Tries Cloudflare R2 custom domain first (`https://media.diyor.ctr/...`);
    2. Falls back to Litterbox direct HTTPS mirror (`https://litter.catbox.moe/...`).
    """
    r2_url = await upload_to_cloudflare_r2(file_path)
    if r2_url.startswith("https://"):
        return r2_url

    if "/home/user/tashqi_xotira" not in sys.path:
        sys.path.insert(0, "/home/user/tashqi_xotira")
    from cloud_vault import upload_file_to_cloud
    info = await asyncio.to_thread(upload_file_to_cloud, file_path, file_path.name)
    return info.get("direct_cdn_url", "")


# ==============================================================================
# 3. OFFICIAL META INSTAGRAM CONTENT PUBLISHING API ($0 FREE — REELS & CAROUSELS)
# ==============================================================================
async def _wait_ig_container_ready(session: aiohttp.ClientSession, base_url: str, creation_id: str, token: str) -> bool:
    for _ in range(30):
        async with session.get(
            f"{base_url}/{creation_id}",
            params={"fields": "status_code,status", "access_token": token},
        ) as resp:
            d = await resp.json(content_type=None) or {}
            sc = d.get("status_code", "")
            if sc == "FINISHED":
                return True
            if sc in ("ERROR", "EXPIRED"):
                return False
        await asyncio.sleep(3.0)
    return False


async def publish_reel_to_instagram(video_path: Path, caption: str, share_to_feed: bool = True) -> dict[str, Any]:
    """Publishes a `9:16` MP4 Reel directly to `@diyor.ctr` via Meta Graph Content Publishing API ($0 fee)."""
    s = load_cloud_secrets()
    ig_id = s.get("ig_business_id", "")
    token = s.get("meta_access_token", "")
    if not (ig_id and token):
        return {"ok": False, "error": "IG_BUSINESS_ID va META_ACCESS_TOKEN kiritilmagan."}

    video_url = await ensure_public_https_url(video_path)
    if not video_url:
        return {"ok": False, "error": "Ochiq HTTPS video havolasini olish imkoni bo‘lmadi (Cloudflare R2 ni ulang)."}

    base_url = "https://graph.instagram.com/v21.0"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/{ig_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true" if share_to_feed else "false",
                "access_token": token,
            },
        ) as resp:
            c_data = await resp.json(content_type=None) or {}
            creation_id = c_data.get("id")
            if not creation_id:
                return {"ok": False, "error": c_data}

        if not await _wait_ig_container_ready(session, base_url, creation_id, token):
            return {"ok": False, "error": "Meta video konteynerni qayta ishlashda xato berdi."}

        async with session.post(
            f"{base_url}/{ig_id}/media_publish",
            data={"creation_id": creation_id, "access_token": token},
        ) as pub_resp:
            pub_data = await pub_resp.json(content_type=None) or {}
            return {"ok": "id" in pub_data, "media_id": pub_data.get("id"), "response": pub_data, "source_url": video_url}


async def publish_mixed_carousel_to_instagram(media_paths: list[Path], caption: str) -> dict[str, Any]:
    """Publishes up to 10-item Mixed-Media Carousel (JPEG/PNG + MP4) directly to `@diyor.ctr` ($0 fee)."""
    s = load_cloud_secrets()
    ig_id = s.get("ig_business_id", "")
    token = s.get("meta_access_token", "")
    if not (ig_id and token):
        return {"ok": False, "error": "IG_BUSINESS_ID va META_ACCESS_TOKEN kiritilmagan."}

    base_url = "https://graph.instagram.com/v21.0"
    child_ids: list[str] = []

    async with aiohttp.ClientSession() as session:
        for mp in media_paths[:10]:
            pub_url = await ensure_public_https_url(mp)
            if not pub_url:
                return {"ok": False, "error": f"Ochiq HTTPS havola topilmadi: {mp.name}"}
            is_vid = mp.suffix.lower() in (".mp4", ".mov")
            payload = {"is_carousel_item": "true", "access_token": token}
            if is_vid:
                payload["media_type"] = "VIDEO"
                payload["video_url"] = pub_url
            else:
                payload["image_url"] = pub_url

            async with session.post(f"{base_url}/{ig_id}/media", data=payload) as r:
                cd = await r.json(content_type=None) or {}
                cid = cd.get("id")
                if not cid:
                    return {"ok": False, "error": cd}
                if is_vid:
                    await _wait_ig_container_ready(session, base_url, cid, token)
                child_ids.append(cid)

        async with session.post(
            f"{base_url}/{ig_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": token,
            },
        ) as cr:
            car_data = await cr.json(content_type=None) or {}
            car_id = car_data.get("id")
            if not car_id:
                return {"ok": False, "error": car_data}

        await _wait_ig_container_ready(session, base_url, car_id, token)
        async with session.post(
            f"{base_url}/{ig_id}/media_publish",
            data={"creation_id": car_id, "access_token": token},
        ) as pr:
            pub_data = await pr.json(content_type=None) or {}
            return {"ok": "id" in pub_data, "media_id": pub_data.get("id"), "children": child_ids, "response": pub_data}
