#!/usr/bin/env python3
"""CUT-LOCKED FX bed.

Measured problem: the old bed's transients sat 0.17-0.72 s off the picture cuts
and nothing marked the whip-pans. Here every cut gets a sub-boom + a noise
whoosh that lands exactly on the frame, every scene event gets its own tick at
its real animation time, and the master is normalised to -14 LUFS with a
-1 dBTP ceiling (Reels / Shorts / TikTok loudness target).
"""
import numpy as np, wave, sys, os

SR = 48000
rng = np.random.default_rng(20261029)

# ------------------------------------------------------------------ recipes
def _t(dur):
    return np.arange(int(dur * SR)) / SR

def whoosh(dur=0.42, amt=1.0, up=True):
    """band-passed noise sweep; lands ON the cut, tail decays after it."""
    m = int(dur * SR); tt = _t(dur)
    nz = rng.normal(0, 1, m)
    # two cascaded one-poles = soft band-pass, cheap and smooth
    a = 0.09 + 0.5 * (tt / dur if up else 1 - tt / dur)
    y = np.empty(m); acc = 0.0; acc2 = 0.0
    for i in range(m):
        acc += a[i] * (nz[i] - acc)
        acc2 += 0.25 * (acc - acc2)
        y[i] = acc - acc2
    env = np.minimum(1.0, tt / (dur * 0.55)) ** 2.2 * np.exp(-np.maximum(0, tt - dur * 0.7) * 9)
    return y * env * amt

def sub(dur=0.5, f0=68, amt=1.0):
    tt = _t(dur)
    f = f0 * np.exp(-tt * 9) + 34
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7.5) * np.minimum(1, tt / 0.004) * amt

def click(f=2100, dur=0.04, amt=1.0):
    tt = _t(dur)
    return (np.sin(2*np.pi*f*tt) * 0.6 + np.sin(2*np.pi*f*1.51*tt) * 0.4) * np.exp(-tt*90) * amt

def pop(f0=420, f1=1100, dur=0.14, amt=1.0):
    tt = _t(dur)
    f = f0 + (f1 - f0) * (tt / dur)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-tt*26) * np.minimum(1, tt/0.003) * amt

def bell(f=1568, dur=0.9, amt=1.0):
    tt = _t(dur)
    env = np.exp(-tt*3.6) * np.minimum(1, tt/0.004)
    return (np.sin(2*np.pi*f*tt) + 0.4*np.sin(2*np.pi*f*2.01*tt) + 0.18*np.sin(2*np.pi*f*3.02*tt)) * env * amt

def type_tick(f=2400, dur=0.03, amt=1.0):
    """dry, quiet keystroke - marks every text line without becoming music."""
    tt = _t(dur)
    nz = rng.normal(0, 1, len(tt)) * np.exp(-tt*260)
    return (nz * 0.6 + np.sin(2*np.pi*f*tt) * np.exp(-tt*300) * 0.5) * amt

