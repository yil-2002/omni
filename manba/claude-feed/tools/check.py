#!/usr/bin/env python3
"""Layout gate: assert every critical element stays inside the 9:16 safe box
and that key scenes are not empty. Catches the class of bug a render can't.

Universal 2026 safe box: 900x1400 centred in 1080x1920  ->  y: 260..1660, x: 90..990
Strict band for critical text (TikTok bottom caption):  y < 1440
Usage: python3 tools/check.py
"""
import json, os, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = "file://" + os.path.join(ROOT, "index.html")

SAFE = {"x0": 84, "x1": 996, "y0": 250, "y1": 1670}   # hard box (HUD may touch)
CRIT = {"x0": 90, "x1": 990, "y0": 260, "y1": 1445}   # critical text band

SCENES = [
    ("s1", 2.0), ("s2", 4.8), ("s3", 9.0), ("s3", 10.7),
    ("s4", 13.4), ("s5", 17.0), ("s6", 21.2), ("s7", 25.2),
]
SEL = {
    "s1": ["#s1 h1", "#s1 .hero-sans", "#s1 .lede", "#s1 .meta"],
    "s2": ["#s2 h2", "#s2 .arcwrap", "#s2 .cap"],
    "s3": ["#s3 h2", "#s3 .funnelstage", "#s3 .bigpct", "#s3 .pills"],
    "s4": ["#s4 h2", "#s4 .codestack"],
    "s5": ["#s5 h2", "#s5 .rows", "#s5 .note"],
    "s6": ["#s6 h2", "#s6 .bigyear", "#s6 .body", "#s6 .timeline"],
    "s7": ["#s7 .msgcard", "#s7 h2", "#s7 .sub", "#s7 .src"],
}
HUD = [".hud .topline", ".hud .botline", ".hud .progress"]


def main():
    fails, warns = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(PAGE)
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(2200)
        dur = pg.evaluate("() => window.__timelines.main.duration()")
        print(f"timeline duration: {dur}s (root data-duration: 27)")
        if abs(dur - 27) > 0.01:
            warns.append(f"timeline {dur}s != 27s — render will be {dur}s")

        # HUD must stay in the hard safe box
        pg.evaluate("() => { window.__timelines.main.seek(2.0); }")
        for sel in HUD:
            box = pg.evaluate("""sel => { const el = document.querySelector(sel); const r = el.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height}; }""", sel)
            if box["y"] < SAFE["y0"] or box["y"] + box["h"] > SAFE["y1"]:
                fails.append(f"HUD {sel}: y {box['y']:.0f}..{box['y']+box['h']:.0f} outside {SAFE['y0']}..{SAFE['y1']}")

        for scene, t in SCENES:
            print(f"  .. scene {scene} @ {t}s", flush=True)
            pg.evaluate("t => { const tl = window.__timelines.main; tl.pause(); tl.seek(t); }", t)
            pg.wait_for_timeout(140)
            for sel in SEL[scene]:
                box = pg.evaluate("""sel => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    const op = parseFloat(getComputedStyle(el).opacity);
                    return {x: r.x, y: r.y, w: r.width, h: r.height, op: op,
                            text: (el.innerText || '').trim().slice(0, 28)};
                }""", sel)
                if box is None:
                    fails.append(f"{t}s {sel}: MISSING")
                    continue
                if box["op"] < 0.05 or box["w"] < 2 or box["h"] < 2:
                    warns.append(f"{t}s {sel}: invisible at this time (op={box['op']:.2f})")
                    continue
                x0, x1 = box["x"], box["x"] + box["w"]
                y0, y1 = box["y"], box["y"] + box["h"]
                if x0 < SAFE["x0"] - 1 or x1 > SAFE["x1"] + 1:
                    fails.append(f"{t}s {sel}: x {x0:.0f}..{x1:.0f} outside {SAFE['x0']}..{SAFE['x1']}")
                if y1 > CRIT["y1"]:
                    fails.append(f"{t}s {sel}: bottom {y1:.0f} > {CRIT['y1']} (TikTok caption band)")
                if y0 < CRIT["y0"] - 30:
                    warns.append(f"{t}s {sel}: top {y0:.0f} higher than {CRIT['y0']}")
        pg.close()
        b.close()

    print("\n--- FAILURES ---" if fails else "\n--- no failures ---")
    for f in fails:
        print(" FAIL", f)
    print(f"--- warnings ({len(warns)}) ---")
    for w in warns:
        print(" warn", w)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
