#!/usr/bin/env python3
"""
🚀 @diyor.ctr — Dedicated Modal.com T4 GPU Worker for `aisha-org/navoiy-tts`
===========================================================================
Narxi: $0 / oy (Modal Starter rejasidagi har oylik $30 BEPUL kredit ichida ~50 soat T4 GPU =
oyiga ~10,000+ ta Reels ovozi mutlaqo tekin!)

Afzalliklari:
1. Umumiy navbat yo‘q — shaxsiy NVIDIA T4 (`16 GB VRAM`, `fp16`) konteyneringizda ishlaydi.
2. Barcha 10 ta o‘zbekcha emotsiya (`mehribon`, `xotirjam`, `xursand`, `hayratda` va h.k.).
3. KELAJAK UCHUN BONUS: `reference_wav_base64` yuborilsa, `Navoiy TTS` (`CosyVoice2-0.5B`)
   sizning o‘z 15 soniyalik ovozingizni o‘zbek tilida $0 ga klonlab gapiradi!

Deploy qilish (bir marta):
  pip install modal
  modal token set --token-id <ID> --token-secret <SECRET>
  modal deploy /home/user/claude-techbrief/engine/modal_navoiy_tts_worker.py
"""
from __future__ import annotations

import base64
import io
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import modal
except ImportError:
    modal = None

COSYVOICE_COMMIT = "074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc"
NAVOIY_REPO = "aisha-org/navoiy-tts"
NAVOIY_REVISION = "912e6bb6663f11e5dec5de830ca06ea8dd4c985f"
BASE_REPO = "FunAudioLLM/CosyVoice2-0.5B"
BASE_REVISION = "eec1ae6c79877dbd9379285cf8789c9e0879293d"

if modal is not None:
    app = modal.App("diyor-ctr-navoiy-tts")

    navoiy_image = (
        modal.Image.debian_slim(python_version="3.10")
        .apt_install("git", "ffmpeg", "libsndfile1", "libsox-dev", "sox")
        .pip_install(
            "torch==2.4.1",
            "torchaudio==2.4.1",
            "huggingface_hub==0.36.2",
            "numpy==1.26.4",
            "conformer==0.3.2",
            "diffusers==0.29.0",
            "HyperPyYAML==1.2.3",
            "inflect==7.3.1",
            "librosa==0.10.2",
            "omegaconf==2.3.0",
            "onnxruntime==1.20.1",
            "openai-whisper==20250625",
            "protobuf==4.25.5",
            "einops==0.8.0",
            "regex==2024.11.6",
            "scipy==1.13.1",
            "soundfile==0.12.1",
            "transformers==4.51.3",
            "x-transformers==2.11.24",
            "wetext==0.0.4",
            "fastapi[standard]",
        )
        .run_commands(
            f"git clone https://github.com/FunAudioLLM/CosyVoice.git /opt/CosyVoice && "
            f"cd /opt/CosyVoice && git checkout {COSYVOICE_COMMIT} && git submodule update --init --recursive",
            f"python3 -c \"from huggingface_hub import snapshot_download; "
            f"snapshot_download('{NAVOIY_REPO}', revision='{NAVOIY_REVISION}', local_dir='/opt/navoiy-tts'); "
            f"snapshot_download('{BASE_REPO}', revision='{BASE_REVISION}', local_dir='/opt/CosyVoice2-0.5B')\"",
        )
    )

    @app.cls(image=navoiy_image, gpu="T4", memory=8192, scaledown_window=180, timeout=300)
    class NavoiyGPUService:
        @modal.enter()
        def load_model(self) -> None:
            import torch

            sys.path.insert(0, "/opt/navoiy-tts")
            sys.path.insert(0, "/opt/CosyVoice")
            sys.path.insert(0, "/opt/CosyVoice/third_party/Matcha-TTS")
            from cosyvoice.cli.cosyvoice import CosyVoice2
            from uztts.normalize import normalize

            self.normalize = normalize
            entries = json.loads(Path("/opt/navoiy-tts/emotions_40h.json").read_text(encoding="utf-8"))
            self.emotions = {e["uz"].lower(): e for e in entries}
            self.default_ref = "/opt/CosyVoice/asset/zero_shot_prompt.wav"

            self.model = CosyVoice2("/opt/CosyVoice2-0.5B", load_jit=False, load_trt=False, fp16=True)
            state = torch.load("/opt/navoiy-tts/emotion_600h_joint.pt", map_location="cpu", weights_only=True)
            while isinstance(state, dict) and any(k in state for k in ("state_dict", "model", "llm")):
                for k in ("state_dict", "model", "llm"):
                    if isinstance(state.get(k), dict):
                        state = state[k]
                        break
            self.model.model.llm.load_state_dict(state, strict=False)
            self.model.model.llm.eval()

        @modal.fastapi_endpoint(method="POST")
        def synthesize(self, body: dict[str, Any]) -> dict[str, Any]:
            import soundfile as sf
            import torch

            text = str(body.get("text", "")).strip()
            emotion_key = str(body.get("emotion", "mehribon")).lower()
            speed = float(body.get("speed", 1.0))
            ref_b64 = body.get("reference_wav_base64", "")

            em = self.emotions.get(emotion_key) or self.emotions["xotirjam"]
            norm_txt = self.normalize(text, mode="infer")
            instruct = em["instruct"].strip() + "<|endofprompt|>"

            ref_path = self.default_ref
            tmp_ref = None
            if ref_b64:
                tmp_ref = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_ref.write(base64.b64decode(ref_b64))
                tmp_ref.close()
                ref_path = tmp_ref.name

            try:
                random.seed(1986)
                torch.manual_seed(1986)
                torch.cuda.manual_seed_all(1986)
                chunks = []
                with torch.inference_mode():
                    for r in self.model.inference_instruct2(norm_txt, instruct, ref_path, stream=False, speed=speed):
                        chunks.append(r["tts_speech"].detach().cpu())
                audio = torch.cat(chunks, dim=1).squeeze().float().numpy()
                buf = io.BytesIO()
                sf.write(buf, audio, 24000, format="WAV")
                return {
                    "ok": True,
                    "sample_rate": 24000,
                    "duration": round(len(audio) / 24000.0, 2),
                    "wav_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
                }
            finally:
                if tmp_ref is not None:
                    Path(tmp_ref.name).unlink(missing_ok=True)
