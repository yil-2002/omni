# CLAUDE-BRIEF v2 — Texnik reja (audit → jihoz → yuksaltirish)

Sana: 2026-10-29 · Loyiha: `/home/user/om/claude-brief` · Chiqish: 1080×1920, 60 fps

---

## 0. Hozirgi holat auditi (v1 = 6/10, foydalanuvchi bahosi)

| # | Muammo | Sabab (aniqlandi) | Yechim |
|---|--------|-------------------|--------|
| 1 | **Butun tipografika ingichka** | Faqat `Instrument Serif 400` ishlatilgan; sans faqat 400/500; `h1/h2` da weight yo'q | Fraunces **variable** (wght 100–900) + Inter 700–800 ni "display bold" momentlarga qo'shish |
| 2 | **Nuqtalar to'planishi noto'g'ri** | `x` offset va `y` alohida tween, target taxminiy (`0.86`, `356` px qo'lda) → nuqtalar chiziq bo'lib, sarlavha/darvoza ustiga chiqadi | Polar koordinata: har nuqta ring bo'ylab spawn → **bitta aniq target** `(540, 470)` ga `power3.in` bilan; matn zonasidan pastda |
| 3 | Ba'zi animatsiyalar "sakrab" ishlaydi | `drawSVG` o'rniga qo'lda `stroke-dashoffset`; matn reveal `onUpdate` bilan; `left` tween | GSAP rasmiy plaginlari (DrawSVG, SplitText, CustomEase) + faqat transform/opacity |
| 4 | Safe-zone buzilgan | HUD pastki qatori `y≈1784` — TikTok'dan caption zonasi (pastki 320–484 px) ustiga tushadi | Butun kontent **900×1400 markaziy box** ichida (top 260 / bottom 260 / left-right 90) |
| 5 | QA sekin | Har tekshiruv = 4 daqiqali render | `tools/frames.py` — Playwright bilan 7 sekundda 12 kadrli kontakt-sheet |

---

## 1. "Aniq jihoz" — qidiruv natijasida tanlangan stack

### 1.1 Tipografika (Claude'ning haqiqiy shriftlari OCHIQ EMAS)
Manbalar: shadcn.io/design/claude (DESIGN.md), Yacey/claude-design/typography.md, font-inspector.com, wtfont.app, brandmd.dev.

| Rol | Claude'da (proprietary) | Bizning bepul ekvivalent | Holat |
|-----|--------------------------|--------------------------|-------|
| Display serif | **Copernicus** / Tiempos Headline (Klim) | **Fraunces** variable — 4 o'q: `wght` 100–900, `opsz` 9–144, `SOFT` 0–100, `WONK` 0/1; italic alohida fayl | **yuklanadi** |
| Display sans (impact hero, 700–800) | **Anthropic Sans** / Styrene A | **Inter** 700 / 800 (allaqachon bor) | bor |
| Body | Anthropic Serif 400 / Anthropic Sans 400 | Fraunces 400 (opsz kichik) / Inter 400 | yuklanadi |
| Mono / texnik yorliq | Anthropic Mono / Söhne Mono | **JetBrains Mono** 400/500 | bor |

