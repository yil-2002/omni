# Clawd overlay — Claude Animation Base qanday ishlatildi

Repo: `github.com/JohnHeibel/ClaudeAnimationBase` (p5.js + p5.brush, Claude Code uchun qilingan animatsiya starter-kit).

## Repo qanday ishlaydi (o'rganganlar)

| narsa | mazmuni |
|---|---|
| `ANIMATION_GUIDE.md` | qoidalar: **handmade** (brush + ink, "qaynaydigan" chiziq), **alive** (hech narsa qotmaydi), **one piece**; matn yozish taqiqlangan; har sahnada voqea; har kesimda o'tish |
| `src/core.js` | 1920×1080 canvas, `paint()` / `inkLine()`, kamera, `glow()`, `jump/take/stroll/spring`, paper + grain |
| `src/clawd.js` | Clawd personaji: 31 emotsiya (`emotions()`), 5 ko'rinish (`turn()`), shlyapalar, emotelar, raqslar |
| `src/timeline.js` | `shots([[t0, fn], ...])` — har shot `fn(t, lt, dur)`, **vaqtning sof funksiyasi** (parallel render uchun) |
| `render.mjs` | puppeteer + ffmpeg: sheet / strip / crop / stills / mp4 |

Kalit cheklov: **matn yo'q**. Clawd his-tuyg'u va belgilar bilan gapiradi, yozuv bilan emas.

## Bizning moslashtirish (`om/clawd/`)

1. **Canvas 1080×1920** (9:16 reel) — `src/core.js` da `W, H`.
2. **Shaffof fon**: `PROJECT.clear = true` → `draw()` da paper o'rniga `clear()`, `composite()` da grain/multiply va `clearRect()`; natija — **alpha PNG**. Shu bilan Clawd tayyor videoning **ustiga** qo'yiladi, dizayn tegilmaydi.
3. `overlay.html` — studioning soddalashtirilgan varianti (paper/grain/UI yo'q, faqat engine + bitta scena fayli).
4. `render_overlay.py` — Playwright bilan kadrlarni **resume** qilib render qiladi (Chrome bir marta ochiladi).
5. `src/scenes/viral_overlay.js` — uchta overlay oynasi (video vaqtida):
   - **0.34–1.66** hook: Clawd raqam yoniga sakrab chiqadi, "40×" ni ko'rsatadi, hayratlanadi
   - **8.80–11.45** "Nima o'zgarmadi?": ro'yxatni o'qiydi, so'ng qog'ozga **qizil X** chizadi (buzilmagan degani inkor — hazil)
   - **16.75–19.60** loop: qaytib sakrab chiqadi, CTA'ga qo'l silkitadi — reel shu kadrda loop bo'ladi

### Texnik topilmalar (boshqa urinmaslik uchun)

- p5.brush **`inkLine()` 2 nuqtali yoki kollinear yo'lni chizmaydi** (p5.brush `spline` chetlab o'tadi). Yechim: chiziqni `ribbon()` shakli sifatida `paint()` bilan chizish — `inkStroke()` helper.
- p5.brush shtrixlarni kechiktirib chizadi → overlay'da **`flushBrush()`** chaqirilmasa chiziqlar kadrga tushmaydi.
- Shaffof rejimda `draw()` da `clear()` va `composite()` da `clearRect()` **shart**, aks holda kadrlar ustma-ust yig'iladi.
- Chrome WebGL: `--use-angle=gl-egl` + `--ignore-gpu-blocklist` (llvmpipe, ~10 ms/frame render + ~1.6 s/frame PNG eksport).
- Overlay kadrlari: 409 kadr (60 fps), ffmpeg `overlay` + `setpts=PTS+offset/TB`, `eof_action=pass`.

## Buyruqlar

```bash
# kadrlarni render (resume bo'ladi)
cd om/clawd && python3 render_overlay.py "0.34:1.66,8.80:11.45,16.75:19.60" --fps=60
# video ustiga kompozit
ffmpeg -i base.mp4 -framerate 60 -i out/frames/0/f%05d.png ... -filter_complex "..." out.mp4
```
