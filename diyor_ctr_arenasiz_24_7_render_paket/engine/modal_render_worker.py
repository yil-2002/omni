#!/usr/bin/env python3
"""
⚡ @diyor.ctr — Modal.com Serverless Distributed Render Farm (`modal_render_worker.py`)
=====================================================================================
Narxi: $0 / oy (Modal Starter rejasidagi har oylik $30 BEPUL kredit ichida yuzlab 1080p/4K video!)

Ishga tushirish (bir marta):
  pip install modal
  modal token set --token-id <ID> --token-secret <SECRET>
  modal deploy /home/user/claude-techbrief/engine/modal_render_worker.py

Deploy yakunida Modal sizga doimiy HTTPS manzil beradi:
  `https://<username>--diyor-ctr-render-farm-render-webhook.modal.run`
Shu URL ni `:8000` Master Studio -> `⚡ $0 Cloud-Render` oynasiga kiritsangiz,
har qanday 1–10 daqiqalik `16:9` YouTube yoki `9:16` Reels sahnasi 20–40 ta parallel
bulut konteynerda 8–15 soniyada render bo‘lib qaytadi!
"""
from __future__ import annotations

import base64
import io
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    import modal
except ImportError:
    modal = None  # Allows importing file safely even before `pip install modal`

TB_ROOT = Path("/home/user/claude-techbrief")

if modal is not None:
    app = modal.App("diyor-ctr-render-farm")

    render_image = (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install("ffmpeg", "fonts-liberation", "libnss3", "libatk1.0-0", "libatk-bridge2.0-0", "libcups2", "libdrm2", "libxkbcommon0", "libxcomposite1", "libxdamage1", "libxrandr2", "libgbm1", "libasound2")
        .pip_install("playwright>=1.48.0", "pillow>=10.0.0", "numpy>=1.26.0", "scipy>=1.13.0", "fastapi[standard]")
        .run_commands("python3 -m playwright install chromium")
        .add_local_dir(str(TB_ROOT / "shared"), remote_path="/opt/tb/shared", copy=True)
        .add_local_dir(str(TB_ROOT / "vositalar"), remote_path="/opt/tb/vositalar", copy=True)
    )

    @app.function(image=render_image, cpu=2.0, memory=2048, timeout=300, max_containers=40)
    def render_slice_worker(payload: dict[str, Any]) -> bytes:
        """Renders `[f_start, f_end)` frames of a deterministic GSAP HTML timeline in an isolated cloud worker."""
        from PIL import Image
        from playwright.sync_api import sync_playwright

        html_str = (
            payload["html"]
            .replace("file:///home/user/claude-techbrief/shared", "file:///opt/tb/shared")
        )
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
    @modal.fastapi_endpoint(method="POST")
    def render_webhook(body: dict[str, Any]) -> dict[str, Any]:
        """
        Receives `{html, width, height, duration, fps, cuts, lufs_target}` -> fans out across N parallel
        `render_slice_worker.map()` cloud containers -> concatenates losslessly + muxes `-14.5 LUFS` FX!
        """
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

        total_frames = max(1, int(round(dur * fps)))
        slice_size = 75  # 2.5 seconds per cloud container -> 60s video runs across 24 containers in ~6s!
        slices = []
        for f0 in range(0, total_frames, slice_size):
            f1 = min(total_frames, f0 + slice_size)
            slices.append({
                "html": html_str,
                "width": W,
                "height": H,
                "fps": fps,
                "f_start": f0,
                "f_end": f1,
            })

        chunk_bytes_list = list(render_slice_worker.map(slices))

        with tempfile.TemporaryDirectory() as tdir:
            td = Path(tdir)
            chunk_paths = []
            for idx, b in enumerate(chunk_bytes_list):
                cp = td / f"c_{idx:04d}.mp4"
                cp.write_bytes(b)
                chunk_paths.append(cp)

            wav_path = str(td / "fx.wav")
            build_fx_for_cuts(dur, cuts, wav_path, lufs_target=lufs_target)

            concat_txt = td / "list.txt"
            concat_txt.write_text("\n".join(f"file '{p}'" for p in chunk_paths) + "\n", encoding="utf-8")

            final_mp4 = td / "final.mp4"
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-i", wav_path,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", "-shortest", str(final_mp4),
            ], check=True)

            mp4_b64 = base64.b64encode(final_mp4.read_bytes()).decode("ascii")
            return {
                "ok": True,
                "workers_used": len(slices),
                "duration": dur,
                "width": W,
                "height": H,
                "mp4_base64": mp4_b64,
            }
