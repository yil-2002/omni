#!/usr/bin/env python3
"""Sound design for claude-brief (FX only, no narration).
Writes assets/fx.wav — 48 kHz stereo, 27.0 s.
Every cue is placed on a real timeline event so picture and sound agree.
"""
import numpy as np, wave, os

SR = 48000
D = 27.0
N = int(SR * D)
rng = np.random.default_rng(7)
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

# ---------------- instruments ----------------
def whoosh(dur=0.55, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    nz = rng.normal(0, 1, m)
    band = hp(lp(nz, 0.55), 0.06)
    return band * (tt / dur) ** 2.2 * amt

def click(f=2100, dur=0.05, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    return (np.sin(2*np.pi*f*tt)*0.65 + np.sin(2*np.pi*f*1.5*tt)*0.35) * np.exp(-tt*70) * amt

def pop(f0=520, f1=1100, dur=0.14, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    f = f0 + (f1 - f0) * (tt / dur)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-tt*26) * np.minimum(1.0, tt/0.003) * amt

def thud(f=70, dur=0.26, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    fq = f*np.exp(-tt*14) + 42
    return np.sin(2*np.pi*np.cumsum(fq)/SR) * np.exp(-tt*11) * amt

def bell(f=1568, dur=1.2, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    env = np.exp(-tt*3.2) * np.minimum(1.0, tt/0.004)
    v = np.sin(2*np.pi*f*tt) + 0.45*np.sin(2*np.pi*f*2.01*tt) + 0.22*np.sin(2*np.pi*f*3.02*tt)
    return v * env * amt

def riser(dur=1.4, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    nz = rng.normal(0, 1, m)
    band = hp(lp(nz, 0.42), 0.02)
    tone = np.sin(2*np.pi*(180 + 520*(tt/dur)**2)*tt) * 0.10
    return (band*0.9 + tone) * (tt/dur)**3.0 * amt

def paper(dur=0.30, amt=1.0):
    m = int(dur * SR); tt = np.arange(m) / SR
    nz = rng.normal(0, 1, m)
    band = hp(lp(nz, 0.30), 0.12)
    return band * np.sin(np.pi*(tt/dur))**1.5 * amt

def subdrop(dur=0.7, amt=1.0):
    m = int(dur*SR); tt = np.arange(m)/SR
    fq = 120*np.exp(-tt*5.0) + 32
    env = np.exp(-tt*4.0) * np.minimum(1.0, tt/0.008)
    return np.sin(2*np.pi*np.cumsum(fq)/SR) * env * amt

# ---------------- musical bed (warm, editorial) ----------------
prog = [(130.81, [261.63, 329.63, 392.00]),   # C
        (110.00, [220.00, 261.63, 329.63]),   # Am
        (87.31,  [174.61, 220.00, 261.63]),   # F
        (98.00,  [196.00, 246.94, 293.66])]   # G
seq = prog * 2
seg = D / 6.0
for ci, (base, notes) in enumerate(seq):
    st = ci*seg; dur = seg + 0.6
    i0 = int(st*SR); i1 = min(N, int((st + dur)*SR))
    if i1 <= i0:
        break
    tt = np.arange(i1-i0)/SR
    env = np.minimum(1.0, tt/0.9) * np.minimum(1.0, np.maximum(0, (dur-tt)/1.6)) * np.exp(-tt*0.12)
    for k, f in enumerate(notes):
        v = np.zeros(i1-i0)
        for h, w in ((1, 1.0), (2, 0.28), (3, 0.12)):
            v += w*np.sin(2*np.pi*f*h*tt + rng.uniform(0, 6.28))
        pan = -0.35 + 0.35*k
        gl = np.sqrt((1-pan)/2); gr = np.sqrt((1+pan)/2)
        v = v*env*0.052
        L[i0:i1] += v*gl; R[i0:i1] += v*gr
    v = 0.085*env*np.sin(2*np.pi*base*tt)
    L[i0:i1] += v; R[i0:i1] += v

# arpeggio enters at the filter scene
order = [0, 1, 2, 1]
tp = 7.6
while tp < D - 1.0:
    ci = int(tp/seg) % len(seq)
    f = seq[ci][1][order[int(tp*2) % len(order)]] * 2
    i0 = int(tp*SR); i1 = min(N, i0 + int(0.9*SR))
    if i1 > i0:
        tt = np.arange(i1-i0)/SR
        env = np.exp(-tt*5.0) * np.minimum(1.0, tt/0.006)
        v = 0.028*env*(np.sin(2*np.pi*f*tt) + 0.22*np.sin(2*np.pi*f*2*tt))
        pan = 0.30*np.sin(tp*1.7)
        gl = np.sqrt((1-pan)/2); gr = np.sqrt((1+pan)/2)
        L[i0:i1] += v*gl; R[i0:i1] += v*gr
    tp += 0.42

# ---------------- scene transitions ----------------
SCENES = [0.0, 3.6, 7.6, 12.0, 15.8, 19.6, 23.0]
for i, st in enumerate(SCENES):
    if i > 0:
        add2(paper(0.34, 0.55), st-0.34, pan=-0.12)
        add2(whoosh(0.50, 0.28), st-0.50, pan=0.18)
        add2(thud(76, 0.30, 0.5), st+0.02, pan=0.0)

# ---------------- S1 title (SplitText chars) ----------------
for i in range(13):                      # "Magiya holati"
    add2(click(1650 + i*55, 0.045, 0.13), 0.70 + i*0.018, pan=-0.5 + i/12.0*0.7)
add2(bell(784, 1.2, 0.10), 0.95, pan=-0.1)
for i in range(7):                       # "yetishtirildi" italic
    add2(click(1500 + i*70, 0.05, 0.10), 0.90 + i*0.018, pan=0.1)
for i in range(9):                       # hero sans chars (40x tozaroq)
    add2(click(1200 + i*45, 0.055, 0.15), 1.15 + i*0.045, pan=-0.3 + i/8.0*0.6)
add2(thud(88, 0.30, 0.42), 1.20, pan=0.0)
add2(pop(420, 900, 0.16, 0.18), 1.70, pan=0.2)

# ---------------- S2 95 % ----------------
tp = 4.0
while tp < 5.55:
    add2(click(2500, 0.028, 0.075), tp, pan=0.45)
    tp += 0.024
add2(whoosh(1.5, 0.16), 4.1, pan=0.0)
add2(bell(1318, 1.1, 0.10), 5.55, pan=0.15)

# ---------------- S3 filter ----------------
for i in range(24):                      # dots spawning
    add2(click(820 + (i % 6)*130, 0.03, 0.06), 8.25 + (i % 19)*0.026 + (i/24.0)*0.5, pan=-0.45 + (i % 6)*0.16)
add2(whoosh(0.95, 0.30), 9.35, pan=0.0)   # convergence
add2(subdrop(0.6, 0.22), 9.95, pan=0.0)
for i in range(8):                       # survivors form the crown
    add2(bell(1046 + i*62, 0.85, 0.085), 10.06 + i*0.035, pan=-0.45 + i*0.12)
add2(pop(300, 760, 0.20, 0.22), 10.16, pan=0.0)   # 8 % lands
add2(bell(1568, 1.1, 0.11), 10.22, pan=0.0)
add2(pop(520, 1150, 0.15, 0.14), 10.50, pan=-0.25)   # pills
add2(bell(1318, 0.95, 0.09), 10.75, pan=0.28)
add2(bell(1760, 0.85, 0.07), 11.60, pan=0.35)

# ---------------- S4 lattices ----------------
for i in range(49):
    add2(click(1500 + (i % 7)*100, 0.022, 0.05), 12.40 + (i % 7)*0.006 + (i//7)*0.02, pan=-0.6 + (i % 7)*0.2)
for i in range(25):
    add2(click(1200 + (i % 5)*110, 0.022, 0.045), 12.95 + (i % 5)*0.011 + (i//5)*0.02, pan=0.6 - (i % 5)*0.3)
add2(whoosh(0.40, 0.18), 13.05, pan=0.0)

# ---------------- S5 honest limits ----------------
for i in range(3):
    add2(thud(110 + i*20, 0.22, 0.22), 16.20 + i*0.15, pan=0.0)

# ---------------- S6 2029 ----------------
add2(riser(1.05, 0.22), 20.35, pan=0.0)
add2(bell(880, 1.3, 0.13), 21.42, pan=0.0)

# ---------------- S7 outro ----------------
add2(pop(340, 700, 0.22, 0.18), 23.20, pan=0.0)
for i in range(12):
    add2(bell(1568 + i*104, 0.5, 0.04), 23.30 + i*0.022, pan=-0.5 + i/11.0)
for i in range(9):                       # headline words
    add2(click(1000 + i*60, 0.05, 0.10), 23.75 + i*0.08, pan=-0.2 + i/8.0*0.4)
add2(thud(60, 0.5, 0.45), 23.78, pan=0.0)

# ---------------- master ----------------
L = lp(L, 0.42); R = lp(R, 0.42)
mid = (L + R)/2; side = lp((L - R)/2, 0.30)*1.15
L = mid + side; R = mid - side
fade = np.minimum(1.0, t/0.9) * np.minimum(1.0, (D - t)/1.8)
L *= fade; R *= fade
pk = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
L = np.tanh(L/pk*1.12)*0.80; R = np.tanh(R/pk*1.12)*0.80
pcm = (np.clip(np.stack([L, R], axis=1), -1, 1)*32767).astype("<i2")
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fx.wav")
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print(f"{out}  {os.path.getsize(out)/1e6:.2f} MB  {N/SR:.1f}s  peak {np.abs(L).max():.2f}")
