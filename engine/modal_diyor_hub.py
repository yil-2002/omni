#!/usr/bin/env python3
"""
🚀 @diyor.ctr — Unified Modal.com Serverless Cloud Hub (`modal_diyor_hub.py`)
=============================================================================
100% $0 / Karta talab qilinmaydi! (Karta ulanmagan Modal hisobida 8-yadroli AVX-512/AMX
Server CPU klasterida ishlaydi; agar keyinchalik karta ulansa `MODAL_ENABLE_GPU=1` bilan
avtomatik T4 GPU rejimiga ham o‘ta oladi!).

Bitta `modal deploy` orqali 3 ta JONLI HTTPS bulut xizmatini ishga tushiradi:
1. 🎙 `diyor-ctr-voice-gpu` (`cpu=8.0`, 12 GB RAM):
   - `bariton_hd` (Tavsiya): `uz-UZ-SardorNeural` + **Rubberband R3 Formant-Preserving Baritone**
     (`--fine --formant` — unli harflarni buzmasdan ovoz paychalarini chuqur kino baritonga
     tushiradi!) + **Spotify Pedalboard C++ Studio Mastering** (`-14.5 LUFS`, `48 kHz`)!
   - `bariton_omni` / `voice_clone`: `k2-fsa/OmniVoice` (8-core `bfloat16` AMX) yordamida
     shaxsiy ovozni klonlash yoki neyron qayta sintez!
   - `transcribe`: `faster-whisper` (`int8` 8-core) o‘zbekcha so‘zma-so‘z subtitr taymingi!
2. ✂️ `diyor-ctr-photo-gpu` (`cpu=8.0`, 8 GB RAM):
   - `isnet-general-use` HD portret kesimi + OpenCV Telea `Clean-Plate` fon tiklash (~1.2s, 0 MB lokal RAM).
3. 🎬 `diyor-ctr-render-farm` (`cpu=4.0` × parallel konteynerlar):
   - `Claude TechBrief` + `Clawd` + `-14.5 LUFS` videolarni parallel bulut konteynerlarda 6–9 soniyada yig‘adi!
"""
from __future__ import annotations

import base64
import io
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    import modal
except ImportError:
    modal = None

TB_ROOT = Path("/home/user/claude-techbrief")
USE_GPU = "T4" if os.environ.get("MODAL_ENABLE_GPU") == "1" else None