Muhim qoidalar (manbalardan):
- Anthropic'da **serif display hech qachon 700 bo'lmaydi** (poster bo'lib qoladi) — lekin **sans impact hero 700–800** bo'ladi. Shuning uchun: serif = 400–560 (`Fraunces SOFT 20–40`), sans display = 700–800. "Qalin" effekt shu ikkisining kontrastidan chiqadi.
- Tracking majburiy: `-0.02em … -0.045em` katta o'lchamlarda.
- **Cream `#faf9f5`** — brend; `#ffffff` emas.

### 1.2 Animatsiya dvigateli
- **GSAP 3.14 + plaginlar 100% BEPUL** (Webflow 2024-oktabrda sotib olgan, 2025-apreldan barcha Club plaginlari ochiq — greensock/gsap-skills SKILL.md tasdiqlaydi).
  Ishlatiladi: **SplitText** (harf/so'z reveal), **DrawSVG** (yoy, timeline, spark chizish), **CustomEase** (kinematik easing egri chiziqlari), **MotionPath** (zarracha trayektoriyasi). Fayllar `assets/vendor/` ga **vendorlanadi** (CDN'ga bog'liqlik yo'q).

### 1.3 Render / QA qurollari
- `hyperframes` 0.8.214 (`render --fps=60 --quality=delivery --keyframe-interval=2`)
- `TMPDIR=/home/user/render_tmp` majburiy (root disk 17 GB bo'sh; `/tmp` tmpfs 1 GB — render o'ladi)
- **`tools/frames.py`** — Playwright (chromium-1248) bilan `window.__timelines.main.seek(t)` → 12 kadr → kontakt-sheet. **4 daq emas, ~7 s.** Har iteratsiyada shu.
- `fonttools` (`pyftsubset`) — keraksiz gliflarni olib tashlash, woff2 hajmini kichraytirish.
- `ffprobe` + `ffmpeg volumedetect` — texnik qabul.

### 1.4 Platforma safe-zone (2026 ma'lumotlari)
Manbalar: bratify.app, kreateflo.com, adaptlypost.com (2026 guide'lar).
- Universal xavfsiz box: **900 × 1400 px** (markazda) — TikTok + Reels + Shorts uchun umumiy kesishma.
- TikTok: top 108–150 px, bottom **320–484 px**, right rail 120–140 px.
- Shuning uchun: kontent `y: 260 … 1660`, `x: 90 … 990`. HUD pastki qatori `y≈1600` ga ko'chadi, o'ng rail bo'sh qoladi.

---

## 2. Sahnalar bo'yicha yuksaltirish (v1 → v2)

| Sahna | v1 | v2 |
|-------|----|----|
| 1. Title | Instrument Serif 400, 12 nur | **Fraunces `opsz 144 / wght 560 / SOFT 30`** + `SplitText` bilan so'z-harf reveal; "yetishtirildi" italic `wght 500`; aksent so'z sans **800** |
| 2. 95 % | bitta yoy, counter | yoy **DrawSVG** bilan + 60 ta tick belgisi ketma-ket yonadi + raqam `opsz 144 / wght 600` |
| 3. 8 % filtr | nuqtalar noto'g'ri to'planadi | **ring spawn → bitta target**, 8 ta "omon qolgan" nuqta kattalashib birlashadi va **portlab** 8 % raqamiga aylanadi; karta raqamlari sans **800** |
| 4. Kodlar | 49+25 blok | bloklar **MorphSVG-siz**, lekin `DrawSVG` bilan bog'lovchi "bridge" chizig'i; bloklar `power4.out` stagger |
| 5. Halol chegara | ro'yxat | raqamlar (92 %, 40×, 1:10¹⁰) **sans 800** bilan ajratiladi, matn serif 400 |
| 6. 2029 | timeline | marker `MotionPath` bilan yo'lda yuradi, yil raqami `wght 700` |
| 7. Outro | Klod xabar kartasi | xabar matni **SplitText** bilan so'z-so'z; "40×" sans 800; kursor `CustomEase` bilan |

---

## 3. Ovoz (FX only — diktor yo'q)
- v1 dizayni saqlanadi, lekin: har yangi element uchun **alohida tick**, "8 % portlash" uchun **sub-drop + shimmer**, 2029 uchun **riser → bell**, finalda **soft impact**.
- Peak −3.4 dB, sahna kesimlarida dinamika (RMS −18…−25 dB).

---

## 4. Ish tartibi (bajarilish ketma-ketligi)
1. Fraunces variable (roman + italic) + subset → `assets/fonts/`
2. GSAP plaginlarini vendorlash → `assets/vendor/`
3. `tools/frames.py` QA qurolini yozish
4. `index.html` v2: safe-zone layout + bold ierarxiya + nuqta tuzatish
5. Har sahna uchun kontakt-sheet tekshiruv → nuqsonlarni tuzatish (3–5 iteratsiya)
6. Ovoz v2 (yangi effektlar)
7. Final render 60 fps delivery → `ffprobe` + loudness + kontakt-sheet
8. Topshirish: `present_file` + nima o'zgargani hisoboti

## 5. Qabul mezonlari (Done)
- [ ] Lint: 0 error
- [ ] Hech bir matn/hud TikTok/Reels safe-zone'dan tashqarida emas (900×1400)
- [ ] Zarrachalar **bitta aniq nuqtaga** to'planadi, matn ustiga chiqmaydi
- [ ] Kamida 3 joyda **qalin (600–800)** tipografik aksent, qolgani ingichka qoladi (kontrast)
- [ ] Ikki shrift tizimi (serif display + sans bold) ko'rinib turadi
- [ ] 1080×1920, 60 fps, h264+aac, audio mavjud
- [ ] Kontakt-sheet'da har sahna to'ldirilgan, bo'sh kadr yo'q
