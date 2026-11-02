#!/usr/bin/env python3
"""render_overlay.py — renders the Clawd overlay windows to alpha PNGs, resumably, in one headless Chrome.

usage: python3 render_overlay.py WINDOWS [--fps=60] [--out=out/frames] [--page=overlay.html]
       WINDOWS = "a:b,c:d" in FILM seconds (the shot windows the overlay page defines)
Each PNG is RGBA with a transparent background (PROJECT.clear), named f00000.png ... in film-frame order per window:
<out>/<window index>/f%05d.png  where the file index counts frames from the window's start.
"""
import argparse, asyncio, base64, os, sys
from playwright.async_api import async_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARGS = ["--no-sandbox", "--allow-file-access-from-files", "--ignore-gpu-blocklist",
        "--use-angle=gl-egl", "--enable-gpu-rasterization", "--window-size=1200,1000",
        "--disable-renderer-backgrounding", "--disable-background-timer-throttling"]

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("windows")
    ap.add_argument("--fps", type=float, default=60)
    ap.add_argument("--out", default="out/frames")
    ap.add_argument("--page", default="overlay.html")
    ap.add_argument("--root", default=SCRIPT_DIR)
    a = ap.parse_args()
    wins = [tuple(float(x) for x in w.split(":")) for w in a.windows.split(",")]
    async with async_playwright() as p:
        b = await p.chromium.launch(args=ARGS)
        pg = await b.new_page(viewport={"width": 1200, "height": 1000})
        pg.on("pageerror", lambda e: print("ERR", str(e)[:300], flush=True))
        await pg.goto(f"file://{a.root}/{a.page}?render")
        await pg.wait_for_timeout(3500)
        if not await pg.evaluate("window.ready === true"):
            print("page never became ready"); return 1
        for wi, (t0, t1) in enumerate(wins):
            d = os.path.join(a.out, str(wi))
            os.makedirs(d, exist_ok=True)
            n = int(round((t1 - t0) * a.fps))
            t_start = __import__("time").time()
            done = 0
            for i in range(n):
                f = os.path.join(d, f"f{i:05d}.png")
                if os.path.exists(f) and os.path.getsize(f) > 500:
                    done += 1; continue
                t = t0 + i / a.fps
                url = await pg.evaluate("t => window.renderAt(t, 'image/png')", t)
                open(f + ".tmp", "wb").write(base64.b64decode(url.split(",", 1)[1]))
                os.replace(f + ".tmp", f)
                done += 1
                if done % 20 == 0 or i == n - 1:
                    el = __import__("time").time() - t_start
                    print(f"window {wi} [{t0}-{t1}]  frame {i+1}/{n}  {(el/max(1,i+1)):.2f} s/frame", flush=True)
        await b.close()
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
