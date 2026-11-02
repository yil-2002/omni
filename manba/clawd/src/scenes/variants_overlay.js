// variants_overlay.js — Clawd over the 27-second brief (9:16) and its 4:5 feed cut.
//
// Same film, two canvases: PROJECT.variant picks the zone table. Both cuts share a timeline, so the windows are the
// same in film seconds; only where he stands changes (the 4:5 crop lifts the footer, so he sits higher and smaller).
//
//   0.50 – 3.40    title reveal: he pops in beside the typing title, wowed, then points up at the star mark
//   23.40 – 26.80  conclusion: he hops back in and waves at the closing line — the frame the reel loops on
//
// No lettering, ever (ANIMATION_GUIDE rule 2): everything he "says" is a face, a gesture or a painted mark.

(() => {
  // zone table in FILM pixels
  const Z = {
    brief: { u: 21, hook: { x: 872, y: 1148, from: 240 }, loop: { x: 700, y: 1424, from: 230 }, loopU: 23 },
    feed:  { u: 17, hook: { x: 846, y: 902, from: 210, flip: true }, loop: { x: 690, y: 1076, from: 200 }, loopU: 18 },
  }[PROJECT.variant || 'brief'];

  // Painted ink stroke (p5.brush's spline drops collinear paths, so marks are drawn as shaped ribbons).
  function inkStroke(P, w, k = 1, col = '#C4432B', o = {}) {
    if (k <= .01 || P.length < 2) return;
    const C = through(P, 10), n = Math.max(2, Math.round(C.length * clamp(k)));
    if (n < 2) return;
    paint(ribbon(C.slice(0, n), w, o.w1 ?? w * .5), { wash: col, fill: mixCol(col, PAL.ink, .3), fillOp: 55, ink: PAL.ink, sw: o.sw ?? 1.2 });
  }

  // ---------- window 1: the title reveal ----------
  // Reads: 1) something alive lands on the empty right side while the title is still typing (motion carries the eye,
  // the type stays put); 2) it looks UP at the star and the title, pointing: the connection is made; 3) it settles
  // into a held, wowed pose so the number/word can land.
  function TITLE(t, lt, dur) {
    const u = Z.u, X = Z.hook.x, Y = Z.hook.y;
    if (lt < .02) return;
    const hop = jump(lt, .04, .34, 2.6);
    const x = lerp(X + Z.hook.from, X, backOut(seg(lt, 0, .34)));
    const mood = emotions(lt, [[.12, 'surprised'], [.48, 'excited'], [1.05, 'starstruck']]);
    const point = ease(seg(lt, .30, .48)) * (1 - ease(seg(lt, .78, .98)));
    // he always points at the page: on the 4:5 crop the type column is his left, so the character is mirrored
    const FL = !!Z.hook.flip, sg = FL ? -1 : 1;
    const pointArm = lerp(mood.aL ?? .2, -1.2, point), otherArm = lerp(mood.aR ?? .2, .6, point * .5);
    clawd(x, Y, u, {
      ...mood,
      flip: FL,
      dy: (mood.dy || 0) + hop.dy,
      sq: (mood.sq || 0) + hop.sq,
      aL: FL ? otherArm : pointArm,
      aR: FL ? pointArm : otherArm,
      lookX: lerp(-.3, -1, point) * sg, lookY: lerp(0, -.9, point),
      rot: (mood.rot || 0) - .05 * point * sg,
      boilKey: 'clawd-title',
    });
    // a small painted star pops over HIM at "Magiya holati" — the one mark he makes, and it is not a letter
    const k = seg(lt, 1.0, 1.25);
    if (k > 0 && k < 1) {
      boilSeed('mark');
      for (const [dx, dy, r] of [[-40, -196, 26], [30, -226, 17], [-8, -250, 11]])
        paint(starPts(x + dx, Y + dy, r * backOut(k) * (1 - .45 * k), .3, 4, k * 2),
          { wash: PAL.cream, fill: PAL.ochre, fillOp: 80, ink: PAL.ink, sw: .9 });
    }
    flushBrush();
  }

  // ---------- window 2: the conclusion ----------
  // Reads: 1) he hops in under the closing line (nothing else moves there); 2) waves at it — the reels' "that's it,
  // save this" gesture; 3) settles and looks at the viewer, holding the last frame still enough to loop on.
  function OUTRO(t, lt, dur) {
    const u = Z.loopU, X = Z.loop.x, Y = Z.loop.y;
    if (lt < .02) return;
    const hop = jump(lt, .04, .34, 2.9);
    const x = lerp(X + Z.loop.from, X, backOut(seg(lt, 0, .34)));
    const wave = seg(lt, .36, .52) * (1 - ease(seg(lt, dur - .95, dur - .55)));
    const mood = emotions(lt, [[.10, 'excited'], [.70, 'happy'], [1.55, 'proud'], [dur - 1.1, 'playful']]);
    clawd(x, Y, u, {
      ...mood,
      dy: (mood.dy || 0) + hop.dy,
      sq: (mood.sq || 0) + hop.sq,
      aL: lerp(mood.aL ?? .2, 1.3 + .45 * Math.sin(lt * 12), wave),
      aR: lerp(mood.aR ?? .2, .6, wave * .35),
      rot: (mood.rot || 0) + .05 * Math.sin(lt * 2.1),
      boilKey: 'clawd-outro',
    });
    const k = seg(lt, .06, .5);
    boilSeed('outrospark');
    if (k > 0 && k < 1) for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + (i - 2) * .4, d = 38 + 52 * backOut(k);
      paint(starPts(x + Math.cos(a) * d, Y - 8 * u + Math.sin(a) * d - 10, 9 * (1 - k * .6) + 4, .32, 4),
        { wash: PAL.cream, fill: PAL.ochre, fillOp: 70, ink: PAL.ink, sw: .7 });
    }
    flushBrush();
  }

  shots([[0.50, TITLE], [23.40, OUTRO]]);
})();
