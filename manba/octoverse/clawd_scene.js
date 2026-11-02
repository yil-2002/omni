// clawd_scene.js — Clawd over the Octoverse film. Two windows only: he sells the idea in the hook, and he closes the
// loop at the end. Between them the film talks about itself (the world window already moves), so he stays out.
//
//   0.30 – 1.80   hook: springs up beside the headline, points at it, is startled
//   18.40 – 20.00 loop: hops back in, waves, settles on the last frame
//
// No lettering (ANIMATION_GUIDE rule 2). The mark he makes is painted.

(() => {
  // Painted ink stroke; p5.brush's spline drops collinear paths, so marks are shaped ribbons.
  function inkStroke(P, w, k = 1, col = '#C4432B', o = {}) {
    if (k <= .01 || P.length < 2) return;
    const C = through(P, 10), n = Math.max(2, Math.round(C.length * clamp(k)));
    if (n < 2) return;
    paint(ribbon(C.slice(0, n), w, o.w1 ?? w * .5), { wash: col, fill: mixCol(col, PAL.ink, .3), fillOp: 55, ink: PAL.ink, sw: o.sw ?? 1.2 });
  }

  // ---------- hook (0.32 → 1.70) ----------
  function HOOK(t, lt, dur) {
    const u = 19, X = 852, Y = 1350;
    if (lt < .02) return;
    const hop = jump(lt, .04, .32, 2.5);
    const x = lerp(X + 200, X, backOut(seg(lt, 0, .32)));
    const mood = emotions(lt, [[.10, 'surprised'], [.42, 'excited'], [.92, 'starstruck']]);
    const point = ease(seg(lt, .24, .42)) * (1 - ease(seg(lt, .66, .84)));
    clawd(x, Y, u, {
      ...mood,
      dy: (mood.dy || 0) + hop.dy,
      sq: (mood.sq || 0) + hop.sq,
      aL: lerp(mood.aL ?? .2, -1.25, point),          // he points up-left at "Ishlayotgan dunyo"
      aR: lerp(mood.aR ?? .2, .55, point * .5),
      lookX: lerp(-.3, -1, point), lookY: lerp(0, -.85, point),
      rot: (mood.rot || 0) - .05 * point,
      boilKey: 'clawd-g4-hook',
    });
    // a painted spark pops over HIM when the idea lands
    const k = seg(lt, .92, 1.16);
    if (k > 0 && k < 1) {
      boilSeed('g4spark');
      for (const [dx, dy, r] of [[-44, -190, 26], [26, -220, 17], [-8, -246, 11]])
        paint(starPts(x + dx, Y + dy, r * backOut(k) * (1 - .45 * k), .3, 4, k * 2),
          { wash: PAL.cream, fill: PAL.ochre, fillOp: 80, ink: PAL.ink, sw: .9 });
    }
    flushBrush();
  }

  // ---------- loop (18.30 → 20.00) ----------
  function LOOP(t, lt, dur) {
    const u = 17, X = 930, Y = 1230;
    if (lt < .02) return;
    const hop = jump(lt, .02, .28, 2.8);
    const x = lerp(X + 190, X, backOut(seg(lt, 0, .28)));
    const wave = seg(lt, .30, .44) * (1 - ease(seg(lt, dur - .72, dur - .38)));
    const mood = emotions(lt, [[.08, 'excited'], [.52, 'happy'], [dur - .8, 'playful']]);
    clawd(x, Y, u, {
      ...mood,
      dy: (mood.dy || 0) + hop.dy,
      sq: (mood.sq || 0) + hop.sq,
      aL: lerp(mood.aL ?? .2, 1.3 + .45 * Math.sin(lt * 12), wave),
      aR: lerp(mood.aR ?? .2, .6, wave * .35),
      rot: (mood.rot || 0) + .05 * Math.sin(lt * 2.2),
      boilKey: 'clawd-g4-loop',
    });
    const k = seg(lt, .04, .42);
    boilSeed('g4loop');
    if (k > 0 && k < 1) for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + (i - 2) * .4, d = 36 + 50 * backOut(k);
      paint(starPts(x + Math.cos(a) * d, Y - 8 * u + Math.sin(a) * d - 10, 9 * (1 - k * .6) + 4, .32, 4),
        { wash: PAL.cream, fill: PAL.ochre, fillOp: 70, ink: PAL.ink, sw: .7 });
    }
    flushBrush();
  }

  shots([[0.30, HOOK], [18.40, LOOP]]);
})();
