// viral_overlay.js — Clawd, painted in watercolour + ink, riding ON TOP of the Claude-palette news film.
//
// Overlay shots: the canvas stays transparent (PROJECT.clear) and each shot draws ONLY Clawd and his props. The
// film underneath supplies the world; Clawd supplies the acting. Shot times are the FILM's times, so the renderer
// writes alpha PNGs for exactly the windows that need them.
//
//   S1  0.34 – 1.66   hook: he springs in on the empty right side of the hook, is startled by "40×", points at it, then
//                     throws his arms up — the reaction carries the frame while the type holds still
//   S4  8.80 – 11.45  "what did NOT change": he reads the page top to bottom, then hoists a drawn X on SHA-256
//   S7 16.75 – 19.60  loop payoff: he hops back in and waves at the CTA, settling on the frame the reel loops on
//
// Rule kept from ANIMATION_GUIDE: no lettering. Clawd's verdict is a painted mark (an X, drawn stroke by stroke).

(() => {
  const NEVER = [-999, -999];

  // Painted ink strokes instead of brush strokes: p5.brush's spline drops collinear/2-point paths, so a "drawn mark"
  // is built as a tapered ribbon shape and painted. `k` draws it on (0..1 of its length), which is the drawSVG effect.
  function inkStroke(P, w, k = 1, col = '#C4432B', o = {}) {
    if (k <= .01 || P.length < 2) return;
    const C = through(P, 10), n = Math.max(2, Math.round(C.length * clamp(k))), Q = C.slice(0, n);
    if (Q.length < 2) return;
    paint(ribbon(Q, w, o.w1 ?? w * .5), { wash: col, fill: mixCol(col, PAL.ink, .3), fillOp: 55, ink: PAL.ink, sw: o.sw ?? 1.3 });
  }

  // A drawn X, painted on one leg at a time. k = 0..1 of each stroke, so it can be drawn, held and pulled away.
  function drawX(cx, cy, s, kA, kB, rot = 0) {
    if (kA <= .01 && kB <= .01) return;
    push(); translate(cx, cy); rotate(rot);
    // a brush drags: the second leg starts a beat after the first and overshoots a hair
    inkStroke([[-s, -s * 1.02], [0, 0], [s * (1 + .04 * kB), s]], 26, kA, '#C4432B', { w1: 16, sw: 1.6 });
    inkStroke([[s, -s * 1.02], [0, 0], [-s * (1 + .04 * kA), s]], 26, kB, '#C4432B', { w1: 16, sw: 1.6 });
    pop();
  }

  // A paper card Clawd holds up: ruled lines (no words) and a clay tick — "the sheet he checks against".
  function holdCard(cx, cy, s, k, warm = 0) {
    if (k <= .01) return;
    push(); translate(cx, cy); scale(backOut(k));
    boilSeed('card');
    paint(rrPts(-1.15 * s, -1.5 * s, 2.3 * s, 3.0 * s, .22 * s, .8),
      { wash: '#FFF8E8', fill: mixCol(PAL.cream, PAL.ochre, warm * .5), fillOp: 70, bleed: .1, tex: .5, border: .5, ink: PAL.ink, sw: 1.5 });
    for (let i = 0; i < 3; i++) {
      const w = [1.5, 1.2, 1.62][i] * s, yy = (-.85 + i * .62) * s;
      inkStroke([[-.85 * s, yy], [-.85 * s + w * .5, yy + 1.5], [-.85 * s + w, yy]], 5, 1, mixCol(PAL.ink, PAL.cream, .5), { w1: 3, sw: .8 });
    }
    // the tick at the bottom: the check he just passed
    paint(ellPts(.55 * s, 1.06 * s, .3 * s, .3 * s, 12), { wash: mixCol(PAL.ochre, PAL.clayLt, .4), ink: PAL.ink, sw: 1.2 });
    pop();
  }

  // A rolled scroll standing in the grass, opened as he reads, re-rolled when he's done.
  function scroll(x, y, s, k) {
    if (k <= .02) return;
    const open = clamp(k);
    push(); translate(x, y); boilSeed('scroll');
    paint(rrPts(-.4 * s, -2.4 * s, .8 * s * (1 + 1.5 * open), 2.4 * s, .3 * s, 1),
      { wash: '#FFF8E8', fill: PAL.cream, fillOp: 80, bleed: .12, tex: .5, border: .5, ink: PAL.ink, sw: 1.6 });
    paint(ellPts(-.4 * s, -2.4 * s, .26 * s, .42 * s * open, 12), { wash: PAL.clayDk, fill: PAL.clay, fillOp: 90, ink: PAL.ink, sw: 1.4 });
    paint(ellPts(-.4 * s + .8 * s * (1 + 1.5 * open), -2.4 * s, .26 * s, .42 * s * open, 12), { wash: PAL.clayDk, fill: PAL.clay, fillOp: 90, ink: PAL.ink, sw: 1.4 });
    pop();
  }

  // ---------- S1: the hook (0.34 → 1.66) ----------
  // Reads: the film already says 40×; 1) a live thing lands on the right, clear of the type; 2) it points AT the
  // number, so the eye connects the two (cause before reaction); 3) it throws its arms up at "first time ever".
  function HOOK(t, lt, dur) {
    const u = 19, HX = 892, GY = 664;
    if (lt < .02) return;
    const hop = jump(lt, .04, .32, 2.4);
    const x = lerp(HX + 220, HX, backOut(seg(lt, 0, .30)));
    const mood = emotions(lt, [[.12, 'surprised'], [.44, 'excited'], [.96, 'starstruck']]);
    const point = ease(seg(lt, .20, .38)) * (1 - ease(seg(lt, .58, .76)));
    clawd(x, GY, u, {
      ...mood,
      dy: (mood.dy || 0) + hop.dy - .5 * point,
      sq: (mood.sq || 0) + hop.sq,
      aL: lerp(mood.aL ?? .2, -1.15, point),                  // he points DOWN-LEFT at "40× tozaroq"
      aR: lerp(mood.aR ?? .2, .55, point * .5),
      lookX: lerp(-.35, -1, point), lookY: lerp(.5, .95, point),
      rot: (mood.rot || 0) - .06 * point,
      boilKey: 'clawd-hook',
    });
    // the good-news sparkle pops over HIM, never over the type
    if (lt > .92) {
      const k = seg(lt, .92, 1.14);
      boilSeed('spark');
      if (k > 0 && k < 1) for (const [dx, dy, r] of [[-46, -216, 30], [26, -246, 20], [-10, -276, 13]])
        paint(starPts(x + dx, GY + dy, r * backOut(k) * (1 - .5 * k), .3, 4, k * 2),
          { wash: PAL.cream, fill: PAL.ochre, fillOp: 80, ink: PAL.ink, sw: 1.0 });
    }
    flushBrush();   // p5.brush defers strokes; without this the ink arrow would never composite
  }

  // ---------- S4: what did NOT change (8.80 → 11.45) ----------
  // Reads, one at a time: 1) a scroll already stands open beside him — he is mid-read; 2) he reads down the three
  // rows the film is revealing; 3) the third row he refuses: the card comes up, then the X is drawn over it and held.
  function LIMITS(t, lt, dur) {
    const u = 19, XG = 880, GY = 1188;
    const tRow1 = .30, tRow2 = 1.05, tRow3 = 1.80, tCard = 1.95, tXA = 2.14, tXB = 2.30;
    const bob = .55 * Math.sin(lt * 2.3);
    const mood = emotions(lt, [[tRow1, 'thinking'], [tRow2 + .1, 'neutral'], [tRow3, 'suspicious'], [tXA, 'determined'], [tXB + .12, 'determined']]);
    const look = kf(lt, [[tRow1, 0], [tRow2, -.55], [tRow3, -1], [tCard, -.8]]);
    const up = ease(seg(lt, tCard, tCard + .16));
    clawd(XG, GY, u, {
      ...mood,
      lookX: -.55, lookY: clamp(look, -1, 0), dy: (mood.dy || 0) + bob,
      aR: lerp(mood.aR ?? .2, 1.45, up) + .05 * Math.sin(lt * 5) * up,
      aL: lerp(mood.aL ?? .2, 1.45, up),
      rot: (mood.rot || 0) + .04 * Math.sin(lt * 1.9),
      boilKey: 'clawd-limits',
    });
    // the scroll he's been reading: rolled up at his feet, gone by the time the card is up
    scroll(XG - 178, GY + 12, 19, 1 - seg(lt, tCard - .16, tCard));
    // the card, held high on his left (page) side, then struck through
    const ck = seg(lt, tCard, tCard + .18);
    const cardX = XG - 6, cardY = GY - 336, cardRot = .05 + .05 * Math.sin(lt * 2.4);
    if (ck > .01) {
      boilSeed('cardhold');
      push(); translate(cardX, cardY); rotate(cardRot); holdCard(0, 0, 54, ck, seg(lt, tXA, tXA + .3)); pop();
    }
    if (lt > tXA - .02) {
      boilSeed('xmark');
      push(); translate(cardX, cardY); rotate(cardRot);
      const settle = ring(lt, [tXB], 7, 20) * .1;
      drawX(0, 0, 78, ease(seg(lt, tXA, tXA + .14)), ease(seg(lt, tXB, tXB + .14)), settle);
      pop();
    }
    flushBrush();   // the card's rules and the X are strokes, not washes
  }

  // ---------- S7: the loop payoff (16.75 → 19.60) ----------
  // The film comes back to "40× tozaroq / Hali boshlanishi". He returns the way he entered — a hop in from the right
  // — then waves at the CTA, then settles and looks back at the viewer: the still frame a reel loops on.
  function LOOP(t, lt, dur) {
    const u = 21, LX = 884, GY = 1444;
    if (lt < .02) return;
    const hop = jump(lt, .04, .32, 2.8);
    const x = lerp(LX + 190, LX, backOut(seg(lt, 0, .32)));
    const wave = seg(lt, .34, .5) * (1 - ease(seg(lt, 1.95, 2.35)));
    const mood = emotions(lt, [[.10, 'excited'], [.66, 'happy'], [1.55, 'proud'], [1.95, 'playful']]);
    clawd(x, GY, u, {
      ...mood,
      dy: (mood.dy || 0) + hop.dy,
      sq: (mood.sq || 0) + hop.sq,
      aL: lerp(mood.aL ?? .2, 1.3 + .45 * Math.sin(lt * 12), wave),
      aR: lerp(mood.aR ?? .2, .65, wave * .35),
      rot: (mood.rot || 0) + .05 * Math.sin(lt * 2.1),
      boilKey: 'clawd-loop',
    });
    // a clean ring of sparks off his head as he lands: the "back to the start" mark
    const k = seg(lt, .06, .48);
    boilSeed('loopspark');
    if (k > 0 && k < 1) for (let i = 0; i < 5; i++) {
      const a2 = -Math.PI / 2 + (i - 2) * .4, d = 40 + 56 * backOut(k);
      paint(starPts(x + Math.cos(a2) * d, GY - 8 * u + Math.sin(a2) * d - 12, 10 * (1 - k * .6) + 5, .32, 4),
        { wash: PAL.cream, fill: PAL.ochre, fillOp: 70, ink: PAL.ink, sw: .8 });
    }
    flushBrush();
  }

  shots([[0.34, HOOK], [8.80, LIMITS], [16.75, LOOP]]);
})();
