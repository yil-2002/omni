# YO'RIQNOMA — Tech Brief video tizimi

Bu paket butun ishlab chiqarish tizimini o'z ichiga oladi: tayyor videolar, ularning manba kodlari,
ovoz generatori va Clawd qatlami. Har qanday yangi yangilikni shu tizimda 20–27 soniyalik vertikal
videoga aylantirish mumkin.

---

## 1. Papka tuzilishi

```
claude-techbrief/
├── YORIQNOMA.md          ← shu fayl
├── PLATFORM.md           ← har bir video uchun kadr-jadval, ovoz va texnik yozuvlar
├── natijalar/            ← 13 ta tayyor mp4 (pastdagi jadval)
├── manba/                ← har bir videoning HTML/JS manbasi
│   ├── claude-viral/     ← Willow kvant "40× tozaroq" (19.6 s)
│   ├── claude-brief/     ← o'sha mavzu, 27 s, 9:16
│   ├── claude-feed/      ← o'sha mavzu, 4:5
│   ├── claude-wide/      ← o'sha mavzu, 16:9
│   ├── genie4/           ← Google DeepMind Genie 4 (20 s)
│   ├── octoverse/        ← GitHub Octoverse 2026 (20 s)
│   ├── mistral/          ← Mistral Large 4 open weights (20 s)
│   └── clawd/            ← Clawd personaj qatlami (barcha videolar uchun)
└── vositalar/
    └── _fxbed.py         ← ovoz (FX) bed generatori
```

### Tayyor videolar (`natijalar/`)

| fayl | o'lcham | davomiylik | mazmun |
|---|---|---|---|
| `MISTRAL4_vertical.mp4` | 1080×1920 | 20 s | Mistral Large 4 ochiq vaznlar |
| `MISTRAL4_vertical_clawd.mp4` | 1080×1920 | 20 s | + Clawd |
| `OCTOVERSE_vertical.mp4` | 1080×1920 | 20 s | GitHub agentlar statistikasi |
| `OCTOVERSE_vertical_clawd.mp4` | 1080×1920 | 20 s | + Clawd |
| `GENIE4_vertical.mp4` | 1080×1920 | 20 s | DeepMind Genie 4 |
| `GENIE4_vertical_clawd.mp4` | 1080×1920 | 20 s | + Clawd |
| `CLAUDE_VIRAL_vertical.mp4` | 1080×1920 | 19.6 s | Willow 40× (viral versiya) |
| `CLAUDE_VIRAL_clawd.mp4` | 1080×1920 | 19.6 s | + Clawd |
| `CLAUDE_BRIEF_vertical.mp4` | 1080×1920 | 27 s | Willow, to'liq brief |
| `CLAUDE_BRIEF_vertical_clawd.mp4` | 1080×1920 | 27 s | + Clawd |
| `CLAUDE_FEED_4x5.mp4` | 1080×1350 | 27 s | Feed (4:5) |
| `CLAUDE_FEED_4x5_clawd.mp4` | 1080×1350 | 27 s | + Clawd |
| `CLAUDE_BRIEF_horizontal.mp4` | 1920×1080 | 27 s | YouTube/16:9 |

