#!/usr/bin/env python3
"""Fast QA: seek the HyperFrames timeline in a real browser and build a contact sheet.

Usage:  python3 tools/frames.py "6.0,12.5,23.0" out.png [--scale 0.40] [--full]
Needs: playwright chromium installed (python3 -m playwright install chromium)
Why: a full 60fps delivery render takes ~4 min; this takes ~7 s and catches layout bugs.
"""
import sys, json, os
import cv2
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = "file://" + os.path.join(ROOT, "index.html")

def main():
    times = [float(x) for x in sys.argv[1].split(",")]
    out = sys.argv[2] if len(sys.argv) > 2 else "/home/user/qa.png"
    scale = 0.40
    if "--scale" in sys.argv:
        scale = float(sys.argv[sys.argv.index("--scale") + 1])
    full = "--full" in sys.argv          # single big frames instead of a sheet
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files",
                                    "--font-render-hinting=none"])
        W, H = (1920, 1080) if "--wide" in sys.argv else (1080, 1920)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(PAGE)
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(2200)
        info = pg.evaluate("""() => ({
            tl: !!window.__timelines,
            dur: window.__timelines ? window.__timelines.main.duration() : null,
            fonts: [...document.fonts].map(f => f.family + ' ' + f.weight + ' ' + f.status),
            fraunces: document.fonts.check('60px Fraunces'),
            serifBold: document.fonts.check('700 60px Inter')
        })""")
        print(json.dumps(info, indent=1))
        shots = []
        for t in times:
            pg.evaluate("t => { const tl = window.__timelines.main; tl.pause(); tl.seek(t); }", t)
            pg.wait_for_timeout(180)
            pth = f"/tmp/qa_{t:.2f}.png"
            pg.screenshot(path=pth)
            img = cv2.imread(pth)
            if full:
                shots.append(img)
            else:
                h, w = int(H * scale), int(W * scale)
                small = cv2.resize(img, (w, h))
                cv2.putText(small, f"{t:g}s", (8, 22), 0, 0.62, (40, 40, 220), 2)
                shots.append(small)
        b.close()
    if full:
        for t, img in zip(times, shots):
            cv2.imwrite(f"{out.rsplit('.',1)[0]}_{t:g}.png", img)
        print("wrote", len(shots), "frames")
        return
    cols = min(6, len(shots))
    rows = (len(shots) + cols - 1) // cols
    blank = np.full_like(shots[0], 255)
    while len(shots) < rows * cols:
        shots.append(blank)
    sheet = np.vstack([np.hstack(shots[r * cols:(r + 1) * cols]) for r in range(rows)])
    cv2.imwrite(out, sheet)
    print("sheet:", out, sheet.shape)

if __name__ == "__main__":
    main()
