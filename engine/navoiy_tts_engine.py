#!/usr/bin/env python3
"""
🎙 @diyor.ctr — Uzbek `Navoiy TTS` 3-Tier $0-Cost Cloud Engine (`navoiy_tts_engine.py`)
======================================================================================
Nega lokal konteynerning o‘zida (`1.9 GB RAM`, `CPU-only`) model og‘irligini yuklab bo‘lmaydi?
  `aisha-org/navoiy-tts` (`CosyVoice2-0.5B` + `emotion_600h_joint.pt` = ~4.1 GB) CUDA GPU
  (`~4.8 GB VRAM` fp16) talab qiladi.

Shu cheklovni 0 MB lokal RAM sarfi va $0 xarajat bilan yechuvchi 3 bosqichli ko‘prik:
  1-USUL (Shaxsiy Dedikatsiyalangan GPU — `$0/oy` Modal.com `$30` bepul kreditda `T4` GPU):
     Agar `modal_navoiy_webhook_url` (yoki Colab/Kaggle `navoiy_custom_url`) kiritilgan bo‘lsa —
     o‘z konteyneringizda `aisha-org/navoiy-tts` ni hech qanday navbatsiz ishga tushiradi
     (kelajakda 15 soniyalik ovozingizni ulab bepul ovoz klonlash imkoni bilan!).
  2-USUL (HOZIROQ TAYYOR VA ISHLAMOQDA — Hugging Face `Zero-A10G` GPU Bridge, `$0`):
     `uzbtrust/morfem-navoiy-tts` rasmiy `aisha-org/navoiy-tts` (`CosyVoice2-0.5B`) A10G GPU
     endpointiga SSE orqali ulanib, ~6–8 soniyada 24 kHz toza o‘zbekcha `Navoiy` ovozini oladi!
     (`HF_TOKEN` qo‘shilsa ZeroGPU kunlik kvotasi 5–8 barobar oshadi!)
  3-USUL (100% Cheksiz Avto-Zaxira — Microsoft Neural `edge-tts`, `$0`):
     Agar ZeroGPU vaqtincha band bo‘lsa, jarayon to‘xtab qolmasligi uchun avtomatik ravishda
     `uz-UZ-SardorNeural` / `uz-UZ-MadinaNeural` neyron ovoziga o‘tadi.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import aiohttp

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if str(TB_ROOT / "vositalar") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "vositalar"))

from cloud_render_bridge import load_cloud_secrets, save_cloud_secrets  # noqa: E402
from motion_engine import get_ffmpeg_bin, VAULT_TMP  # noqa: E402
from uztts_normalize import normalize_uzbek_for_tts  # noqa: E402
from _fxbed import build_fx_for_cuts  # noqa: E402

HF_NAVOIY_SPACE_URL = "https://uzbtrust-morfem-navoiy-tts.hf.space"

NAVOIY_EMOTIONS: dict[str, str] = {
    "mehribon": "Mehribon / Iliq ekspert ohangi (Tavsiya etiladi)",
    "xotirjam": "Xotirjam / Ishonchli tahliliy ohang",
    "xursand": "Xursand / Yuqori energiyali Hook ohangi",
    "hayratda": "Hayratda / Kuchli e'tibor tortuvchi",
    "pichirlab": "Pichirlab / Sirli insayd ohangi",
    "jahldor": "Qat'iy / Keskin urg'uli",
    "g'amgin": "Vazmin / Og'riqli muammo tahlili",
    "qo'rqqan": "Xavotirli",
    "charchagan": "Horg'in",
    "kinoyali": "Kinoyali",
}


def navoiy_resource_status() -> dict[str, Any]:
    s = load_cloud_secrets()
    modal_tts_url = s.get("modal_navoiy_webhook_url", "").strip()
    custom_url = s.get("navoiy_custom_url", "").strip()
    hf_tok = s.get("hf_token", "").strip() or os.getenv("HF_TOKEN", "").strip()
    if modal_tts_url:
        active = "Modal.com Dedicated T4 GPU (`aisha-org/navoiy-tts`, $0 Starter)"
    elif custom_url:
        active = f"Custom GPU Endpoint ({custom_url})"
    else:
        active = "Hugging Face Zero-A10G GPU (`aisha-org/navoiy-tts` Live API)" + (" + HF Pro/Token Quota" if hf_tok else "")
    return {
        "local_ram_gb": 1.9,
        "local_gpu": False,
        "local_can_host_weights_directly": False,
        "why_remote_gpu": "Navoiy TTS (CosyVoice2-0.5B + 1.88 GB checkpoint) ~4.8 GB CUDA VRAM talab qiladi; 0 MB lokal RAM bilan bulutli A10G/T4 GPU orqali ulandi.",
        "active_provider": active,
        "hf_token_configured": bool(hf_tok),
        "modal_navoiy_webhook_url": modal_tts_url,
        "emotions": NAVOIY_EMOTIONS,
    }


def _split_uzbek_sentences(text: str, max_chars: int = 380) -> list[str]:
    """Splits long Uzbek text cleanly below Navoiy's 500-char context window."""
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= max_chars:
        return [cleaned]
    raw_parts = re.split(r"(?<=[.!?…])\s+", cleaned)
    chunks: list[str] = []
    cur = ""
    for p in raw_parts:
        if not p:
            continue
        if len(cur) + len(p) + 1 <= max_chars:
            cur = f"{cur} {p}".strip()
        else:
            if cur:
                chunks.append(cur)
            if len(p) <= max_chars:
                cur = p
            else:
                for i in range(0, len(p), max_chars):
                    chunks.append(p[i:i + max_chars].strip())
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks or [cleaned[:max_chars]]