Barchasi 60 fps, H.264 + AAC. Ovoz — **faqat FX** (musiqa va ovoz yo'q).

---

## 2. Tizim nima bilan ishlaydi

| qatlam | vosita | izoh |
|---|---|---|
| Kompozitsiya | HTML + CSS + GSAP 3.13 | har bir sahna — DOM elementi, animatsiya — timeline |
| Render | `hyperframes@0.8.214` (npx) | HTML'ni kadr-ba-kadr 60 fps mp4 ga yozadi |
| Shriftlar | Fraunces / Inter / JetBrains Mono | `manba/<loyiha>/assets/fonts/` (lokal woff2) |
| Ovoz | `vositalar/_fxbed.py` (numpy) | kesimlarga qulflangan FX bed → `assets/fx.wav` yoki `.ogg` |
| Personaj | `manba/clawd/` (p5.js) | shaffof PNG kadrlar, keyin ffmpeg bilan ustiga qo'yiladi |
| Tekshiruv | Playwright + ffmpeg | kadr olish, LUFS/true-peak o'lchash |

### Dizayn tili (o'zgarmas qoidalar)
- Fon: `#faf9f5`, matn: `#141413`, urg'u: klay `#d97757` / `#c1613f`, ikkinchi daraja: `#d4a27f`.
- Sarlavha — Fraunces (serif, italic urg'u), katta raqam — Inter 800, HUD — JetBrains Mono.
- Har kadrda: burchak belgilari, pastda chapda mavzu yorlig'i, o'ngda **@DIYOR.CTR**.
- **Vaqt chizig'i/soat va "TECH BRIEF" yozuvi yo'q** — bu ataylab olib tashlangan.
- Sahna o'tishi: chapga whip-pan + 0.13 s fade, kesimda past-sub + whoosh.

---

## 3. Muhitni tayyorlash (bir marta)

```bash
# 1 · vositalar
sudo apt-get update
sudo apt-get install -y ffmpeg nodejs npm
# Node 22+ kerak (hyperframes talabi)
node -v            # >= 22 bo'lishi shart

# 2 · python tomoni
pip install playwright opencv-python-headless numpy
python3 -m playwright install chromium
python3 -m playwright install-deps chromium

# 3 · tizim kutubxonalari (chromium uchun)
sudo apt-get install -y libnspr4 libnss3 libasound2t64 libatk-bridge2.0-0 \
  libcups2 libgbm1 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
  libpango-1.0-0 libcairo2 libatspi2.0-0
```

Tekshirish:
```bash
ffmpeg -version | head -1
node -v
python3 -c "import playwright, cv2, numpy; print('ok')"
```

---

## 4. Yangi video yasash — 7 qadam

### Qadam 1 · mavzuni tanlash va faktlarni tekshirish
Har video — **bitta aniq yangilik**. Uch-to'rt mustaqil manbadan raqamlarni tekshiring.
Vendor raqami bilan mustaqil indeks farq qilsa — ikkalasini ham ko'rsating (MISTRAL4 shunday qilingan).

### Qadam 2 · eng yaqin loyihani nusxalash
```bash
cd manba
cp -r mistral yangi-mavzu          # eng toza shablon
cd yangi-mavzu
```
Loyiha ichida:
```
index.html            ← kompozitsiya + timeline (asosiy ish shu yerda)
assets/fonts/         ← shriftlar (o'zgartirmang)
assets/fx.wav         ← ovoz (Qadam 6 da qayta yaratiladi)
.hyperframes/         ← render keshi — paketga qo'shilmaydi
```

### Qadam 3 · sahnbalarni yozish (`index.html`)
Har sahna — `.scene` div, `id="s1".."s7"`, `data-start` / `data-duration` bilan.
Sahna tarkibi odatda: `.kick` (yorliq) → `.ed` yoki `.bl` (sarlavha) → kontent → `.cap` (izoh).

```html
<div class="scene clip" id="s2" data-start="2.0" data-duration="4.0" data-track-index="1">
  <div class="punch">
    <div class="kick"><span class="dotmk"></span>01 — Nima o'zgardi</div>
    <div class="ed" style="font-size:62px;">Sarlavha <em>urg'u</em></div>
    <div class="cap">Izoh: <b>muhim raqam</b>.</div>
  </div>
</div>
```

Timeline boshidagi uchta massivni **albatta** yangilang:
```js
const CUT  = [0, 2.0, 6.0, 10.0, 13.2, 16.4, 18.4];   // sahna boshlanishi
const ENDS = [2.0, 6.0, 10.0, 13.2, 16.4, 18.4, 20.0]; // sahna tugashi
```

### Qadam 4 · matn qoidalari (tajribadan)
1. **Sarlavhani qo'lda bo'ling** — `<br>` bilan. Aks holda Fraunces oxirgi so'zni yolg'iz qoldiradi.
2. Katta raqam 112–118 px dan oshmasin (1080 px kenglikda ikki qatorga tushadi).
3. Sanaladigan raqam bilan ustun **bir xil easing**da harakatlansin (`power2.inOut`) — keyin raqam va
   bar doim mos tushadi. (Eski xato: yoy 40% da, raqam 95% da edi.)
4. Canvas/WebGL ishlatsangiz — kadr **vaqtning sof funksiyasi** bo'lsin:
   `tl.seek` ni o'rab, har seek'da qayta chizing (`window.__paintWorldAt = paint`).
5. Canvas'da `✓` (U+2713) kabi gliflar bo'lmasligi mumkin — belgini **chizing**, matn yozmang.
6. `#arc` kabi SVG aylanalarni GSAP bilan aylantirsangiz, `svgOrigin: "240 240"` bering —
   `transform="rotate(...)"` atributi bilan birga ishlatilsa yoy buziladi.

### Qadam 5 · render tekshiruvi (arzon)
```bash
cat > /tmp/shot.py <<'EOF'
import asyncio, sys
from playwright.async_api import async_playwright
url, times, tag = sys.argv[1], [float(x) for x in sys.argv[2].split(',')], sys.argv[3]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage","--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width":1080,"height":1920})
        pg.on("pageerror", lambda e: print("ERR", e))
        await pg.goto(url, wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
        for t in times:
            await pg.evaluate(f"window.__timelines.main.pause(); window.__timelines.main.seek({t}); null")
            await pg.wait_for_timeout(140)
            await pg.screenshot(path=f"/tmp/{tag}_{t}.png")
        await b.close()
asyncio.run(main())
EOF
python3 /tmp/shot.py file://$PWD/index.html 1.5,4.6,9.0 /tmp/chk
```
Har kadrni ko'z bilan tekshiring: matn kesilmaganmi, raqam bilan grafik mosmi, hech narsa ustma-ust tushmaganmi.

### Qadam 6 · ovoz (FX bed)
`vositalar/_fxbed.py` ichida oxirgi funksiyani nusxalab, kesim vaqtlarini o'zgartiring:

```python
def yangi_mavzu():
    CUT = [2.0, 6.0, 10.0, 13.2, 16.4, 18.4]
    b = Bed(20.0)
    for i, c in enumerate(CUT):
        b.add(whoosh(0.46, 0.28), c - 0.30)          # kesim oldidan
        b.add(sub(0.55, 62 if i % 2 else 70, 0.58), c)  # kesimda past-sub
        b.add(click(1500 if i % 2 else 1900, 0.04, 0.10), c)
    for t in (0.02, 0.34, 0.66):
        b.add(type_tick(2300, 0.03, 0.13), t)        # matn paydo bo'lishi
    b.save("manba/yangi-mavzu/assets/fx.wav")
```
```bash
python3 vositalar/_fxbed.py yangi_mavzu
```
Faylni `index.html` ga ulang:
```html
<audio id="fx" src="assets/fx.wav" data-start="0" data-duration="20" data-volume="0.92"></audio>
```
> Hajm tejash uchun `fx.wav` ni `fx.ogg` ga o'girib ishlatsa ham bo'ladi:
> `ffmpeg -i fx.wav -c:a libvorbis -q:a 5 fx.ogg` (sifat amalda farq qilmaydi, hajm 25× kichik).

### Qadam 7 · yakuniy render
```bash
npx --yes hyperframes@0.8.214 render . --fps=60 --quality=delivery -o ../../natijalar/YANGI_vertical.mp4
```
- HyperFrames'ga **Node 22+** kerak.
- Render ~3–5 daqiqa (20 s video uchun). Terminal uzilsa: `nohup ... &` bilan ishga tushiring.
- Render tugagach `.hyperframes/` katalogini o'chirib tashlang (u yuzlab megabayt).

### (ixtiyoriy) Clawd qatlami
```bash
cd manba/clawd
python3 render_overlay.py "0.30:1.80,18.40:20.00" --fps=60 \
        --page=../yangi-mavzu/overlay.html --out=out/yangi
```
Keyin ffmpeg bilan ustiga qo'yish:
```bash
ffmpeg -i base.mp4 \
  -framerate 60 -start_number 0 -i out/yangi/0/f%05d.png \
  -framerate 60 -start_number 0 -i out/yangi/1/f%05d.png \
  -filter_complex "[1:v]setpts=PTS-STARTPTS+0.30/TB[c0];\
                   [2:v]setpts=PTS-STARTPTS+18.40/TB[c1];\
                   [0:v][c0]overlay=0:0:eof_action=pass[v1];\
                   [v1][c1]overlay=0:0,eof_action=pass,format=yuv420p[v]" \
  -map "[v]" -map 0:a -c:v libx264 -preset slow -crf 20 -c:a copy -movflags +faststart final.mp4
```

---

## 5. QA — topshirishdan oldin

```bash
# 1 · texnik parametrlar
ffprobe -v error -show_entries format=duration -show_entries stream=width,height,r_frame_rate \
        -of default=nw=1 natijalar/YANGI_vertical.mp4

# 2 · ovoz balandligi (Reels/Shorts maqsadi: ~ -14..-15 LUFS, TP <= -1 dBFS)
ffmpeg -hide_banner -nostats -i natijalar/YANGI_vertical.mp4 -af ebur128=peak=true -f null - 2>&1 \
  | grep -E "^\s+I:|Peak:"

# 3 · kesim aktsenti 4–6 dB bo'lishi kerak
python3 - <<'EOF'
import subprocess, numpy as np, wave
subprocess.run("ffmpeg -v error -y -i natijalar/YANGI_vertical.mp4 -ac 1 -ar 48000 /tmp/a.wav", shell=True)
w = wave.open('/tmp/a.wav'); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)/32768
db = lambda x: 20*np.log10(max(1e-6, np.sqrt((x**2).mean())))
for c in [2.0, 6.0, 10.0, 13.2, 16.4, 18.4]:
    i = int(c*48000); floor = np.concatenate([a[i-14400:i-2400], a[i+2400:i+14400]])
    print(c, round(float(db(a[i-240:i+240]) - db(floor)), 1), 'dB')
EOF

# 4 · kontrast varaqasi (7 kadrni bitta rasmga)
ffmpeg -v error -y -i natijalar/YANGI_vertical.mp4 \
  -vf "select='eq(n\,80)+eq(n\,260)+eq(n\,520)+eq(n\,700)+eq(n\,880)+eq(n\,1060)+eq(n\,1180)',scale=210:-1,tile=7x1" \
  -frames:v 1 /tmp/sheet.png
```

**Qabul mezonlari:** ○ matn kesilmagan ○ raqam va grafik mos ○ soat/TECH BRIEF yo'q ○ @DIYOR.CTR joyida
○ kesim aktsenti 4–6 dB ○ LUFS −14..−15 ○ TP ≤ −1 dBFS ○ 60 fps ○ audio oqimi mavjud.

---

## 6. Tez-tez uchraydigan xatolar

| belgi | sabab | yechim |
|---|---|---|
| `Audio mix failed: Source not found for audio element fx` | ses fayli yo'q yoki nomi noto'g'ri | `assets/fx.wav` (yoki `.ogg`) mavjudligini va `src=` ni tekshiring |
| Renderda audio umuman yo'q | audio manba topilmadi, video baribir chiqadi | yuqoridagi qatorni tuzatib **qayta render** qiling |
| `HyperFrames requires Node.js >= 22` | Node 20 | Node 22+ o'rnating (`nvm install 22`) |
| `Render failed ... PARTIAL` | oldingi render bilan fayl ustma-ust tushgan | avvalgi mp4 ni o'chirib qayta render qiling |
| `chrome-headless-shell: libnspr4.so` | tizim kutubxonasi yo'q | 3-bo'limdagi apt paketlari |
| Yoy/aylana g'alati chiziladi | SVG `rotate()` + GSAP `rotation` birga | `gsap.set(el,{svgOrigin:"X Y",rotation:-90})` |
| Sarlavhada bitta so'z yolg'iz qoladi | avtomatik qator bo'linishi | qo'lda `<br>` qo'ying |
| Workspace hajmi oshib ketadi | `.hyperframes/`, kadr papkalari, WAV'lar | `rm -rf .hyperframes out/`; videolarni `-crf 20..26` bilan saqlang |

---

## 7. Hajm siyosati (muhim)

- Yakuniy videolar `-crf 20` (arxiv uchun `-crf 24..26`) bilan saqlanadi — sifat yetarli, hajm 3–5× kichik.
- Ovoz: `fx.wav` (manba) → `fx.ogg` (ishlatiladigan). Ikkalasini birga saqlamang.
- Renderdan keyin darhol: `rm -rf .hyperframes out/ render_tmp/ .npm/_npx`
- Clawd kadrlari (`out/<nom>/0/f*.png`) — oraliq mahsulot, saqlamang.

---

## 8. Manbalar qayerdan olinadi

Videolar quyidagi ochiq manbalarga tayangan (har birining sanasi `PLATFORM.md` da):
Google DeepMind / Genie 4 (27.10.2026), GitHub Universe & Octoverse 2026 (28.10.2026),
Mistral AI — Mistral Large 4 open weights (29.10.2026), Science — Willow "magic state cultivation"
(DOI 10.1126/science.aee7961).

Fakt yozishdan oldin: **raqamni ikki manbadan tekshiring**, vendor va mustaqil indeks farqini yashirmang,
"preview / gated access / open weights" kabi holatlarni aniq yozing.
