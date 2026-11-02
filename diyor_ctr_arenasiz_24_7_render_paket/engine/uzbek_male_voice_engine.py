#!/usr/bin/env python3
"""
🎙 @diyor.ctr — $0-Cost Professional Male Uzbek Voice Engine (`uzbek_male_voice_engine.py`)
==========================================================================================
Navoiy TTS'dan tashqari 100% bepul ($0) ishlaydigan professional ERKAK o‘zbek ovozlari:

1. `sardor_founder`  — Microsoft Neural `uz-UZ-SardorNeural` + Shure SM7B Studio Podcast Mastering
                       (Tiniq, zamonaviy IT/Biznes ekspert erkak ovozi, 1.5s, $0 cheksiz).
2. `sardor_bariton`  — Microsoft Neural `uz-UZ-SardorNeural` + Chuqur Kino Bariton Mastering
                       (Salobatli, past tembrli hujjatli/reklama erkak ovozi, 1.5s, $0 cheksiz).
3. `meta_mms_male`   — Meta AI `facebook/mms-tts-uzb-script_cyrillic` (36.3M VITS erkak diktor,
                       100% lokal CPU da internet limitsiz ishlaydi, `speaking_rate=0.82`, $0).
4. `gemini_charon`   — Google Gemini 2.5 Flash Native TTS (`Charon` / `Orus` chuqur erkak ovozi —
                       agar bepul `GEMINI_API_KEY` kiritilsa, kuniga bepul limit ichida $0 ishlaydi).
5. `navoiy_tts`      — Aisha `aisha-org/navoiy-tts` (`Zero-A10G` / `Modal T4` GPU, ixtiyoriy).
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
import wave
from pathlib import Path
from typing import Any

import aiohttp

os.environ.setdefault("HF_HOME", "/home/user/.cache/hf_models")

TB_ROOT = Path("/home/user/claude-techbrief")
if str(TB_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "engine"))
if str(TB_ROOT / "vositalar") not in sys.path:
    sys.path.insert(0, str(TB_ROOT / "vositalar"))

from cloud_render_bridge import DIYOR_CLONE_WAV, load_cloud_secrets, post_modal_json, save_cloud_secrets  # noqa: E402
from motion_engine import get_ffmpeg_bin, VAULT_TMP  # noqa: E402
from uztts_normalize import normalize_uzbek_for_tts  # noqa: E402
from navoiy_tts_engine import synthesize_uzbek_navoiy, mux_navoiy_voice_onto_mp4  # noqa: E402

MALE_VOICE_PROFILES: dict[str, dict[str, str]] = {
    "sardor_bariton": {
        "label": "🎬 Sardor · Chuqur Kino Bariton (-6Hz Salobatli Past Tembr Erkak — ASOSIY, $0)",
        "engine": "edge_neural_baritone",
        "desc": "Asosiy tasdiqlangan tembr: chuqurlashtirilgan (-6Hz) kino/podkast bariton erkak ovozi (-14.5 LUFS).",
    },
    "modal_bariton_hd": {
        "label": "🚀 Modal T4 GPU · Kino Bariton HD (OmniVoice Diffusion-LM + SM7B — $30 Bepul Kredit)",
        "engine": "modal_omnivoice_gpu",
        "desc": "Modal T4 GPU ulangach Kino Bariton tembrini jonli nafas va neyron mikro-intonatsiya bilan kuchaytiradi.",
    },
    "modal_diyor_clone": {
        "label": "🎤 Modal T4 GPU · @diyor.ctr Shaxsiy Ovoz Klon (6–12s Ovozli Xabardan — $0)",
        "engine": "modal_omnivoice_clone",
        "desc": "Telegram botga yoki Studiyaga yuborilgan shaxsiy ovozingizni o‘zbek tilida klonlab gapiradi.",
    },
    "sardor_founder": {
        "label": "🎙 Sardor · Studio Founder (Tiniq Biznes/IT Ekspert Erkak — $0 Cheksiz)",
        "engine": "edge_neural_sm7b",
        "desc": "Microsoft Neural o‘zbek erkak diktori + Shure SM7B podkast tembri va dinamik urg‘u.",
    },
    "meta_mms_male": {
        "label": "🧠 Meta MMS · Lokal VITS Erkak Diktor (100% Offline CPU — $0 Cheksiz)",
        "engine": "meta_vits_local",
        "desc": "Meta AI ning 36M parametrli sof o‘zbek erkak VITS modeli (lokal CPU da ishlaydi).",
    },
    "gemini_orus": {
        "label": "✨ Gemini 2.5 · Orus Male (Bepul GEMINI_API_KEY bilan — $0 Studio Erkak)",
        "engine": "gemini_tts",
        "desc": "Google AI Studio bepul kaliti kiritilsa, Orus chuqur erkak ovozida o‘zbekcha o‘qiydi.",
    },
    "navoiy_mehribon": {
        "label": "🔊 Aisha Navoiy TTS (Zero-A10G / Modal GPU · Zaxira — $0)",
        "engine": "navoiy_gpu",
        "desc": "Oldingi bosqichda sinab ko‘rilgan Aisha CosyVoice2-0.5B modeli.",
    },
}

_MMS_CACHE: dict[str, Any] = {}


def _prepare_uzbek_for_sardor(text: str) -> str:
    """Normalizes numbers/units and converts ASCII apostrophes in o'/g' to official Uzbek `ʻ` (U+02BB)."""
    norm = normalize_uzbek_for_tts(text)
    norm = re.sub(r"\bavto-sotuv\b", "avtomatik sotuv", norm, flags=re.IGNORECASE)
    norm = re.sub(r"([oOgG])'", r"\1ʻ", norm)
    return norm


def _latin_to_uzbek_cyrillic(text: str) -> str:
    """Accurate Uzbek Latin -> Uzbek Cyrillic converter (`emas` -> `эмас`, `o'` -> `ў`, `g'` -> `ғ`, `q` -> `қ`, `h` -> `ҳ`)."""
    s = normalize_uzbek_for_tts(text)
    s = re.sub(r"\bavto-sotuv\b", "avtomatik sotuv", s, flags=re.IGNORECASE)
    # Digraphs first
    digraphs = [
        ("O'", "Ў"), ("o'", "ў"), ("Oʻ", "Ў"), ("oʻ", "ў"),
        ("G'", "Ғ"), ("g'", "ғ"), ("Gʻ", "Ғ"), ("gʻ", "ғ"),
        ("Sh", "Ш"), ("SH", "Ш"), ("sh", "ш"),
        ("Ch", "Ч"), ("CH", "Ч"), ("ch", "ч"),
        ("Yo", "Ё"), ("YO", "Ё"), ("yo", "ё"),
        ("Yu", "Ю"), ("YU", "Ю"), ("yu", "ю"),
        ("Ya", "Я"), ("YA", "Я"), ("ya", "я"),
        ("Ts", "Ц"), ("TS", "Ц"), ("ts", "ц"),
    ]
    for a, b in digraphs:
        s = s.replace(a, b)
    # Word-initial E/e -> Э/э in Uzbek Cyrillic!
    s = re.sub(r"(?<![A-Za-zА-Яа-яЎўҚқҒғҲҳ])E", "Э", s)
    s = re.sub(r"(?<![A-Za-zА-Яа-яЎўҚқҒғҲҳ])e", "э", s)
    s = s.replace("'", "ъ").replace("ʻ", "ъ")

    mp = {
        "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
        "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
        "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
        "x": "х", "y": "й", "z": "з",
    }
    out = []
    for ch in s:
        lo = ch.lower()
        if lo in mp:
            c = mp[lo]
            out.append(c.upper() if ch.isupper() else c)
        else:
            out.append(ch)
    return "".join(out)


def _split_clauses_for_prosody(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts or [text.strip()]


def _probe_dur(ffmpeg_bin: str, p: Path) -> float:
    proc = subprocess.run([ffmpeg_bin, "-i", str(p)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", (proc.stderr or ""))
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


async def _synth_sardor_studio(
    text: str,
    out_wav: Path,
    deep_baritone: bool = False,
    speed: float = 1.0,
) -> dict[str, Any]:
    """
    Synthesizes native Uzbekistan male voice (`uz-UZ-SardorNeural`) sentence-by-sentence with
    natural Hook->Body->CTA cadence, exact edge-only silence trimming (`areverse`), and Shure SM7B
    Studio Podcast Baritone EQ + Opto-Compression (`-14.5 LUFS`).
    """
    import edge_tts

    ffmpeg_bin = get_ffmpeg_bin()
    clean_txt = _prepare_uzbek_for_sardor(text)
    clauses = _split_clauses_for_prosody(clean_txt)

    base_rate = int(round((speed - 1.0) * 100)) + (4 if deep_baritone else 8)
    base_pitch = -6 if deep_baritone else -3

    with tempfile.TemporaryDirectory(prefix="sardor_sm7b_", dir=str(VAULT_TMP)) as tmpdir:
        td = Path(tmpdir)
        part_wavs: list[Path] = []

        for idx, cl in enumerate(clauses):
            # Subtle natural inflection: energetic Hook (+2% rate, +1Hz), steady Body, grounded CTA (-2% rate, -1Hz)
            if idx == 0 and len(clauses) > 1:
                r_off, p_off = 2, 1
            elif idx == len(clauses) - 1 and len(clauses) > 1:
                r_off, p_off = -1, -1
            else:
                r_off, p_off = 0, 0

            rate_str = f"{base_rate + r_off:+d}%"
            pitch_str = f"{base_pitch + p_off:+d}Hz"
            mp3_p = td / f"c_{idx:03d}.mp3"
            wav_p = td / f"c_{idx:03d}.wav"

            comm = edge_tts.Communicate(cl, voice="uz-UZ-SardorNeural", rate=rate_str, pitch=pitch_str)
            await comm.save(str(mp3_p))

            # Safe start + end trim ONLY (`areverse` trick never cuts internal pauses!)
            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", str(mp3_p),
                    "-af", (
                        "silenceremove=start_periods=1:start_threshold=-47dB,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-47dB,areverse"
                    ),
                    "-ar", "48000", "-ac", "1", str(wav_p),
                ],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            part_wavs.append(wav_p)

        if len(part_wavs) == 1:
            joined = part_wavs[0]
        else:
            pause_wav = td / "pause.wav"
            subprocess.run(
                [ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.12", str(pause_wav)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            seq: list[Path] = []
            for i, pw in enumerate(part_wavs):
                if i > 0:
                    seq.append(pause_wav)
                seq.append(pw)
            lst = td / "list.txt"
            lst.write_text("\n".join(f"file '{p.resolve()}'" for p in seq) + "\n", encoding="utf-8")
            joined = td / "joined.wav"
            subprocess.run(
                [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), str(joined)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )

        low_freq = 115 if deep_baritone else 132
        low_gain = 4.2 if deep_baritone else 3.4
        af_master = (
            f"highpass=f=72,"
            f"equalizer=f={low_freq}:t=q:w=1.0:g={low_gain},"
            f"equalizer=f=360:t=q:w=1.5:g=-2.0,"
            f"equalizer=f=3700:t=q:w=1.2:g=2.5,"
            f"treble=g=1.6:f=9200,"
            f"acompressor=threshold=-20dB:ratio=3.0:attack=10:release=130:makeup=2.4,"
            f"loudnorm=I=-14.5:TP=-1.2:LRA=7"
        )
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [ffmpeg_bin, "-y", "-i", str(joined), "-af", af_master, "-ar", "48000", "-ac", "2", str(out_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    return {
        "backend": "sardor_kino_bariton_sm7b" if deep_baritone else "sardor_studio_founder_sm7b",
        "normalized_text": clean_txt,
    }


def _synth_meta_mms_sync(text: str, out_wav: Path, speed: float = 1.0) -> dict[str, Any]:
    """Runs Meta AI's `facebook/mms-tts-uzb-script_cyrillic` (36.3M native Uzbek male VITS) locally on CPU."""
    import numpy as np
    import scipy.io.wavfile as wavfile
    import torch
    from transformers import AutoTokenizer, VitsModel

    ffmpeg_bin = get_ffmpeg_bin()
    model_id = "facebook/mms-tts-uzb-script_cyrillic"
    if "model" not in _MMS_CACHE:
        _MMS_CACHE["tok"] = AutoTokenizer.from_pretrained(model_id)
        _MMS_CACHE["model"] = VitsModel.from_pretrained(model_id).eval()

    tok = _MMS_CACHE["tok"]
    model = _MMS_CACHE["model"]
    # VITS speaking_rate < 1.0 means faster speech; 0.78 gives crisp ~125 WPM Reels tempo!
    model.config.speaking_rate = max(0.62, min(1.05, 0.78 / max(0.8, speed)))
    model.config.noise_scale = 0.5

    uz_cyr = _latin_to_uzbek_cyrillic(text)
    clauses = _split_clauses_for_prosody(uz_cyr)

    sr_hz = int(model.config.sampling_rate)
    audio_parts = []
    pause_samples = np.zeros(int(sr_hz * 0.12), dtype=np.float32)

    torch.manual_seed(42)
    with torch.no_grad():
        for i, cl in enumerate(clauses):
            inp = tok(cl, return_tensors="pt")
            w = model(**inp).waveform.squeeze().cpu().numpy().astype(np.float32)
            if i > 0:
                audio_parts.append(pause_samples)
            audio_parts.append(w)

    full_w = np.concatenate(audio_parts) if audio_parts else np.zeros(sr_hz, dtype=np.float32)
    peak = float(np.max(np.abs(full_w))) or 1.0
    wav_i16 = np.clip((full_w / peak) * 30000, -32768, 32767).astype(np.int16)

    with tempfile.TemporaryDirectory(prefix="mms_uz_", dir=str(VAULT_TMP)) as tmpdir:
        raw_w = Path(tmpdir) / "raw_16k.wav"
        wavfile.write(str(raw_w), sr_hz, wav_i16)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        # Upsample 16kHz -> 48kHz + brisk 1.38x Reels tempo + warm studio EQ & broadcast -14.5 LUFS!
        subprocess.run(
            [
                ffmpeg_bin, "-y", "-i", str(raw_w),
                "-af", (
                    "silenceremove=start_periods=1:start_threshold=-45dB,"
                    "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    f"atempo={min(1.65, max(0.85, 1.38 * speed)):.3f},"
                    "highpass=f=75,equalizer=f=135:t=q:w=1.1:g=2.8,"
                    "equalizer=f=3500:t=q:w=1.2:g=3.0,"
                    "acompressor=threshold=-19dB:ratio=2.6:attack=12:release=140,"
                    "loudnorm=I=-14.5:TP=-1.2:LRA=7"
                ),
                "-ar", "48000", "-ac", "2", str(out_wav),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    return {"backend": "meta_mms_vits_uzbek_male_cpu", "normalized_text": uz_cyr}


async def _synth_gemini_male(text: str, out_wav: Path, voice_name: str = "Orus") -> dict[str, Any] | None:
    """Uses Google AI Studio Free Tier (`GEMINI_API_KEY`) `gemini-2.5-flash-preview-tts` if key is set."""
    s = load_cloud_secrets()
    api_key = s.get("gemini_api_key", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    clean_txt = _prepare_uzbek_for_sardor(text)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"Ushbu oʻzbekcha matnni ishonchli, professional erkak biznes ekspert ovozida ravon oʻqib bering: {clean_txt}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}},
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=45)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None) or {}
            try:
                b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                pcm_bytes = base64.b64decode(b64)
            except Exception:
                return None

    ffmpeg_bin = get_ffmpeg_bin()
    with tempfile.TemporaryDirectory(prefix="gem_tts_", dir=str(VAULT_TMP)) as tmpdir:
        raw_wav = Path(tmpdir) / "gem_24k.wav"
        with wave.open(str(raw_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_bytes)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                ffmpeg_bin, "-y", "-i", str(raw_wav),
                "-af", "loudnorm=I=-14.5:TP=-1.2:LRA=7",
                "-ar", "48000", "-ac", "2", str(out_wav),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    return {"backend": f"gemini_2.5_flash_tts ({voice_name})", "normalized_text": clean_txt}


def save_diyor_clone_reference(in_audio_path: Path, ref_text: str = "") -> dict[str, Any]:
    """
    Converts a 4–12s voice message/upload (`.ogg`, `.mp3`, `.m4a`, `.wav`) into a clean `24 kHz` mono
    PCM reference WAV (`DIYOR_CLONE_WAV`) and auto-transcribes Uzbek `ref_text` if omitted.
    """
    ffmpeg_bin = get_ffmpeg_bin()
    DIYOR_CLONE_WAV.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg_bin, "-y", "-i", str(in_audio_path),
            "-af", (
                "silenceremove=start_periods=1:start_threshold=-44dB,"
                "areverse,silenceremove=start_periods=1:start_threshold=-44dB,areverse,"
                "highpass=f=75,loudnorm=I=-16:TP=-1.5:LRA=8"
            ),
            "-t", "10.5",
            "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(DIYOR_CLONE_WAV),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    dur = round(_probe_dur(ffmpeg_bin, DIYOR_CLONE_WAV), 2)
    final_txt = ref_text.strip()
    if not final_txt:
        try:
            import speech_recognition as sr
            rec = sr.Recognizer()
            with sr.AudioFile(str(DIYOR_CLONE_WAV)) as src:
                final_txt = rec.recognize_google(rec.record(src), language="uz-UZ")
        except Exception:
            final_txt = ""
    save_cloud_secrets({"diyor_clone_ref_text": final_txt})
    return {"ok": True, "wav_path": str(DIYOR_CLONE_WAV), "duration": dur, "ref_text": final_txt}


async def _synth_modal_voice_gpu(
    text: str,
    out_wav: Path,
    mode: str = "bariton_hd",
    speed: float = 1.0,
    target_duration: float | None = None,
) -> dict[str, Any] | None:
    """Calls `ModalVoiceGPU` (`diyor-ctr-voice-gpu.modal.run`) on NVIDIA T4 GPU if configured."""
    s = load_cloud_secrets()
    url = s.get("modal_voice_url", "").strip()
    if not url:
        return None

    payload: dict[str, Any] = {
        "mode": mode,
        "text": text,
        "speed": speed,
        "num_step": 32,
    }
    if target_duration:
        payload["duration"] = round(float(target_duration), 2)

    if mode == "voice_clone":
        if DIYOR_CLONE_WAV.exists() and DIYOR_CLONE_WAV.stat().st_size > 2000:
            payload["ref_wav_base64"] = base64.b64encode(DIYOR_CLONE_WAV.read_bytes()).decode("ascii")
            if s.get("diyor_clone_ref_text"):
                payload["ref_text"] = s["diyor_clone_ref_text"]
        else:
            # Until personal voice note is uploaded, use Kino Bariton HD reference
            payload["mode"] = "bariton_hd"

    try:
        data = await post_modal_json(url, payload, timeout_sec=150)
        if not data or not data.get("ok") or not data.get("wav_base64"):
            return None
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        out_wav.write_bytes(base64.b64decode(data["wav_base64"]))
        return {
            "backend": f"modal_cloud_8core_studio ({data.get('mode', payload['mode'])})",
            "normalized_text": data.get("normalized_text", text),
        }
    except Exception:
        return None


async def synthesize_pro_uzbek_voice(
    text: str,
    out_wav: Path,
    profile: str = "modal_bariton_hd",
    speed: float = 1.0,
    target_duration: float | None = None,
) -> dict[str, Any]:
    """Unified $0-cost professional Uzbek Male Voice dispatcher (defaults to `modal_bariton_hd`!)."""
    VAULT_TMP.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_bin()
    t0 = time.time()

    if profile == "modal_bariton_hd":
        m_res = await _synth_modal_voice_gpu(text, out_wav, mode="bariton_hd", speed=speed, target_duration=target_duration)
        if m_res is not None:
            info = m_res
        else:
            info = await _synth_sardor_studio(text, out_wav, deep_baritone=True, speed=speed)
            info["backend"] += " (Modal ulanishi kutilmoqda -> Kino Bariton ishlatildi)"
    elif profile == "modal_diyor_clone":
        m_res = await _synth_modal_voice_gpu(text, out_wav, mode="voice_clone", speed=speed, target_duration=target_duration)
        if m_res is not None:
            info = m_res
        else:
            info = await _synth_sardor_studio(text, out_wav, deep_baritone=True, speed=speed)
            info["backend"] += " (Modal ulanishi kutilmoqda -> Kino Bariton ishlatildi)"
    elif profile == "sardor_founder":
        info = await _synth_sardor_studio(text, out_wav, deep_baritone=False, speed=speed)
    elif profile == "meta_mms_male":
        info = await asyncio.to_thread(_synth_meta_mms_sync, text, out_wav, speed)
    elif profile == "gemini_orus":
        gem = await _synth_gemini_male(text, out_wav, voice_name="Orus")
        if gem is None:
            info = await _synth_sardor_studio(text, out_wav, deep_baritone=True, speed=speed)
            info["backend"] += " (GEMINI_API_KEY kiritilmagani uchun Kino Bariton ishlatildi)"
        else:
            info = gem
    elif profile == "navoiy_mehribon":
        nv = await synthesize_uzbek_navoiy(text, out_wav, emotion="mehribon", speed=speed)
        return {**nv, "profile": profile}
    else:
        # Default primary voice: `sardor_bariton` (`🎬 Sardor · Chuqur Kino Bariton`, -6Hz)!
        # If Modal T4 GPU is already live, optionally auto-boost if requested via env, else ultra-fast Kino Bariton
        s = load_cloud_secrets()
        if s.get("modal_voice_url") and s.get("auto_modal_bariton") == "1":
            m_res = await _synth_modal_voice_gpu(text, out_wav, mode="bariton_hd", speed=speed, target_duration=target_duration)
            if m_res is not None:
                info = m_res
            else:
                info = await _synth_sardor_studio(text, out_wav, deep_baritone=True, speed=speed)
        else:
            info = await _synth_sardor_studio(text, out_wav, deep_baritone=True, speed=speed)

    dur = round(_probe_dur(ffmpeg_bin, out_wav), 2)
    return {
        "ok": True,
        "output": str(out_wav),
        "profile": profile,
        "duration": dur,
        "speed": speed,
        "backend": info["backend"],
        "normalized_text": info["normalized_text"],
        "elapsed_sec": round(time.time() - t0, 2),
    }


__all__ = [
    "MALE_VOICE_PROFILES",
    "save_diyor_clone_reference",
    "synthesize_pro_uzbek_voice",
    "mux_navoiy_voice_onto_mp4",
]