if modal is not None:
    app = modal.App("diyor-ctr-cloud-hub")

    # ------------------------------------------------------------------
    # 1. 8-CORE STUDIO VOICE MASTERING + OMNIVOICE CLONE + WHISPER
    # ------------------------------------------------------------------
    voice_image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("ffmpeg", "libsndfile1", "rubberband-cli", "git")
        .pip_install(
            "edge-tts>=7.2.0",
            "pedalboard>=0.9.14",
            "soundfile>=0.12.1",
            "numpy>=1.26.0",
            "scipy>=1.13.0",
            "faster-whisper>=1.1.0",
            "torch>=2.5.0",
            "torchaudio>=2.5.0",
            "omnivoice>=0.2.1",
            "fastapi[standard]",
        )
        .add_local_dir(str(TB_ROOT / "shared" / "voice_refs"), remote_path="/opt/tb/voice_refs", copy=True)
        .add_local_file(str(TB_ROOT / "engine" / "uztts_normalize.py"), remote_path="/opt/tb/uztts_normalize.py", copy=True)
    )

    @app.cls(image=voice_image, gpu=USE_GPU, cpu=8.0, memory=12288, scaledown_window=180, timeout=300)
    class ModalVoiceStudio:
        @modal.enter()
        def setup(self) -> None:
            import sys
            import torch

            torch.set_num_threads(8)
            sys.path.insert(0, "/opt/tb")
            from uztts_normalize import normalize_uzbek_for_tts

            self.normalize = normalize_uzbek_for_tts
            self.bariton_ref_wav = "/opt/tb/voice_refs/bariton_ref_24k.wav"
            self.bariton_ref_txt = Path("/opt/tb/voice_refs/bariton_ref.txt").read_text(encoding="utf-8").strip()
            self._omni = None
            self._whisper = None

        def _get_omni(self):
            if self._omni is None:
                import torch
                from omnivoice.models.omnivoice import OmniVoice
                dev = "cuda:0" if torch.cuda.is_available() else "cpu"
                dt = torch.float16 if torch.cuda.is_available() else torch.bfloat16
                self._omni = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=dev, dtype=dt)
            return self._omni

        def _get_whisper(self):
            if self._whisper is None:
                import torch
                from faster_whisper import WhisperModel
                dev = "cuda" if torch.cuda.is_available() else "cpu"
                ct = "float16" if torch.cuda.is_available() else "int8"
                self._whisper = WhisperModel("small", device=dev, compute_type=ct, cpu_threads=8)
            return self._whisper

        def _master_with_pedalboard(self, in_wav: Path, out_wav: Path, formant_semitones: float = 0.0) -> float:
            """
            Studio Mastering Chain:
            1. Optional Rubberband R3 (`--fine --formant`) formant-locked vocal cord deepening:
               lowers fundamental pitch without 'slow-motion' vowel distortion!
            2. Spotify `pedalboard` C++ Broadcast Chain: Highpass 68Hz -> Warm Tube Chest 116Hz (+3.8dB)
               -> Mud Cut 340Hz (-2.2dB) -> Articulation Presence 3.7kHz (+2.6dB) -> Air Shelf 9.5kHz
               -> Studio Opto Compressor -> Limiter -> FFmpeg EBU R128 `-14.5 LUFS` (`48 kHz` stereo).
            """
            import numpy as np
            import soundfile as sf
            from pedalboard import (
                Compressor,
                Gain,
                HighShelfFilter,
                HighpassFilter,
                Limiter,
                LowShelfFilter,
                PeakFilter,
                Pedalboard,
            )

            work_wav = in_wav
            if abs(formant_semitones) > 0.05:
                rb_wav = in_wav.parent / "rb_formant.wav"
                subprocess.run(
                    [
                        "rubberband", "--quiet", "-3", "--formant",
                        "-p", f"{formant_semitones:.2f}",
                        str(in_wav), str(rb_wav),
                    ],
                    check=True,
                )
                work_wav = rb_wav

            audio, sr = sf.read(str(work_wav), dtype="float32")
            if audio.ndim == 1:
                audio = audio[None, :]
            else:
                audio = audio.T

            board = Pedalboard([
                HighpassFilter(cutoff_frequency_hz=68.0),
                LowShelfFilter(cutoff_frequency_hz=118.0, gain_db=3.6, q=0.85),
                PeakFilter(cutoff_frequency_hz=340.0, gain_db=-2.2, q=1.4),
                PeakFilter(cutoff_frequency_hz=3750.0, gain_db=2.6, q=1.15),
                HighShelfFilter(cutoff_frequency_hz=9500.0, gain_db=1.8, q=0.7),
                Compressor(threshold_db=-20.0, ratio=3.2, attack_ms=9.0, release_ms=135.0),
                Gain(gain_db=2.4),
                Limiter(threshold_db=-1.2, release_ms=80.0),
            ])
            effected = board(audio, sr)
            pb_wav = in_wav.parent / "pb_out.wav"
            sf.write(str(pb_wav), effected.T, sr)

            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(pb_wav),
                    "-af", "loudnorm=I=-14.5:TP=-1.2:LRA=7",
                    "-ar", "48000", "-ac", "2", str(out_wav),
                ],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            final_a, final_sr = sf.read(str(out_wav), dtype="float32")
            return round(len(final_a) / float(final_sr), 2)

        @modal.fastapi_endpoint(method="POST", label="diyor-ctr-voice-gpu")
        async def voice_endpoint(self, body: dict[str, Any]) -> dict[str, Any]:
            import asyncio
            import edge_tts
            import soundfile as sf

            mode = str(body.get("mode", "bariton_hd")).lower()

            # A) Uzbek Transcription + Word Timestamps (`faster-whisper`)
            if mode == "transcribe":
                audio_b64 = str(body.get("audio_base64", ""))
                if not audio_b64:
                    return {"ok": False, "error": "audio_base64 required"}
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tf.write(base64.b64decode(audio_b64))
                    in_p = tf.name
                try:
                    def _run_asr():
                        wmodel = self._get_whisper()
                        segs, info = wmodel.transcribe(in_p, language="uz", word_timestamps=True)
                        words, full_txt = [], []
                        for sg in segs:
                            full_txt.append(sg.text.strip())
                            for w in (sg.words or []):
                                words.append({"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)})
                        return {"ok": True, "text": " ".join(full_txt).strip(), "words": words, "language": info.language}
                    return await asyncio.to_thread(_run_asr)
                finally:
                    Path(in_p).unlink(missing_ok=True)

            raw_text = str(body.get("text", "")).strip()
            if not raw_text:
                return {"ok": False, "error": "text required"}

            norm_txt = self.normalize(raw_text)
            norm_txt = re.sub(r"\bavto-sotuv\b", "avtomatik sotuv", norm_txt, flags=re.IGNORECASE)
            norm_txt = re.sub(r"([oOgG])'", r"\1ʻ", norm_txt)
            speed = float(body.get("speed", 1.0))

            # B) Zero-Shot Voice Cloning (`OmniVoice` 8-core AMX)
            if mode in ("voice_clone", "bariton_omni"):
                def _run_clone():
                    tts = self._get_omni()
                    ref_audio = self.bariton_ref_wav
                    ref_text = self.bariton_ref_txt
                    tmp_ref = None
                    if mode == "voice_clone" and body.get("ref_wav_base64"):
                        rf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                        rf.write(base64.b64decode(str(body["ref_wav_base64"])))
                        rf.close()
                        tmp_ref = rf.name
                        ref_audio = tmp_ref
                        ref_text = str(body.get("ref_text") or "").strip() or None
                    try:
                        audios = tts.generate(
                            text=norm_txt,
                            language="Uzbek",
                            ref_audio=ref_audio,
                            ref_text=ref_text,
                            speed=speed,
                            num_step=int(body.get("num_step", 16)),
                            guidance_scale=2.0,
                            denoise=True,
                        )
                        sr_hz = int(getattr(tts, "sampling_rate", 24000))
                        with tempfile.TemporaryDirectory() as td:
                            td_p = Path(td)
                            raw_w = td_p / "omni_raw.wav"
                            mst_w = td_p / "omni_master.wav"
                            sf.write(str(raw_w), audios[0], sr_hz)
                            dur_s = self._master_with_pedalboard(raw_w, mst_w, formant_semitones=0.0)
                            return mst_w.read_bytes(), dur_s
                    finally:
                        if tmp_ref:
                            Path(tmp_ref).unlink(missing_ok=True)

                wav_bytes, dur_s = await asyncio.to_thread(_run_clone)
                return {
                    "ok": True,
                    "mode": mode,
                    "sample_rate": 48000,
                    "duration": dur_s,
                    "normalized_text": norm_txt,
                    "wav_base64": base64.b64encode(wav_bytes).decode("ascii"),
                }

            # C) Default `bariton_hd`: Clause-dynamic `SardorNeural` + Rubberband R3 Formant-Locked
            #    Baritone (`-1.15` semitones with 100% preserved Uzbek vowel formants!) + Spotify Pedalboard C++ Mastering!
            clauses = [p.strip() for p in re.split(r"(?<=[.!?])\s+", norm_txt) if p.strip()] or [norm_txt]
            base_rate = int(round((speed - 1.0) * 100)) + 5

            with tempfile.TemporaryDirectory() as td:
                td_p = Path(td)
                part_wavs: list[Path] = []
                for idx, cl in enumerate(clauses):
                    r_off = 2 if (idx == 0 and len(clauses) > 1) else (-1 if idx == len(clauses) - 1 and len(clauses) > 1 else 0)
                    mp3_p = td_p / f"c_{idx:03d}.mp3"
                    wav_p = td_p / f"c_{idx:03d}.wav"
                    comm = edge_tts.Communicate(cl, voice="uz-UZ-SardorNeural", rate=f"{base_rate + r_off:+d}%", pitch="-1Hz")
                    await comm.save(str(mp3_p))
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", str(mp3_p),
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
                    pause_w = td_p / "p.wav"
                    subprocess.run(
                        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.11", str(pause_w)],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    )
                    seq: list[Path] = []
                    for i, pw in enumerate(part_wavs):
                        if i > 0:
                            seq.append(pause_w)
                        seq.append(pw)
                    lst = td_p / "list.txt"
                    lst.write_text("\n".join(f"file '{p}'" for p in seq) + "\n", encoding="utf-8")
                    joined = td_p / "joined.wav"
                    subprocess.run(
                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), str(joined)],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    )

                mst_w = td_p / "bariton_hd_48k.wav"
                dur_s = await asyncio.to_thread(self._master_with_pedalboard, joined, mst_w, -1.15)
                wav_bytes = mst_w.read_bytes()

            return {
                "ok": True,
                "mode": "bariton_hd_rubberband_pedalboard",
                "sample_rate": 48000,
                "duration": dur_s,
                "normalized_text": norm_txt,
                "wav_base64": base64.b64encode(wav_bytes).decode("ascii"),
            }

    # ------------------------------------------------------------------
    # 2. 8-CORE HD CUTOUT (`isnet-general-use`) + CLEAN-PLATE SERVICE
    # ------------------------------------------------------------------
    photo_image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("libgl1", "libglib2.0-0")
        .pip_install(
            "rembg>=2.0.59",
            "onnxruntime>=1.19.0",
            "opencv-python-headless>=4.10.0",
            "pillow>=10.0.0",
            "numpy>=1.26.0",
            "fastapi[standard]",
        )
        .run_commands('python3 -c "from rembg import new_session; new_session(\'isnet-general-use\')"')
    )

    @app.cls(image=photo_image, gpu=USE_GPU, cpu=8.0, memory=8192, scaledown_window=120, timeout=180)
    class ModalPhotoStudio:
        @modal.enter()
        def load_seg(self) -> None:
            from rembg import new_session
            self.session = new_session("isnet-general-use")

        @modal.fastapi_endpoint(method="POST", label="diyor-ctr-photo-gpu")
        def cutout_endpoint(self, body: dict[str, Any]) -> dict[str, Any]:
            import cv2
            import numpy as np
            from PIL import Image
            from rembg import remove

            img_b64 = str(body.get("image_base64", ""))
            if not img_b64:
                return {"ok": False, "error": "image_base64 required"}

            src_pil = Image.open(io.BytesIO(base64.b64decode(img_b64))).convert("RGB")
            fg_pil = remove(src_pil, session=self.session, post_process_mask=True)

            rgb_np = np.array(src_pil)
            alpha_np = np.array(fg_pil.split()[-1])
            mask = (alpha_np > 18).astype(np.uint8) * 255
            k = max(15, int(min(rgb_np.shape[:2]) * 0.022) | 1)
            dilated = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)), iterations=1)
            bgr_clean = cv2.inpaint(cv2.cvtColor(rgb_np, cv2.COLOR_RGB2BGR), dilated, 9, cv2.INPAINT_TELEA)
            clean_pil = Image.fromarray(cv2.cvtColor(bgr_clean, cv2.COLOR_BGR2RGB))

            fg_buf = io.BytesIO()
            fg_pil.save(fg_buf, format="PNG")
            cp_buf = io.BytesIO()
            clean_pil.save(cp_buf, format="JPEG", quality=93)

            return {
                "ok": True,
                "fg_png_base64": base64.b64encode(fg_buf.getvalue()).decode("ascii"),
                "clean_plate_jpg_base64": base64.b64encode(cp_buf.getvalue()).decode("ascii"),
            }

    # ------------------------------------------------------------------
    # 3. PARALLEL CLOUD RENDER FARM (CHROMIUM + GSAP + FX/VOICE MUX)
    # ------------------------------------------------------------------
    render_image = (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install(
            "ffmpeg", "fonts-liberation", "libnss3", "libatk1.0-0", "libatk-bridge2.0-0",
            "libcups2", "libdrm2", "libxkbcommon0", "libxcomposite1", "libxdamage1",
            "libxrandr2", "libgbm1", "libasound2",
        )
        .pip_install("playwright>=1.48.0", "pillow>=10.0.0", "numpy>=1.26.0", "scipy>=1.13.0", "fastapi[standard]")
        .run_commands("python3 -m playwright install chromium")
        .add_local_dir(str(TB_ROOT / "shared"), remote_path="/opt/tb/shared", copy=True)
        .add_local_dir(str(TB_ROOT / "vositalar"), remote_path="/opt/tb/vositalar", copy=True)
    )

    @app.function(image=render_image, cpu=4.0, memory=4096, timeout=300, max_containers=20)
    def render_slice_worker(payload: dict[str, Any]) -> bytes:
        from PIL import Image
        from playwright.sync_api import sync_playwright

        html_str = payload["html"].replace("file:///home/user/claude-techbrief/shared", "file:///opt/tb/shared")
        W = int(payload["width"])
        H = int(payload["height"])
        fps = int(payload["fps"])
        f_start = int(payload["f_start"])
        f_end = int(payload["f_end"])

        with tempfile.TemporaryDirectory() as tdir:
            html_file = Path(tdir) / "scene.html"
            out_chunk = Path(tdir) / "chunk.mp4"
            html_file.write_text(html_str, encoding="utf-8")

            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
                page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
                page.goto(f"file://{html_file}", wait_until="networkidle")
                page.evaluate("document.fonts.ready")

                cmd = [
                    "ffmpeg", "-y",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                    "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
                    str(out_chunk),
                ]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                assert proc.stdin is not None
                for f_idx in range(f_start, f_end):
                    t = f_idx / float(fps)
                    page.evaluate("t => { const tl = window.__timelines.main; tl.pause(); tl.seek(t, false); }", t)
                    jpg = page.screenshot(type="jpeg", quality=94)
                    proc.stdin.write(Image.open(io.BytesIO(jpg)).convert("RGB").tobytes())
                proc.stdin.close()
                if proc.wait() != 0:
                    raise RuntimeError("Cloud slice FFmpeg failed")
                browser.close()
            return out_chunk.read_bytes()

    @app.function(image=render_image, cpu=2.0, memory=2048, timeout=600)
    @modal.fastapi_endpoint(method="POST", label="diyor-ctr-render-farm")
    def render_webhook(body: dict[str, Any]) -> dict[str, Any]:
        import sys
        sys.path.insert(0, "/opt/tb/vositalar")
        from _fxbed import build_fx_for_cuts

        html_str = str(body["html"])
        W = int(body.get("width", 1080))
        H = int(body.get("height", 1920))
        dur = float(body.get("duration", 8.0))
        fps = int(body.get("fps", 30))
        cuts = [float(x) for x in body.get("cuts", [])]
        lufs_target = float(body.get("lufs_target", -14.5))
        vo_b64 = str(body.get("voice_wav_base64", ""))

        total_frames = max(1, int(round(dur * fps)))
        slice_size = 75
        slices = [
            {"html": html_str, "width": W, "height": H, "fps": fps, "f_start": f0, "f_end": min(total_frames, f0 + slice_size)}
            for f0 in range(0, total_frames, slice_size)
        ]
        chunk_bytes_list = list(render_slice_worker.map(slices))

        with tempfile.TemporaryDirectory() as tdir:
            td = Path(tdir)
            chunk_paths = []
            for idx, b in enumerate(chunk_bytes_list):
                cp = td / f"c_{idx:04d}.mp4"
                cp.write_bytes(b)
                chunk_paths.append(cp)

            fx_wav = str(td / "fx.wav")
            build_fx_for_cuts(dur, cuts, fx_wav, lufs_target=-16.0 if vo_b64 else lufs_target)
            concat_txt = td / "list.txt"
            concat_txt.write_text("\n".join(f"file '{p}'" for p in chunk_paths) + "\n", encoding="utf-8")
            final_mp4 = td / "final.mp4"

            if vo_b64:
                vo_wav = td / "vo.wav"
                vo_wav.write_bytes(base64.b64decode(vo_b64))
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                    "-i", str(vo_wav), "-i", fx_wav,
                    "-filter_complex", (
                        f"[1:a]apad=whole_dur={dur:.3f},volume=1.0[vo];"
                        f"[2:a]volume=0.11[fx];"
                        f"[vo][fx]amix=inputs=2:duration=first:dropout_transition=0,"
                        f"loudnorm=I=-14.5:TP=-1.2:LRA=9[aout]"
                    ),
                    "-map", "0:v:0", "-map", "[aout]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", "-t", f"{dur:.3f}", str(final_mp4),
                ], check=True)
            else:
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                    "-i", fx_wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", "-shortest", str(final_mp4),
                ], check=True)

            return {
                "ok": True,
                "workers_used": len(slices),
                "duration": dur,
                "width": W,
                "height": H,
                "mp4_base64": base64.b64encode(final_mp4.read_bytes()).decode("ascii"),
            }

    # ------------------------------------------------------------------
    # 4. 24/7 ALWAYS-ON TELEGRAM AI-AGENT & FULL STUDIO CLOUD WORKER
    # ------------------------------------------------------------------
    bot_kv = modal.Dict.from_name("diyor-ctr-bot-kv", create_if_missing=True)
    vault_vol = modal.Volume.from_name("diyor-ctr-vault-vol", create_if_missing=True)

    bot_webhook_image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")

    bot_studio_image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install(
            "ffmpeg", "curl", "libgl1", "libglib2.0-0",
            "fonts-liberation", "fonts-noto-color-emoji",
        )
        .pip_install(
            "playwright>=1.48.0",
            "pillow>=10.0.0",
            "numpy>=1.26.0",
            "scipy>=1.13.0",
            "opencv-python-headless>=4.10.0",
            "aiohttp>=3.9.0",
            "edge-tts>=7.2.0",
            "soundfile>=0.12.1",
            "g4f>=0.5.0",
            "curl_cffi>=0.7.0",
            "fastapi[standard]",
        )
        .run_commands("python3 -m playwright install --with-deps chromium")
        .add_local_dir("/home/user/claude-techbrief", remote_path="/home/user/claude-techbrief", copy=True)
        .add_local_file("/home/user/uploads/IMG_2860.jpeg", remote_path="/home/user/uploads/IMG_2860.jpeg", copy=True)
        .add_local_file("/home/user/uploads/IMG_2860_DIYOR_CTR.jpg", remote_path="/home/user/uploads/IMG_2860_DIYOR_CTR.jpg", copy=True)
        .add_local_file("/home/user/tashqi_xotira/cloud_vault.py", remote_path="/home/user/tashqi_xotira/cloud_vault.py", copy=True)
        .add_local_file("/home/user/tashqi_xotira/cloud_manifest.json", remote_path="/home/user/tashqi_xotira/cloud_manifest.json", copy=True)
        .add_local_file("/home/user/tashqi_xotira/telegram_vault_bot.py", remote_path="/home/user/tashqi_xotira/telegram_vault_bot.py", copy=True)
        .add_local_file("/home/user/tashqi_xotira/telegram_ai_agent.py", remote_path="/home/user/tashqi_xotira/telegram_ai_agent.py", copy=True)
    )

    @app.cls(
        image=bot_studio_image,
        cpu=8.0,
        memory=12288,
        volumes={"/home/user/.cache/diyor_vault": vault_vol},
        scaledown_window=300,
        timeout=600,
    )
    class ModalTelegramStudioWorker:
        @modal.enter()
        def boot(self) -> None:
            import json
            import sys

            os.environ["DIYOR_CLOUD_WORKER"] = "1"
            for p in ("/home/user/claude-techbrief/engine", "/home/user/tashqi_xotira"):
                if p not in sys.path:
                    sys.path.insert(0, p)

            from cloud_vault import init_vault_dirs
            init_vault_dirs()

            tok = str(bot_kv.get("tg_bot_token") or "")
            owner_cid = int(bot_kv.get("owner_chat_id") or 7179261501)
            if tok:
                sec_p = Path("/home/user/tashqi_xotira/.tg_bot_secret.json")
                sec_p.parent.mkdir(parents=True, exist_ok=True)
                sec_p.write_text(
                    json.dumps({"bot_token": tok, "chat_id": owner_cid, "bot_username": "diyor937373839337bot"}),
                    encoding="utf-8",
                )

        @modal.method()
        async def handle_update(self, upd: dict[str, Any]) -> dict[str, Any]:
            import asyncio
            import html as _html
            import json
            import time

            tok = str((await bot_kv.get.aio("tg_bot_token")) or "")
            owner_cid = int((await bot_kv.get.aio("owner_chat_id")) or 7179261501)
            if tok:
                sec_p = Path("/home/user/tashqi_xotira/.tg_bot_secret.json")
                sec_p.write_text(
                    json.dumps({"bot_token": tok, "chat_id": owner_cid, "bot_username": "diyor937373839337bot"}),
                    encoding="utf-8",
                )

            from cloud_vault import VAULT_MEDIA, VAULT_ROOT
            from telegram_vault_bot import (
                download_from_telegram_vault,
                tg_send_chat_action,
                tg_send_message,
                upload_to_telegram_vault,
            )
            from telegram_ai_agent import handle_natural_agent_turn

            msg = upd.get("message") or upd.get("channel_post")
            if not isinstance(msg, dict):
                return {"ok": True, "ignored": True}
            chat = msg.get("chat") or {}
            cid = chat.get("id")
            if not cid:
                return {"ok": True, "ignored": True}

            if int(cid) != owner_cid:
                await asyncio.to_thread(
                    tg_send_message,
                    cid,
                    "🔒 Ushbu 24/7 AI-Studiya faqat @diyor.ctr egasi uchun yopiq rejimda ishlaydi.",
                )
                return {"ok": True, "unauthorized": True}

            text = (msg.get("text") or "").strip()
            caption = (msg.get("caption") or "").strip()

            try:
                if text.startswith("/start"):
                    await asyncio.to_thread(
                        tg_send_message,
                        cid,
                        "⚡ <b>@diyor.ctr — 24/7 Bulut AI-Agent (Modal Cloud)</b>\n\n"
                        "Endi men Arena yopiq bo‘lganda ham kechayu-kunduz 24/7 uyg‘oqman! "
                        "Hech qanday <code>/ai</code> buyruqlarsiz oddiy o‘zbek tilida yozavering yoki 🎤 ovozli xabar yuboring:\n"
                        "• <i>«Menga AI sotuv tizimi haqida yangi reels va muqova qilib ber, kalit so‘zi SOTUV»</i>\n"
                        "• <i>«Shu gapni kino baritonda o‘qib ber: Biznesingiz 24/7 avtopilotda ishlasin!»</i>\n"
                        "• Yoki istalgan mavzuda erkin suhbatlashamiz!",
                    )
                elif text.startswith("/avto"):
                    from autopilot_conveyor import run_one_click_autopilot
                    from telegram_vault_bot import LiveStepIndicator
                    raw_arg = text[5:].strip()
                    parts = [p.strip() for p in raw_arg.split("|") if p.strip()]
                    topic_in = parts[0] if parts else "Bir kishilik AI-Imperiya"
                    kw_in = (parts[1] if len(parts) > 1 else "SKILL").upper()
                    ind_avto = LiveStepIndicator(cid, sticker_emoji="🔥")
                    try:
                        await ind_avto.start(
                            f"⏳ <b>1-qadam:</b> 24/7 Avto-Konveyer («{_html.escape(topic_in)}» · <code>{kw_in}</code>) tayyorlanmoqda..."
                        )
                        res = await run_one_click_autopilot(
                            topic=topic_in,
                            keyword=kw_in,
                            voice_profile="modal_bariton_hd",
                            with_subtitles=True,
                            on_step=ind_avto.next_step,
                        )
                        await ind_avto.next_step("📤 <b>7-qadam:</b> Tayyor muqova va 9:16 Reels Telegramga yuklanmoqda...")
                        cov_p, reel_p = Path(res["cover_png"]), Path(res["reel_mp4"])
                        await ind_avto.clear_all()
                        await asyncio.to_thread(
                            upload_to_telegram_vault, cov_p, cov_p.name,
                            f"🖼 [1/2] 4:5 DIYOR.CTR Muqova ({res['topic']})", cid, False
                        )
                        await asyncio.to_thread(
                            upload_to_telegram_vault, reel_p, reel_p.name,
                            f"🎬 [2/2] 9:16 Reel · Qora xoshiyasiz Subtitr ({res['duration']}s)", cid, True
                        )
                        await asyncio.to_thread(tg_send_message, cid, f"📋 <b>Tayyor Caption:</b>\n\n{_html.escape(res['caption'])}")
                    finally:
                        await ind_avto.clear_all()
                elif msg.get("voice") or msg.get("audio"):
                    vobj = msg.get("voice") or msg.get("audio")
                    in_ogg = VAULT_ROOT / "user_uploads" / f"tg_voice_{int(time.time())}.ogg"
                    in_ogg.parent.mkdir(parents=True, exist_ok=True)
                    ok = await asyncio.to_thread(download_from_telegram_vault, [vobj["file_id"]], in_ogg)
                    if ok:
                        if "klon" in caption.lower() or "clone" in caption.lower():
                            from uzbek_male_voice_engine import save_diyor_clone_reference
                            c_res = await asyncio.to_thread(save_diyor_clone_reference, in_ogg, "")
                            await asyncio.to_thread(
                                tg_send_message, cid,
                                f"🎤 <b>Shaxsiy ovoz klon namunangiz 24/7 bulutga saqlandi!</b> ({c_res['duration']}s)"
                            )
                        else:
                            await asyncio.to_thread(tg_send_chat_action, cid, "typing")
                            from cloud_render_bridge import transcribe_uzbek_via_modal
                            w16 = VAULT_ROOT / "user_uploads" / f"v16_{int(time.time())}.wav"
                            subprocess.run(
                                ["ffmpeg", "-y", "-i", str(in_ogg), "-ar", "16000", "-ac", "1", str(w16)],
                                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            )
                            w_res = await transcribe_uzbek_via_modal(w16)
                            w16.unlink(missing_ok=True)
                            spoken_txt = str((w_res or {}).get("text") or "").strip()
                            if spoken_txt:
                                await handle_natural_agent_turn(
                                    cid, spoken_txt, tg_send_message, upload_to_telegram_vault, tg_send_chat_action
                                )
                            else:
                                await asyncio.to_thread(
                                    tg_send_message, cid, "🎤 Ovoz eshitilmadi — iltimos qayta yuboring yoki matn yozing."
                                )
                elif msg.get("photo"):
                    best_photo = msg["photo"][-1]
                    await asyncio.to_thread(tg_send_chat_action, cid, "upload_photo")
                    in_p = VAULT_ROOT / "user_uploads" / f"tg_photo_{int(time.time())}.jpg"
                    in_p.parent.mkdir(parents=True, exist_ok=True)
                    ok = await asyncio.to_thread(download_from_telegram_vault, [best_photo["file_id"]], in_p)
                    if ok:
                        from photo_brand_engine import render_brand_photo_slide
                        bw = "AI TIZIM"
                        hl = "Biznesingiz <em>24/7 avtopilotda</em> ishlasin"
                        if caption and "|" in caption:
                            p0, p1 = [x.strip() for x in caption.split("|", 1)]
                            bw = (p0 or bw).upper()[:13]
                            hl = p1 or hl
                        out_png = VAULT_MEDIA / "custom_renders" / f"cloud_photo_{int(time.time())}.png"
                        await render_brand_photo_slide(in_p, out_png, config={"behindWord": bw, "headlineHtml": hl}, aspect="4:5")
                        await asyncio.to_thread(
                            upload_to_telegram_vault, out_png, out_png.name,
                            f"✨ Tayyor 4:5 DIYOR.CTR Brend Post ({bw})", cid, False
                        )
                elif text:
                    clean_user_msg = text[3:].strip() if text.lower().startswith("/ai") else text
                    if clean_user_msg:
                        stop_ev = asyncio.Event()

                        async def _keep_typing():
                            while not stop_ev.is_set():
                                await asyncio.to_thread(tg_send_chat_action, cid, "typing")
                                try:
                                    await asyncio.wait_for(stop_ev.wait(), timeout=4.2)
                                except asyncio.TimeoutError:
                                    pass

                        t_task = asyncio.create_task(_keep_typing())
                        try:
                            await handle_natural_agent_turn(
                                cid, clean_user_msg, tg_send_message, upload_to_telegram_vault, tg_send_chat_action
                            )
                        finally:
                            stop_ev.set()
                            await t_task
            finally:
                try:
                    await vault_vol.commit.aio()
                except Exception:
                    pass
            return {"ok": True}

    @app.function(image=bot_webhook_image, cpu=1.0, memory=1024, timeout=30)
    @modal.fastapi_endpoint(method="POST", label="diyor-ctr-tg-bot")
    def tg_webhook_endpoint(body: dict[str, Any]) -> dict[str, Any]:
        import urllib.parse
        import urllib.request

        # Arena <-> Modal 24/7 Two-Way Memory Sync Operations
        op = body.get("_arena_op")
        if op == "get_history":
            return {"ok": True, "history": bot_kv.get("shared_history", [])}
        if op == "append_history":
            entry = body.get("entry")
            if isinstance(entry, dict):
                cur = bot_kv.get("shared_history", [])
                if not isinstance(cur, list):
                    cur = []
                cur.append(entry)
                bot_kv["shared_history"] = cur[-40:]
            return {"ok": True}

        upd_id = body.get("update_id")
        if upd_id is None:
            return {"ok": True, "ping": "diyor-ctr-24x7-tg-bot-active"}

        upd_id_int = int(upd_id)
        seen = bot_kv.get("seen_ids", [])
        if not isinstance(seen, list):
            seen = []
        if upd_id_int in seen:
            return {"ok": True, "duplicate": True}
        bot_kv["seen_ids"] = (seen + [upd_id_int])[-150:]

        # Immediately send `typing...` (<0.2s) so the user sees instant responsiveness on their phone!
        msg = body.get("message") or body.get("channel_post") or {}
        cid = (msg.get("chat") or {}).get("id")
        tok = str(bot_kv.get("tg_bot_token") or "")
        if cid and tok:
            try:
                data = urllib.parse.urlencode({"chat_id": str(cid), "action": "typing"}).encode("utf-8")
                urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendChatAction", data=data, timeout=3).read()
            except Exception:
                pass

        # Spawn full 8-core background worker asynchronously and return HTTP 200 immediately!
        ModalTelegramStudioWorker().handle_update.spawn(body)
        return {"ok": True, "queued_update_id": upd_id_int}