async def _call_hf_zero_gpu_single(
    session: aiohttp.ClientSession,
    text_chunk: str,
    emotion: str,
    speed: float,
    out_wav: Path,
    hf_token: str = "",
    space_base: str = HF_NAVOIY_SPACE_URL,
) -> bool:
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    payload = {"data": [text_chunk, emotion, round(max(0.8, min(1.2, speed)), 2)]}
    async with session.post(
        f"{space_base.rstrip('/')}/gradio_api/call/synthesize",
        json=payload,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        if resp.status != 200:
            return False
        call_data = await resp.json(content_type=None) or {}
        event_id = call_data.get("event_id")
        if not event_id:
            return False

    sse_headers = {"User-Agent": "Mozilla/5.0"}
    if hf_token:
        sse_headers["Authorization"] = f"Bearer {hf_token}"

    audio_url = ""
    current_event = ""
    async with session.get(
        f"{space_base.rstrip('/')}/gradio_api/call/synthesize/{event_id}",
        headers=sse_headers,
        timeout=aiohttp.ClientTimeout(total=150),
    ) as sse_resp:
        async for raw_bytes in sse_resp.content:
            line = raw_bytes.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
                if current_event == "error":
                    return False
                if current_event == "complete":
                    arr = json.loads(data_str)
                    if isinstance(arr, list) and arr and isinstance(arr[0], dict):
                        audio_url = arr[0].get("url") or ""
                        if not audio_url and arr[0].get("path"):
                            audio_url = f"{space_base.rstrip('/')}/gradio_api/file={arr[0]['path']}"
                    break

    if not audio_url:
        return False

    async with session.get(audio_url, headers=sse_headers, timeout=aiohttp.ClientTimeout(total=60)) as wav_resp:
        if wav_resp.status != 200:
            return False
        wav_bytes = await wav_resp.read()
        if len(wav_bytes) < 1000:
            return False
        out_wav.write_bytes(wav_bytes)
        return True


async def _call_modal_navoiy_webhook(
    session: aiohttp.ClientSession,
    webhook_url: str,
    text: str,
    emotion: str,
    speed: float,
    out_wav: Path,
) -> bool:
    async with session.post(
        webhook_url,
        json={"text": text, "emotion": emotion, "speed": speed},
        timeout=aiohttp.ClientTimeout(total=180),
    ) as resp:
        if resp.status != 200:
            return False
        d = await resp.json(content_type=None) or {}
        b64 = d.get("wav_base64", "")
        if not d.get("ok") or not b64:
            return False
        out_wav.write_bytes(base64.b64decode(b64))
        return True


async def _fallback_edge_tts_uzbek(text: str, out_wav: Path, speed: float = 1.0, voice: str = "uz-UZ-SardorNeural") -> str:
    import edge_tts

    norm_txt = normalize_uzbek_for_tts(text)
    rate_pct = int(round((speed - 1.0) * 100))
    rate_str = f"{rate_pct:+d}%"
    tmp_mp3 = out_wav.with_suffix(".edge.mp3")
    comm = edge_tts.Communicate(norm_txt, voice=voice, rate=rate_str)
    await comm.save(str(tmp_mp3))
    ffmpeg_bin = get_ffmpeg_bin()
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(tmp_mp3), "-ar", "24000", "-ac", "1", str(out_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    tmp_mp3.unlink(missing_ok=True)
    return f"edge_tts_fallback ({voice})"


def _probe_audio_duration(ffmpeg_bin: str, audio_path: Path) -> float:
    proc = subprocess.run([ffmpeg_bin, "-i", str(audio_path)], capture_output=True, text=True)
    info = (proc.stderr or "") + (proc.stdout or "")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


async def synthesize_uzbek_navoiy(
    text: str,
    out_wav: Path,
    emotion: str = "mehribon",
    speed: float = 1.0,
    pre_normalize: bool = True,
) -> dict[str, Any]:
    """
    Synthesizes expressive Uzbek speech via `aisha-org/navoiy-tts` (`24 kHz` WAV) using:
      1. Dedicated Modal T4 Webhook (if configured) ->
      2. Live Hugging Face `Zero-A10G` GPU (`uzbtrust/morfem-navoiy-tts`) ->
      3. Automatic `edge-tts` (`uz-UZ-SardorNeural`) fallback if GPU queue is busy.
    """
    VAULT_TMP.mkdir(parents=True, exist_ok=True)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_bin()
    emotion_key = emotion if emotion in NAVOIY_EMOTIONS else "mehribon"

    # Pre-expand %, $, @diyor.ctr, 24/7 so Navoiy pronounces tech copy naturally!
    prepared_text = normalize_uzbek_for_tts(text) if pre_normalize else text.strip()
    chunks = _split_uzbek_sentences(prepared_text, max_chars=360)

    s = load_cloud_secrets()
    modal_url = s.get("modal_navoiy_webhook_url", "").strip()
    custom_space = s.get("navoiy_custom_url", "").strip()
    hf_tok = s.get("hf_token", "").strip() or os.getenv("HF_TOKEN", "").strip()

    t0 = time.time()
    backend_used = ""

    with tempfile.TemporaryDirectory(prefix="navoiy_", dir=str(VAULT_TMP)) as tmpdir:
        td = Path(tmpdir)
        part_wavs: list[Path] = []

        async with aiohttp.ClientSession() as session:
            # 1. Try Dedicated Modal T4 GPU first if configured
            if modal_url:
                ok_all = True
                for idx, ch in enumerate(chunks):
                    pw = td / f"p_{idx:03d}.wav"
                    if not await _call_modal_navoiy_webhook(session, modal_url, ch, emotion_key, speed, pw):
                        ok_all = False
                        break
                    part_wavs.append(pw)
                if ok_all and part_wavs:
                    backend_used = "modal_t4_navoiy_tts"

            # 2. Try Live Hugging Face Zero-A10G Navoiy Space (or custom Gradio tunnel)
            if not backend_used:
                part_wavs.clear()
                target_space = custom_space or HF_NAVOIY_SPACE_URL
                ok_all = True
                for idx, ch in enumerate(chunks):
                    pw = td / f"p_{idx:03d}.wav"
                    try:
                        ok = await _call_hf_zero_gpu_single(session, ch, emotion_key, speed, pw, hf_token=hf_tok, space_base=target_space)
                    except Exception:
                        ok = False
                    if not ok:
                        ok_all = False
                        break
                    part_wavs.append(pw)
                if ok_all and part_wavs:
                    backend_used = "hf_zero_a10g_navoiy_tts"

        # Stitch chunks cleanly with gentle 120ms breath pause & EBU R128 -14.5 LUFS loudness normalization
        if backend_used and part_wavs:
            if len(part_wavs) == 1:
                raw_joined = part_wavs[0]
            else:
                silence_wav = td / "pause.wav"
                subprocess.run(
                    [ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.14", str(silence_wav)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                )
                interleaved: list[Path] = []
                for i, pw in enumerate(part_wavs):
                    if i > 0:
                        interleaved.append(silence_wav)
                    interleaved.append(pw)
                lst = td / "list.txt"
                lst.write_text("\n".join(f"file '{p.resolve()}'" for p in interleaved) + "\n", encoding="utf-8")
                raw_joined = td / "joined.wav"
                subprocess.run(
                    [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "24000", "-ac", "1", str(raw_joined)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                )

            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", str(raw_joined),
                    "-af", "silenceremove=start_periods=1:start_threshold=-46dB,loudnorm=I=-14.5:TP=-1.2:LRA=9",
                    "-ar", "48000", "-ac", "2", str(out_wav),
                ],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
        else:
            raw_fb = td / "fb.wav"
            backend_used = await _fallback_edge_tts_uzbek(text, raw_fb, speed=speed)
            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", str(raw_fb),
                    "-af", "loudnorm=I=-14.5:TP=-1.2:LRA=9",
                    "-ar", "48000", "-ac", "2", str(out_wav),
                ],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )

    dur = round(_probe_audio_duration(ffmpeg_bin, out_wav), 2)
    return {
        "ok": True,
        "output": str(out_wav),
        "duration": dur,
        "emotion": emotion_key,
        "speed": speed,
        "normalized_text": prepared_text,
        "backend": backend_used,
        "elapsed_sec": round(time.time() - t0, 2),
    }


def mux_navoiy_voice_onto_mp4(
    silent_or_fx_mp4: Path,
    voice_wav: Path,
    out_mp4: Path,
    cuts: list[float] | None = None,
    video_duration: float | None = None,
) -> Path:
    """
    Replaces/mixes a video's audio track with `Navoiy TTS` Uzbek narration (`-14.5 LUFS` foreground)
    + subtle `-21 dB` cut-locked Claude TechBrief UI chimes underneath!
    """
    ffmpeg_bin = get_ffmpeg_bin()
    v_dur = video_duration or _probe_audio_duration(ffmpeg_bin, silent_or_fx_mp4) or 10.0
    vo_dur = _probe_audio_duration(ffmpeg_bin, voice_wav)
    tempo_filter = ""
    if vo_dur > v_dur - 0.30 and v_dur > 1.5:
        ratio = min(1.55, vo_dur / max(1.0, v_dur - 0.35))
        tempo_filter = f"atempo={ratio:.3f},"

    with tempfile.TemporaryDirectory(prefix="nv_mux_", dir=str(VAULT_TMP)) as tmpdir:
        td = Path(tmpdir)
        fx_wav = td / "fx_bed.wav"
        build_fx_for_cuts(v_dur, cuts or [], str(fx_wav), lufs_target=-16.0)

        # Preserve exact `0.000s` voiceover sample phase (already calibrated to `-14.6 LUFS`!)
        # by summing foreground `vo` (`weight 1.0`) + subtle UI `fx` (`weight 0.11`) without single-pass loudnorm pump!
        filter_c = (
            f"[1:a]{tempo_filter}apad=whole_dur={v_dur:.3f},volume=0.86[vo];"
            f"[2:a]volume=0.10[fx];"
            f"[vo][fx]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            f"alimiter=limit=0.86:level=disabled:attack=5:release=50[aout]"
        )
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                ffmpeg_bin, "-y",
                "-i", str(silent_or_fx_mp4),
                "-i", str(voice_wav),
                "-i", str(fx_wav),
                "-filter_complex", filter_c,
                "-map", "0:v:0",
                "-map", "[aout]",
                "-t", f"{v_dur:.3f}",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
                str(out_mp4),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    return out_mp4
