#!/usr/bin/env python3
"""Clean public cloud_render_bridge stub (zero embedded credentials)."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

DIYOR_CLONE_WAV = Path("/home/user/.cache/diyor_vault/models/diyor_clone_ref_24k.wav")
_SEC_PATH = Path("/home/user/.cache/diyor_vault/.cloud_secrets.json")

def load_cloud_secrets() -> dict[str, Any]:
    if _SEC_PATH.exists():
        try:
            return json.loads(_SEC_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cloud_secrets(patch: dict[str, Any]) -> None:
    cur = load_cloud_secrets()
    cur.update(patch)
    _SEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SEC_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")

async def post_modal_json(url: str, payload: dict[str, Any], timeout_sec: int = 90) -> dict[str, Any] | None:
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as r:
            if r.status == 200:
                return await r.json(content_type=None)
    return None

async def transcribe_uzbek_via_modal(wav_path: Path) -> dict[str, Any] | None:
    return None
