# Platform moslamasi — Instagram & YouTube Shorts

Yakuniy holat: **2026-10-29**. Hamma video QA'dan PASS (pastda o'lchovlar).

## Qaysi faylni qayerga

| Fayl | Nisbat | Kimga | Izoh |
|---|---|---|---|
| **`CLAUDE_VIRAL_clawd.mp4`** | 9:16 · 1080×1920 · 19.6 s | **Instagram Reels**, **YouTube Shorts**, TikTok | **YANGI asosiy versiya** — Clawd personaji qo'shilgan |
| `CLAUDE_VIRAL_vertical.mp4` | 9:16 · 1080×1920 · 19.6 s | — | Clawd'siz versiya (A/B uchun) |
| `CLAUDE_BRIEF_vertical.mp4` | 9:16 · 1080×1920 · 27.0 s | **Instagram Reels** (chuqurroq hikoya), **YouTube Shorts** | To'liq tushuntirish |
| `CLAUDE_FEED_4x5.mp4` | 4:5 · 1080×1350 · 27.0 s | **Instagram feed video** (Reels emas) | 4:5 feed'da eng katta maydon |
| `CLAUDE_BRIEF_horizontal.mp4` | 16:9 · 1920×1080 · 27.0 s | **YouTube asosiy**, sayt, prezentatsiya | Shorts emas — oddiy YouTube |
| `covers/COVER_VIRAL_CLAWD.png` | 9:16 | Reels / Shorts cover | Clawd kadri bilan |
| `covers/COVER_*.png` | tegishli nisbatda | cover / thumbnail | Video'dan olingan, brend bilan bir xil |

## Instagram (Reels + feed)

- **Reels:** 9:16 fayllar. Pastdagi ~420 px va o'ngdagi ~120 px **interfeys ostida qoladi** — matn bu zonalarga kirmaydi (QA'da tekshirilgan).
- **Feed video:** 4:5 fayl. Pastdagi ~15 % (`1350 × 0.15 ≈ 200 px`) amal paneli ostida — kontent undan yuqorida tugaydi.
- **Cover:** `covers/COVER_VIRAL.png` (Reels cover), `covers/COVER_FEED.png` (feed).
- **Birinchi kadr muhim:** Reels'da video birinchi kadrdan avtomatik boshlanadi, shuning uchun hook (0–0.55 s) o'zi cover bo'lib ishlaydi.
- **Ovoz:** FX-only, −15.2 LUFS. Instagram'da musiqa qo'shsangiz, pastga tushiring — FX zarbalari kesimlarda qolishi kerak.

## YouTube Shorts