# ------------------------------------------------------------------ build
class Bed:
    def __init__(self, dur):
        self.n = int(SR * dur); self.dur = dur
        self.L = np.zeros(self.n); self.R = np.zeros(self.n)

    def add(self, sig, at, pan=0.0, gain=1.0):
        i0 = int(round(at * SR))
        if i0 < 0:
            sig = sig[-i0:]; i0 = 0
        i1 = min(self.n, i0 + len(sig))
        if i1 <= i0: return
        seg = sig[:i1-i0] * gain
        gl = np.sqrt((1-pan)/2); gr = np.sqrt((1+pan)/2)
        self.L[i0:i1] += seg * gl
        self.R[i0:i1] += seg * gr

    def _write(self, path, L, R, gain=1.0):
        L = L * gain; R = R * gain
        fade = np.minimum(1.0, np.arange(self.n)/SR/0.18) * np.minimum(1.0, (self.dur - np.arange(self.n)/SR)/0.45)
        L *= fade; R *= fade
        pcm = (np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype("<i2")
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

    @staticmethod
    def _ffmpeg_bin():
        import shutil, glob
        f = shutil.which("ffmpeg")
        if f:
            return f
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        bins = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux")))
        return bins[-1] if bins else "ffmpeg"

    @staticmethod
    def _measure(path):
        import subprocess, re
        ff = Bed._ffmpeg_bin()
        out = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path),
                              "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        i = re.findall(r"I:\s*(-?[\d.]+) LUFS", out)
        tp = re.findall(r"Peak:\s*(-?[\d.]+) dBFS", out)
        return float(i[-1]) if i else None, float(tp[-1]) if tp else None

    def save(self, path, lufs_target=-14.0, tp_ceiling=-1.0):
        """gain first, then limit, then verify: intersample peaks rise ~1.2 dB over
        the sample peaks, so the limiter works to a -2.2 dBFS sample ceiling."""
        L0, R0 = self.L, self.R
        mid = (L0 + R0) / 2
        side = (L0 - R0) / 2
        L0, R0 = mid + side * 1.08, mid - side * 1.08
        self._write(path, L0, R0, 1.0)
        I, _ = self._measure(path)
        gain = 10 ** ((lufs_target - (I if I else -20.0)) / 20.0)
        ceil = 10 ** ((tp_ceiling - 1.2) / 20.0)     # sample ceiling with intersample headroom
        knee = 0.5 * ceil
        best = None
        for _ in range(3):
            def limit(x):
                a = np.abs(x); over = a > knee
                y = x.copy()
                y[over] = np.sign(x[over]) * (knee + (ceil - knee) *
                          np.tanh((a[over] - knee) / (ceil - knee)))
                return y
            Lg = limit(L0 * gain); Rg = limit(R0 * gain)
            self._write(path, Lg, Rg, 1.0)
            I, TP = self._measure(path)
            score = abs(I - lufs_target) if (TP is None or TP <= tp_ceiling) else 99
            if best is None or score < best[0]:
                best = (score, gain, Lg, Rg, I, TP)
            if score < 0.3:
                break
            if TP is not None and TP > tp_ceiling:
                gain *= 10 ** ((tp_ceiling - TP) / 20.0)
            elif I is not None:
                gain *= 10 ** ((lufs_target - I) / 20.0 * 0.9)
        _, gain, Lg, Rg, I, TP = best
        self._write(path, Lg, Rg, 1.0)
        I, TP = self._measure(path)
        print(f"  {os.path.basename(path)}  {os.path.getsize(path)/1e6:.2f} MB  {self.dur:.1f}s  "
              f"I {I:.1f} LUFS  true-peak {TP:.1f} dBFS")






