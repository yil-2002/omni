#!/usr/bin/env python3
"""FX sound design for the VIRAL cut (19.6 s, 9:16). No narration, no melody-forward bed:
soft pad + impacts on cuts + micro-ticks on every type/dot event. 48 kHz stereo."""
import numpy as np, wave, os

SR = 48000
D = 19.6
N = int(SR * D)
rng = np.random.default_rng(11)
L = np.zeros(N); R = np.zeros(N); t = np.arange(N) / SR

def add2(sig, st, pan=0.0, gain=1.0):
    i0 = int(st * SR)
    if i0 < 0:
        sig = sig[-i0:]; i0 = 0
    i1 = min(N, i0 + len(sig))
    if i1 <= i0:
        return
    seg = sig[:i1 - i0] * gain
    gl = np.sqrt((1 - pan) / 2.0); gr = np.sqrt((1 + pan) / 2.0)
    L[i0:i1] += seg * gl
    R[i0:i1] += seg * gr

def lp(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y

def hp(x, a):
    return x - lp(x, a)

def whoosh(dur=0.5, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    band = hp(lp(rng.normal(0, 1, m), 0.55), 0.06)
    return band * (tt / dur) ** 2.4 * amt

def click(f=2100, dur=0.045, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    return (np.sin(2*np.pi*f*tt)*0.65 + np.sin(2*np.pi*f*1.5*tt)*0.35) * np.exp(-tt*80) * amt

def pop(f0=520, f1=1150, dur=0.13, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    f = f0 + (f1 - f0) * (tt / dur)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-tt*30) * np.minimum(1.0, tt/0.003) * amt

def thud(f=74, dur=0.28, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    fq = f*np.exp(-tt*15) + 42
    return np.sin(2*np.pi*np.cumsum(fq)/SR) * np.exp(-tt*12) * amt

def bell(f=1568, dur=1.0, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    env = np.exp(-tt*3.4) * np.minimum(1.0, tt/0.004)
    return (np.sin(2*np.pi*f*tt) + 0.42*np.sin(2*np.pi*f*2.01*tt) + 0.2*np.sin(2*np.pi*f*3.02*tt)) * env * amt

def riser(dur=0.9, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    nz = hp(lp(rng.normal(0, 1, m), 0.7), 0.12)
    f = 180 + 900 * (tt/dur) ** 2
    tone = np.sin(2*np.pi*np.cumsum(f)/SR) * 0.35
    return (nz + tone) * (tt/dur) ** 2.0 * amt

def subdrop(dur=0.6, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    f = 120 * np.exp(-tt*4.5) + 34
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-tt*4.0) * amt

def paper(dur=0.3, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    return hp(rng.normal(0, 1, m), 0.5) * np.exp(-tt*14) * amt

# ---------------- warm pad ----------------
prog = [(130.81, [261.63, 329.63, 392.00]),
        (110.00, [220.00, 261.63, 329.63]),
        (98.00,  [196.00, 246.94, 293.66]),
        (116.54, [233.08, 293.66, 349.23])]
seg = D / len(prog)
for ci, (base, notes) in enumerate(prog):
    st = ci*seg; dur = seg + 0.8
    i0 = int(st*SR); i1 = min(N, int((st + dur)*SR))
    if i1 <= i0:
        break
    tt = np.arange(i1-i0)/SR
    env = np.minimum(1.0, tt/0.6) * np.minimum(1.0, np.maximum(0, (dur-tt)/1.0)) * np.exp(-tt*0.18)
    for k, f in enumerate(notes):
        v = np.zeros(i1-i0)
        for h, w in ((1, 1.0), (2, 0.26), (3, 0.10)):
            v += w*np.sin(2*np.pi*f*h*tt + rng.uniform(0, 6.28))
        pan = -0.35 + 0.35*k
        gl = np.sqrt((1-pan)/2); gr = np.sqrt((1+pan)/2)
        v = v*env*0.048
        L[i0:i1] += v*gl; R[i0:i1] += v*gr
    v = 0.075*env*np.sin(2*np.pi*base*tt)
    L[i0:i1] += v; R[i0:i1] += v

# pulse enters at S3 and rides to the end (retention driver)
tp = 5.0
while tp < D - 0.4:
    i0 = int(tp*SR); i1 = min(N, i0 + int(0.30*SR))
    if i1 > i0:
        tt = np.arange(i1-i0)/SR
        env = np.exp(-tt*9) * np.minimum(1.0, tt/0.004)
        v = 0.055*env*np.sin(2*np.pi*146.83*tt)
        L[i0:i1] += v; R[i0:i1] += v
    tp += 0.30

# ---------------- hard cuts: paper + whoosh + thud ----------------
CUTS = [1.8, 5.0, 8.6, 11.6, 14.2, 16.6]
for st in CUTS:
    add2(paper(0.26, 0.55), st-0.26, pan=-0.12)
    add2(whoosh(0.42, 0.30), st-0.42, pan=0.18)
    add2(thud(78, 0.26, 0.46), st+0.01, pan=0.0)

# ---------------- S1 hook ----------------
for i in range(11):
    add2(click(1700 + i*60, 0.035, 0.13), 0.06 + i*0.012, pan=-0.5 + i/10.0*0.7)
for i in range(15):
    add2(click(1500 + i*48, 0.035, 0.11), 0.26 + i*0.012, pan=0.1)
add2(whoosh(0.30, 0.26), 0.42, pan=0.0)
add2(thud(92, 0.30, 0.50), 0.62, pan=0.0)
add2(pop(420, 980, 0.16, 0.20), 0.62, pan=0.0)
add2(click(1200, 0.04, 0.10), 0.92, pan=0.25)

# ---------------- S2 95 % ----------------
add2(click(1900, 0.04, 0.12), 1.84, pan=-0.2)
tp = 2.12
while tp < 3.37:
    add2(click(2500, 0.024, 0.07), tp, pan=0.42)
    tp += 0.022
add2(whoosh(1.25, 0.16), 2.12, pan=0.0)
add2(bell(1318, 0.9, 0.10), 3.37, pan=0.15)
add2(click(1400, 0.04, 0.09), 2.85, pan=0.3)

# ---------------- S3 dots + 8 % + chart ----------------
for i in range(26):
    add2(click(860 + (i % 7)*120, 0.028, 0.06), 5.35 + (i % 13)*0.016, pan=-0.5 + (i % 7)*0.16)
add2(whoosh(0.75, 0.32), 6.15, pan=0.0)
add2(subdrop(0.55, 0.24), 6.60, pan=0.0)
for i in range(6):
    add2(bell(1108 + i*74, 0.75, 0.085), 6.62 + i*0.03, pan=-0.4 + i*0.16)
add2(pop(300, 800, 0.18, 0.24), 6.70, pan=0.0)
add2(bell(1568, 0.95, 0.11), 6.76, pan=0.0)
add2(click(1600, 0.05, 0.10), 7.20, pan=-0.2)          # chart card in
for i, g in enumerate((0.30, 0.24, 0.20)):            # bars
    add2(click(1150 + i*180, 0.05, g), 7.34 + i*0.11, pan=-0.3 + i*0.3)
add2(bell(1760, 0.7, 0.06), 7.7, pan=0.35)

# ---------------- S4 three caveats ----------------
for i in range(3):
    add2(thud(112 + i*16, 0.20, 0.20), 8.95 + i*0.18, pan=0.0)
    add2(paper(0.16, 0.22), 8.95 + i*0.18, pan=-0.2 + i*0.2)
add2(click(1500, 0.05, 0.09), 10.35, pan=0.0)

# ---------------- S5 2029 ----------------
add2(riser(0.85, 0.20), 12.40, pan=0.0)
add2(bell(880, 1.1, 0.12), 12.45, pan=0.0)
add2(click(1300, 0.04, 0.08), 12.50, pan=-0.3)

# ---------------- S6 the twist (92 %) ----------------
add2(whoosh(0.35, 0.24), 14.05, pan=0.1)
add2(thud(64, 0.34, 0.48), 14.30, pan=0.0)
tp = 14.32
while tp < 14.94:
    add2(click(2300, 0.02, 0.055), tp, pan=-0.35)
    tp += 0.019
add2(bell(1046, 0.85, 0.10), 14.95, pan=0.15)

# ---------------- S7 payoff / loop ----------------
add2(thud(70, 0.40, 0.42), 16.66, pan=0.0)
for i in range(4):
    add2(bell(1046*(1 + i*0.25), 0.9, 0.075), 16.66 + i*0.06, pan=-0.4 + i*0.27)
add2(pop(500, 1150, 0.15, 0.15), 17.15, pan=-0.2)
add2(bell(1760, 0.8, 0.06), 17.15, pan=0.3)

# ---------------- master ----------------
L = lp(L, 0.45); R = lp(R, 0.45)
mid = (L + R)/2; side = lp((L - R)/2, 0.30)*1.15
L = mid + side; R = mid - side
fade = np.minimum(1.0, t/0.25) * np.minimum(1.0, (D - t)/0.55)
L *= fade; R *= fade
pk = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
L = np.tanh(L/pk*1.15)*0.79; R = np.tanh(R/pk*1.15)*0.79
pcm = (np.clip(np.stack([L, R], axis=1), -1, 1)*32767).astype("<i2")
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fx.wav")
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print(f"{out}  {os.path.getsize(out)/1e6:.2f} MB  {N/SR:.1f}s  peak {np.abs(L).max():.2f}")