- Shorts **9:16, ≤60 s** — 19.6 s va 27 s ikkisi ham mos.
- **Safe area:** pastda ~320 px (sarlavha/tugmalar), o'ngda ~120 px — bizning 9:16 layout shu chegaralarda.
- **Shorts uchun sarlavha:** 40 belgidan oshmasin, hook bilan bir xil bo'lsin.
- **End screen yo'q:** Shorts'da end screen ishlamaydi — loop (bizda 19.6 s oxiri hook'ga qaytadi) shu vazifani bajaradi.
- **Oddiy YouTube:** `CLAUDE_BRIEF_horizontal.mp4` (16:9) + `covers/COVER_WIDE.png` thumbnail.

## A/B uchun hook variantlari

Birinchi 0.55 s uch xil ohangda yozilgan variant kerak bo'lsa, quyidagi matnlardan foydalaning (bir xil kadr, faqat sarlavha):

1. **"40× tozaroq"** — hozirgi, raqamga tayanadi (eng xolis)
2. **"Kvant xatosi birinchi marta real chipda"** — yangilik urg'usi
3. **"92 % tashlanadi"** — qarama-qarshilik, eng yuqori "pattern interrupt"

Tavsiya: 1 va 3 ni bir xil kunda chiqarib, 24 soatdan keyin retention'ni solishtirish.

## Chop etishdan oldingi checklist

- [x] Davomiylik: 19.600 s / 27.000 s (aniq)
- [x] 60 fps, H.264 + AAC 48 kHz stereo
- [x] Loudness −15.2 … −15.3 LUFS, true-peak ≤ −1.8 dBFS
- [x] Har kesimda tovush zarbasi (15–22 dB aktsent)
- [x] Matn safe-zone ichida (QA `safe-zone` PASS)
- [x] Hech bir sahnada qotgan kadr yo'q (QA `dead scenes: none`)
- [ ] Platformada birinchi 3 soniyani tekshirish (yuklashdan keyin avtomatik sifat pasayishi mumkin)

## O'lchovlar (QA, `om/tools/qa.py`)

| fayl | motion density | LUFS | TP | kesim aktsenti |
|---|---|---|---|---|
| VIRAL 9:16 | 1.41 | −15.2 | −1.8 | 11.7–19.4 dB |
| BRIEF 9:16 | 1.22 | −15.3 | −2.4 | 17.8–18.4 dB |
| WIDE 16:9 | 1.38 | −15.2 | −2.4 | 13.5–22.1 dB |
| FEED 4:5 | PASS | ≈ −15 | ≤ −1.8 | kesimlar bir xil |

## Clawd overlays (yangi)

Claude Animation Base'dan olingan qo'lda bo'yalgan personaj (p5.brush, "qaynaydigan" chiziq) videoning uchta
nuqtasida paydo bo'ladi — fon dizayni o'zgarmagan, faqat alpha-PNG qatlam sifatida ustiga qo'yilgan:

| vaqt | nima bo'ladi | nima uchun |
|---|---|---|
| 0.34–1.66 s | raqam yoniga sakrab chiqadi, "40×" ni ko'rsatadi, hayratlanadi | hook: harakat + yuz jonli, matn esa qimirlamaydi |
| 8.80–11.45 s | ro'yxatni o'qiydi, keyin qog'ozga qizil **X** chizadi | "Nima o'zgarmadi?" ga emotsional javob |
| 16.75–19.60 s | qaytib chiqadi, CTA'ga qo'l silkitadi, kadrda qoladi | loop: reel boshiga qaytganda uzluksiz |

Texnik tafsilot va buyruqlar: `om/clawd/NOTES.md`.

## Clawd: BRIEF va FEED versiyalari

`CLAUDE_BRIEF_vertical_clawd.mp4` (1080×1920) va `CLAUDE_FEED_4x5_clawd.mp4` (1080×1350) — asl filmning
ustiga faqat ikki nuqtada Clawd qo'shilgan, fon dizayni va barcha matn tegmagan:

| vaqt | nima bo'ladi |
|---|---|
| 0.50–3.40 s | sarlavha yonida paydo bo'ladi, "40×" ni ko'rsatadi, keyin hayratlanadi |
| 23.40–26.80 s | xulosa kadrida qaytadi, qo'l silkitadi, loop uchun kadrda qoladi |

Feed nusxasida figura `flip: true` bilan oynaga qaraydi; y-koordinatalar zona jadvalida alohida yozilgan.
Render: `om/clawd/render_overlay.py "0.50:3.40,23.40:26.80" --fps=60 --page=brief_overlay.html --out=out/brief`,
so'ng ffmpeg overlay bilan kompozit (retsept `om/clawd/NOTES.md`).

## GENIE 4 · 20 s (yangi yangilik)

Google DeepMind Genie 4 haqidagi yangilik, o'sha uslubda (PAL + Fraunces + Inter, FX-only ovoz).
Manba: `om/genie4/index.html`. Natija: `motion-clone/GENIE4_vertical.mp4` va `motion-clone/GENIE4_vertical_clawd.mp4`
(Clawd hook va loop kadrlarida qo'shilgan, 0.32–1.70 s va 18.30–20.00 s).

| # | vaqt | kadr |
|---|---|---|
| S1 | 0–1.8 | "Ishlayotgan dunyo — endi u bilan gaplashish mumkin" (hook + Clawd) |
| S2 | 1.8–5.6 | 60 s → 120 s: Genie 3 gauge'i ichida Genie 4 ikki barobar uzun sahna |
| S3 | 5.6–9.6 | prompt yoziladi → dunyo javob beradi ("Yomg'ir yog'dir" → yomg'ir ovozi) |
| S4 | 9.6–13.0 | "Nima yo'q?" — ochiq API / barqaror obyekt / o'qisa bo'ladigan matn |
| S5 | 13.0–16.4 | "Kim oladi?" — trusted testers / AI Ultra · Project Genie / Gemini API · AI Studio |
| S6 | 16.4–18.2 | e'lon qilinmagan uch raqam: rezolyutsiya, narx, mustaqil benchmark — hammasi "—" |
| S7 | 18.2–20.0 | loop: "Dunyo ↔ prompt · Hali o'yin emas" + CTA (Clawd) |

Ovoz: `om/_fxbed.py genie4` → `om/genie4/assets/fx.wav` (20.0 s, kesimlar 1.8/5.6/9.6/13.0/16.4/18.2 ga
qulflangan, −14.1 LUFS, TP −1.5 dBFS). Kesim aktsenti 4.4–5.5 dB (eski filmlarda 5–6 dB — o'sha metodika).

## OCTOVERSE · 20 s (yangi yangilik)

GitHub Universe / Octoverse 2026 haqidagi yangilik — agentlar kod yozishning birinchi qadamiga aylandi.
Manba: `om/octoverse/index.html`. Natija: `motion-clone/OCTOVERSE_vertical.mp4` (Clawd'siz) va
`motion-clone/OCTOVERSE_vertical_clawd.mp4` (0.30–1.80 s hook, 18.40–20.00 s loop).

| # | vaqt | kadr |
|---|---|---|
| S1 | 0–2.0 | "Har ikkinchi PR" — endi odam boshlanmaydi (hook + Clawd) |
| S2 | 2.0–5.8 | mart 17% → sentabr 40%+: ikki bar bar, raqamlar bar bilan bir xil egri chizig'ida sanaladi |
| S3 | 5.8–9.8 | Octoverse raqamlari: commit 12.9B→34.3B, push 6.7B→17.9B, PR 538M→1.3B |
| S4 | 9.8–13.0 | "40% — birinchi qoralama agentdan"; 90% ikki haftada merge (insonlar 86%) |
| S5 | 13.0–16.2 | Copilot Fusion oynasi: agent ikki faylni yozadi, `npm test` yashil bo'ladi |
| S6 | 16.2–18.3 | "Kim to'laydi?" — o'rindiq emas, sarf; AI review approval o'rnida |
| S7 | 18.3–20.0 | loop: "Kod → topshiriq · Review — yangi dasturlash" (+ Clawd) |

Ovoz: `om/_fxbed.py octoverse` → `om/octoverse/assets/fx.wav` (20.0 s, kesimlar 2.0/5.8/9.8/13.0/16.2/18.3 ga
qulflangan, −14.1 LUFS, TP −1.3 dBFS). Yakuniy fayl: −15.0 LUFS, TP −2.1 dBFS, kesim aktsenti 4.4–5.4 dB.

**Texnik izoh (yangi tizim qoidalari):**
- Kod oynasi ham `world` canvas kabi **vaqtning sof funksiyasi** (`drawCode(t)`, seek'da qayta chiziladi) —
  shuning uchun render 60 fps da ham, skrinshotda ham bir xil.
- Canvas matni uchun monospace shriftda `✓` (U+2713) glifi yo'q — belgilar **chiziladi**, matnga yozilmaydi.
- Sarlavhalar qo'lda satrga bo'linadi (`<br>`): aks holda Fraunces bilan oxirgi so'z yolg'iz qoladi.

## HUD o'zgarishi (30.10.2026)

- **Vaqt chizig'i olib tashlandi:** yuqoridagi odometer soat (`00:20` / `00:27`) va uning progress chizig'i
  barcha 6 kompozitsiyadan (viral, brief, feed, wide, genie4, octoverse) chiqarildi. Kadrda endi faqat
  `TECH BRIEF / 2026` yorlig'i qoladi.
- **Handle:** `@techbrief.uz` → **`@DIYOR.CTR`** (pastki o'ng burchak, o'sha mono uslubda). Brief, feed va wide
  versiyalarida handle umuman yo'q edi — endi uchalasiga ham qo'shildi (`.hud .hdl`).

Barcha 9 fayl qayta render qilindi va Clawd qatlamlari yangi bazadan qayta kompozit qilindi.

## MISTRAL 4 · 20 s (yangi yangilik, 30.10.2026)

Mistral Large 4 ("Le Chonk") ochiq vaznlari chiqdi — 1 trillion parametr, 29.10.2026.
Manba: `om/mistral/index.html`. Natija: `motion-clone/MISTRAL4_vertical.mp4` va
`motion-clone/MISTRAL4_vertical_clawd.mp4` (hook 0.30–1.80, loop 18.40–20.00).

| # | vaqt | kadr |
|---|---|---|
| S1 | 0–2.0 | "Ochiq vaznlar" — Le Chonk endi uyingizda |
| S2 | 2.0–6.0 | Terminal-Bench **28.3% → 41%** (bar va raqam bir egri chizma) |
| S3 | 6.0–10.0 | jadval: ML4 41% · GLM-5.3 40% · DeepSeek V4.1 Flash 31% · Kimi K3 21% |
| S4 | 10.0–13.2 | **47%** kam token — har vazifada |
| S5 | 13.2–16.4 | ikki yo'l: API (oson) / o'z serveringiz (mustaqil) |
| S6 | 16.4–18.4 | mayda yozuv: Vals Index 32/44, lekin kodda oldinda |
| S7 | 18.4–20.0 | loop: "Ochiq vazn · yopiq nazorat — suverenlik, lekin sekin" |

Ovoz: `python3 om/_fxbed.py mistral` → kesimlar 2.0 / 6.0 / 10.0 / 13.2 / 16.4 / 18.4.
Yakuniy: −15.0 LUFS, TP −2.3 dBFS, kesim aktsenti 4.5–5.5 dB.

## Hajm siyosati (30.10.2026)

Fayl/hajm limitidan oshmaslik uchun:
- barcha `motion-clone/*.mp4` CRF 21 da qayta siqildi (120 MB → 67 MB), ko'z bilan farq yo'q;
- brief / feed / wide ovozlari `fx.wav` → `fx.ogg` (Vorbis q5), WAV nusxalari o'chirildi;
- render vaqtinchalik `.hyperframes` va `.cache/hyperframes` kataloglari tozalanadi.
Yangi videolar ham shu qoidada: `-crf 20`, WAV faqat manba sifatida qoladi.