# ================================================================== OCTOVERSE · 20.0
def octoverse():
    CUT = [2.0, 5.8, 9.8, 13.0, 16.2, 18.3]
    b = Bed(20.0)
    for i, c in enumerate(CUT):
        b.add(whoosh(0.46, 0.28), c - 0.30, pan=0.0)
        b.add(sub(0.55, 62 if i % 2 else 70, 0.58), c, pan=0.0)
        b.add(click(1500 if i % 2 else 1900, 0.04, 0.10), c, pan=-0.25 + 0.1 * (i % 3))
    for i, t in enumerate((0.02, 0.34, 0.66)):
        b.add(type_tick(2300 + i * 180, 0.03, 0.13), t, pan=-0.3 + 0.3 * i)
    t = 2.55
    while t < 3.30:
        b.add(click(2400, 0.022, 0.035), t, pan=-0.2); t += 0.06
    b.add(bell(1046, 0.7, 0.075), 3.35, pan=-0.1)
    t = 3.55
    while t < 4.80:
        b.add(click(2900, 0.022, 0.045), t, pan=0.25); t += 0.055
    b.add(bell(1568, 1.0, 0.11), 4.86, pan=0.1)
    b.add(type_tick(2000, 0.03, 0.10), 4.62, pan=-0.2)
    for i, t in enumerate((6.30, 6.56, 6.82)):
        b.add(whoosh(0.34, 0.16), t, pan=-0.35 + i * 0.35)
        b.add(click(1800 + i * 260, 0.04, 0.09), t, pan=-0.35 + i * 0.35)
    b.add(bell(1174, 0.8, 0.07), 7.94, pan=0.1)
    b.add(type_tick(2100, 0.03, 0.09), 8.02, pan=0.2)
    t = 10.0
    while t < 10.88:
        b.add(click(2600, 0.02, 0.04), t, pan=0.3); t += 0.05
    b.add(bell(1318, 1.0, 0.10), 10.92, pan=0.1)
    b.add(pop(430, 980, 0.15, 0.13), 10.55, pan=-0.2)
    b.add(type_tick(1900, 0.03, 0.08), 11.62, pan=-0.3)
    for i in range(19):
        b.add(type_tick(2100 + (i % 5) * 140, 0.026, 0.075), 14.15 + i * 0.058, pan=-0.45 + i * 0.05)
    b.add(sub(0.42, 84, 0.20), 15.12, pan=0.0)
    for i in range(4):
        b.add(click(1900 + i * 180, 0.035, 0.085), 15.74 + i * 0.075, pan=-0.3 + i * 0.2)
    b.add(bell(1568, 0.9, 0.09), 16.06, pan=0.15)
    for i in range(2):
        b.add(pop(420 + i * 120, 900 + i * 200, 0.15, 0.12), 16.55 + i * 0.22, pan=-0.3 + i * 0.6)
        b.add(click(620 - i * 60, 0.05, 0.12), 16.62 + i * 0.22, pan=0.3 - i * 0.3)
    b.add(sub(0.38, 58, 0.16), 17.32, pan=0.0)
    for i in range(4):
        b.add(bell(1046 * (1 + i * 0.25), 0.85, 0.05), 18.34 + i * 0.05, pan=-0.4 + i * 0.27)
    b.add(sub(0.5, 64, 0.20), 18.34, pan=0.0)
    b.save(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manba/octoverse/assets/fx.wav"))

# ================================================================== MISTRAL · 20.0
def mistral():
    CUT = [2.0, 6.0, 10.0, 13.2, 16.4, 18.4]
    b = Bed(20.0)
    for i, c in enumerate(CUT):
        b.add(whoosh(0.46, 0.28), c - 0.30, pan=0.0)
        b.add(sub(0.55, 62 if i % 2 else 70, 0.58), c, pan=0.0)
        b.add(click(1500 if i % 2 else 1900, 0.04, 0.10), c, pan=-0.25 + 0.1 * (i % 3))
    # S1 hook: three word landings
    for i, t in enumerate((0.02, 0.34, 0.66)):
        b.add(type_tick(2300 + i * 180, 0.03, 0.13), t, pan=-0.3 + 0.3 * i)
    # S2 28.3 then 41: two counting runs, two landings (the second one bigger)
    t = 2.60
    while t < 3.40:
        b.add(click(2400, 0.02, 0.035), t, pan=-0.25); t += 0.06
    b.add(bell(1046, 0.7, 0.07), 3.46, pan=-0.15)
    t = 3.55
    while t < 4.90:
        b.add(click(3000, 0.02, 0.045), t, pan=0.25); t += 0.055
    b.add(bell(1568, 1.05, 0.12), 4.97, pan=0.1)
    b.add(type_tick(2000, 0.03, 0.10), 4.85, pan=-0.2)
    # S3 four bars: four ticks, the ML4 one gets the bell
    for i in range(4):
        b.add(click(1700 + i * 240, 0.04, 0.075), 6.50 + i * 0.20, pan=-0.4 + i * 0.27)
        b.add(whoosh(0.28, 0.13), 6.50 + i * 0.20, pan=-0.4 + i * 0.27)
    b.add(bell(1318, 0.85, 0.08), 7.60, pan=0.1)
    b.add(type_tick(2100, 0.03, 0.09), 8.30, pan=0.2)
    # S4 47 %
    t = 10.20
    while t < 11.15:
        b.add(click(2600, 0.02, 0.045), t, pan=0.3); t += 0.05
    b.add(bell(1568, 1.0, 0.11), 11.22, pan=0.1)
    b.add(pop(430, 980, 0.15, 0.13), 10.80, pan=-0.2)
    b.add(type_tick(1900, 0.03, 0.08), 11.92, pan=-0.3)
    # S5 two paths
    for i in range(2):
        b.add(pop(420 + i * 120, 900 + i * 200, 0.15, 0.12), 13.60 + i * 0.26, pan=-0.35 + i * 0.7)
        b.add(click(620 - i * 60, 0.05, 0.11), 13.68 + i * 0.26, pan=0.35 - i * 0.7)
    b.add(sub(0.36, 58, 0.16), 14.92, pan=0.0)
    # S6 the fine print: two dry hits
    for i in range(2):
        b.add(click(340, 0.055, 0.13), 16.78 + i * 0.22, pan=-0.25 + i * 0.5)
    b.add(sub(0.34, 52, 0.15), 17.52, pan=0.0)
    # S7 close
    for i in range(4):
        b.add(bell(1046 * (1 + i * 0.25), 0.85, 0.05), 18.44 + i * 0.05, pan=-0.4 + i * 0.27)
    b.add(sub(0.5, 64, 0.20), 18.44, pan=0.0)
    b.save(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manba/mistral/assets/fx.wav"))


def build_fx_for_cuts(duration: float, cuts: list[float], out_wav: str, extra_events: list[dict] | None = None, lufs_target: float = -14.5):
    """Reusable cut-locked FX bed generator for any new @diyor.ctr motion clip (4:5 or 9:16)."""
    b = Bed(float(duration))
    # Hook entrance ticks
    for idx, t in enumerate((0.02, 0.30, 0.58)):
        if t < duration - 0.1:
            b.add(type_tick(2300 + idx * 180, 0.03, 0.13), t, pan=-0.3 + 0.3 * idx)

    # Every cut gets pre-whoosh + exact frame sub-boom + crisp stereo click
    for idx, c in enumerate(cuts):
        if c <= 0.05 or c >= duration - 0.05:
            continue
        b.add(whoosh(0.44, 0.28), max(0.0, c - 0.28), pan=0.0)
        b.add(sub(0.52, 62 if idx % 2 else 70, 0.58), c, pan=0.0)
        b.add(click(1550 if idx % 2 else 1950, 0.04, 0.10), c, pan=-0.25 + 0.12 * (idx % 3))

    for ev in (extra_events or []):
        kind = ev.get("kind", "tick")
        at = float(ev.get("at", 0.5))
        if at >= duration - 0.05:
            continue
        if kind == "count":
            span = float(ev.get("dur", 0.9))
            tt = at
            while tt < min(duration - 0.1, at + span):
                b.add(click(2600, 0.02, 0.04), tt, pan=0.2)
                tt += 0.055
            b.add(bell(1568, 0.95, 0.11), min(duration - 0.15, at + span + 0.04), pan=0.1)
        elif kind == "bars":
            rows = int(ev.get("rows", 3))
            for r in range(rows):
                t_r = at + r * 0.20
                if t_r < duration - 0.1:
                    b.add(whoosh(0.28, 0.14), t_r, pan=-0.35 + 0.25 * (r % 3))
                    b.add(click(1750 + r * 220, 0.04, 0.08), t_r, pan=-0.35 + 0.25 * (r % 3))
        elif kind == "pop":
            b.add(pop(430, 980, 0.15, 0.13), at, pan=-0.15)
        elif kind == "outro":
            for r in range(4):
                if at + r * 0.05 < duration - 0.1:
                    b.add(bell(1046 * (1 + r * 0.25), 0.80, 0.05), at + r * 0.05, pan=-0.36 + r * 0.24)
            b.add(sub(0.48, 64, 0.20), at, pan=0.0)
        else:
            b.add(type_tick(2150, 0.03, 0.09), at, pan=0.1)

    os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
    b.save(out_wav, lufs_target=lufs_target, tp_ceiling=-1.2)
    return out_wav


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("octoverse", "all"): print("OCTOVERSE"); octoverse()
    if which in ("mistral", "all"): print("MISTRAL"); mistral()
