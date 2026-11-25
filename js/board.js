// Gameplay: tapes (spline paths) with a ball at each end. Tap a ball -> it rolls along its own path
// to the other end, eating the line. Another tape's ball sitting on the route blocks it (lose a heart).
'use strict';
const PALETTE = { // from line_* / ball_* materials (_BaseColor, _SColor)
  blue1: { line: [83, 172, 196], ball: [0, 136, 255], dark: [0, 70, 160] },
  blue2: { line: [16, 46, 175], ball: [1, 0, 178], dark: [0, 0, 100] },
  brown1: { line: [120, 42, 20], ball: [109, 40, 40], dark: [60, 16, 16] },
  gray1: { line: [147, 147, 147], ball: [126, 126, 126], dark: [70, 70, 70] },
  green1: { line: [102, 163, 3], ball: [27, 172, 0], dark: [10, 100, 0] },
  green2: { line: [13, 101, 0], ball: [18, 113, 0], dark: [6, 60, 0] },
  orange1: { line: [222, 170, 0], ball: [232, 140, 8], dark: [150, 70, 0] },
  pink1: { line: [193, 124, 168], ball: [241, 93, 110], dark: [150, 40, 70] },
  purple1: { line: [128, 0, 168], ball: [104, 0, 199], dark: [60, 0, 120] },
  red1: { line: [200, 56, 56], ball: [219, 41, 28], dark: [130, 10, 10] },
  yellow1: { line: [230, 217, 5], ball: [213, 175, 8], dark: [140, 110, 0] },
};
const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

const Board = (() => {
  const BALL_R = 0.2, SWEEP = 0.2, SKIN = 0.1; // grazing contacts (<0.1 overlap) do not block: all 587 levels solvable (tools/solve.mjs)
  let cv, g, W = 0, H = 0, dpr = 1;
  let tapes = [], level = null, cam = { x: 0, y: 0, s: 50, fit: 50, minS: 10, maxS: 200 };
  let view = { top: 0, bottom: 0 };
  let fx = [], time = 0, opening = 0, hearts = 3, maxHearts = 3, busyEnd = false;
  let hint = null, tutorial = null, frozen = false;
  const ev = {}; // callbacks: onTap, onHit, onRemoved, onWin, onHeartsOut, onProgress
  const ballCache = {};
  let shadowImg = null, splashImgs = [];
  const stats = { taps: 0, hits: 0, hintsUsed: 0, t0: 0 };

  function init(canvas) {
    cv = canvas; g = cv.getContext('2d');
    shadowImg = new Image(); shadowImg.src = UI.sprite('mianpian');
    for (let i = 1; i <= 5; i++) { const im = new Image(); im.src = UI.sprite('pm' + i); splashImgs.push(im); }
    resize(); addEventListener('resize', resize);
    bindInput();
    requestAnimationFrame(loop);
  }
  function resize() {
    const r = cv.parentElement.getBoundingClientRect();
    dpr = Math.min(2.5, devicePixelRatio || 1);
    W = r.width; H = r.height; cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    if (level) fitCamera(false);
  }
  function setViewInsets(topPx, bottomPx) { view.top = topPx; view.bottom = bottomPx; if (level) fitCamera(false); }

  // ---------- geometry ----------
  function sample(segs) {
    const P = [];
    for (let k = 0; k < segs.length; k++) {
      const [x0, y0, x1, y1, x2, y2, x3, y3] = segs[k];
      const len = Math.hypot(x1 - x0, y1 - y0) + Math.hypot(x2 - x1, y2 - y1) + Math.hypot(x3 - x2, y3 - y2);
      const n = Math.max(4, Math.ceil(len / 0.03));
      for (let i = (k ? 1 : 0); i <= n; i++) {
        const t = i / n, u = 1 - t;
        P.push(u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3, u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3);
      }
    }
    const n = P.length / 2, cum = new Float32Array(n);
    for (let i = 1; i < n; i++) cum[i] = cum[i - 1] + Math.hypot(P[2 * i] - P[2 * i - 2], P[2 * i + 1] - P[2 * i - 1]);
    return { P: new Float32Array(P), cum, L: cum[n - 1] };
  }
  function at(t, s) { // point at arc length s
    const { P, cum, L } = t;
    s = Math.max(0, Math.min(L, s));
    let lo = 0, hi = cum.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (cum[m] < s) lo = m; else hi = m; }
    const seg = cum[hi] - cum[lo] || 1, f = (s - cum[lo]) / seg;
    return [P[2 * lo] + (P[2 * hi] - P[2 * lo]) * f, P[2 * lo + 1] + (P[2 * hi + 1] - P[2 * lo + 1]) * f, lo];
  }
  function startPos(t) { return [t.P[0], t.P[1]]; }
  function endPos(t) { const n = t.P.length; return [t.P[n - 2], t.P[n - 1]]; }

  // ---------- level ----------
  function load(L, opts = {}) {
    level = L; tapes = []; fx = []; hint = null; frozen = false; busyEnd = false;
    hearts = maxHearts = opts.hearts || 3;
    Object.assign(stats, { taps: 0, hits: 0, hintsUsed: 0, t0: performance.now() });
    for (const d of L.tapes) {
      const s = sample(d.segs);
      const pal = PALETTE[d.color] || PALETTE.gray1;
      tapes.push(Object.assign(s, {
        id: d.id, color: d.color, pal, w: Math.max(d.w, 0.05), z: d.z || 0,
        rS: BALL_R * (d.ev || 1), rE: BALL_R * (d.eev || 1), speed: d.speed || 5, click: d.click || 0.35,
        enc: d.enc, state: 'idle', dir: 1, d: 0, v: 0, hitT: 0, flash: 0, shake: 0, shakeDir: [0, 0], appear: 0,
      }));
    }
    // draw order: farther (larger z) first, then authoring order
    tapes.forEach((t, i) => t.order = i);
    tapes.sort((a, b) => (b.z - a.z) || (a.order - b.order));
    opening = 0;
    tutorial = L.tut || null;
    fitCamera(true);
    emit('onProgress', 0, tapes.length);
  }
  function bounds() {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const t of tapes) for (let i = 0; i < t.P.length; i += 2) {
      const x = t.P[i], y = t.P[i + 1];
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    const m = 0.35; return [x0 - m, y0 - m, x1 + m, y1 + m];
  }
  function fitCamera(reset) {
    const [x0, y0, x1, y1] = bounds();
    const aw = W * 0.94, ah = Math.max(50, H - view.top - view.bottom) * 0.96;
    const s = Math.min(aw / (x1 - x0), ah / (y1 - y0));
    cam.fit = s; cam.minS = s * 0.9; cam.maxS = Math.max(s * 4, 140);
    if (reset || cam.s < cam.minS) { cam.s = s; cam.x = (x0 + x1) / 2; cam.y = (y0 + y1) / 2; cam.cx = cam.x; cam.cy = cam.y; }
    clampCam();
  }
  function clampCam() {
    const [x0, y0, x1, y1] = bounds();
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const hw = Math.max(0, (x1 - x0) / 2 - W / 2 / cam.s * 0.6), hh = Math.max(0, (y1 - y0) / 2 - (H - view.top - view.bottom) / 2 / cam.s * 0.6);
    cam.x = Math.max(cx - hw, Math.min(cx + hw, cam.x)); cam.y = Math.max(cy - hh, Math.min(cy + hh, cam.y));
  }
  const sx = x => (x - cam.x) * cam.s + W / 2;
  const sy = y => -(y - cam.y) * cam.s + view.top + (H - view.top - view.bottom) / 2;
  const wx = px => (px - W / 2) / cam.s + cam.x;
  const wy = py => -(py - view.top - (H - view.top - view.bottom) / 2) / cam.s + cam.y;

  // ---------- rules ----------
  function originR(t) { return t.dir > 0 ? t.rS : t.rE; }
  function farR(t) { return t.dir > 0 ? t.rE : t.rS; }
  function movingPos(t) { const s = t.dir > 0 ? t.d : t.L - t.d; return at(t, s); }
  // balls of tape u that can block others
  function ballsOf(u, includeMoving = true) {
    if (u.state === 'gone' || u.state === 'done') return [];
    if (u.state === 'idle') return [[...startPos(u), u.rS], [...endPos(u), u.rE]];
    const far = u.dir > 0 ? [...endPos(u), u.rE] : [...startPos(u), u.rS];
    if (!includeMoving) return [far];
    const m = movingPos(u); return [far, [m[0], m[1], originR(u)]];
  }
  function obstacles(t, includeMoving = true) {
    const out = [];
    for (const u of tapes) if (u !== t) for (const b of ballsOf(u, includeMoving)) out.push([b[0], b[1], b[2], u]);
    return out;
  }
  // first blocking hit when moving t (dir) from d0 to d1 ; returns {d, u} or null
  function sweep(t, dir, d0, d1, obs) {
    const rm = SWEEP * ((dir > 0 ? t.rS : t.rE) / BALL_R);
    const step = 0.03;
    for (let d = d0; d <= d1 + 1e-6; d += step) {
      const dd = Math.min(d, d1);
      const p = at(t, dir > 0 ? dd : t.L - dd);
      for (const o of obs) {
        const lim = rm + o[2] - SKIN;
        const dx = p[0] - o[0], dy = p[1] - o[1];
        if (dx * dx + dy * dy < lim * lim) return { d: dd, u: o[3], o };
      }
      if (dd >= d1) break;
    }
    return null;
  }
  function routeClear(t, dir) { return !sweep(t, dir, 0, t.L, obstacles(t, false)); }

  function pick(px, py) {
    const x = wx(px), y = wy(py);
    const minR = 26 / cam.s;
    let best = null, bd = 1e9;
    for (const t of tapes) {
      if (t.state !== 'idle') continue;
      for (const [dir, p, r] of [[1, startPos(t), t.rS], [-1, endPos(t), t.rE]]) {
        const d = Math.hypot(p[0] - x, p[1] - y), lim = Math.max(t.click * r / BALL_R, minR);
        if (d < lim && d < bd) { bd = d; best = { t, dir }; }
      }
    }
    return best;
  }
  function tap(t, dir) {
    if (frozen || hearts <= 0) return;
    t.state = 'move'; t.dir = dir; t.d = 0; t.v = t.speed; t.t = 0;
    stats.taps++;
    if (hint && hint.t === t) hint = null;
    if (tutorial && tutorial.tape === t.id) tutorial.done = true;
    t.clear = routeClear(t, dir);
    Sfx.play('Sound_ClickTrue'); Sfx.roll(+1); Sfx.vibrate(10);
    emit('onTap', t);
  }
  function update(dt) {
    time += dt;
    if (opening < 1) opening = Math.min(1, opening + dt / 0.9);
    const allCommitted = tapes.every(t => t.state === 'gone' || t.state === 'done' || (t.state === 'move' && t.clear));
    for (const t of tapes) {
      if (t.flash > 0) t.flash -= dt; if (t.shake > 0) t.shake -= dt;
      if (t.state === 'move') {
        t.t += dt;
        const vmax = allCommitted ? 16 : 11;
        if (t.t > 0.12) t.v = Math.min(vmax, t.v + dt * (allCommitted ? 30 : 9));
        const d1 = Math.min(t.L, t.d + t.v * dt);
        const hit = sweep(t, t.dir, t.d, d1, obstacles(t, true));
        if (hit) {
          t.d = hit.d; t.state = 'hit'; t.hitT = 0;
          onHit(t, hit);
        } else {
          t.d = d1;
          if (t.d >= t.L - 1e-4) complete(t);
        }
      } else if (t.state === 'hit') {
        t.hitT += dt;
        if (t.hitT > 0.345) { t.state = 'return'; t.v = Math.max(8, t.speed * 1.6); }
      } else if (t.state === 'return') {
        t.d -= t.v * dt; t.v = Math.min(18, t.v + dt * 12);
        if (t.d <= 0) {
          t.d = 0; t.state = 'idle'; Sfx.roll(-1);
          if (hearts <= 0 && !tapes.some(u => u.state === 'move' || u.state === 'hit' || u.state === 'return')) { frozen = true; emit('onHeartsOut'); }
        }
      } else if (t.state === 'done') {
        t.doneT += dt;
        if (t.doneT > 0.25) t.state = 'gone';
      }
    }
    for (let i = fx.length - 1; i >= 0; i--) { fx[i].t += dt; if (fx[i].t > fx[i].dur) fx.splice(i, 1); }
    if (!busyEnd && tapes.length && tapes.every(t => t.state === 'gone')) {
      busyEnd = true; frozen = true;
      setTimeout(() => emit('onWin', summary()), 450);
    }
  }
  function onHit(t, hit) {
    const p = movingPos(t);
    stats.hits++;
    hearts = Math.max(0, hearts - 1);
    t.flash = 0.35; t.shakeDir = [p[0] - hit.o[0], p[1] - hit.o[1]];
    const u = hit.u; u.flash = 0.35; u.shake = 0.3;
    const n = Math.hypot(...t.shakeDir) || 1; u.shakeDir = [-t.shakeDir[0] / n, -t.shakeDir[1] / n];
    fx.push({ k: 'ring', x: (p[0] + hit.o[0]) / 2, y: (p[1] + hit.o[1]) / 2, t: 0, dur: 0.53 });
    Sfx.play('Sound_Hit'); Sfx.play('Sound_ClickFalse', { vol: 0.6 }); Sfx.vibrate(60);
    emit('onHit', t, hearts);
  }
  function complete(t) {
    t.state = 'done'; t.doneT = 0; Sfx.roll(-1);
    const p = t.dir > 0 ? endPos(t) : startPos(t);
    fx.push({ k: 'splash', x: p[0], y: p[1], c: t.pal.ball, img: splashImgs[(Math.random() * 5) | 0], rot: Math.random() * 6.28, t: 0, dur: 0.85, r: farR(t) });
    Sfx.play('Sound_Splash0' + (1 + ((Math.random() * 4) | 0)));
    const removed = tapes.filter(u => u.state === 'gone' || u.state === 'done').length;
    emit('onProgress', removed, tapes.length);
    emit('onRemoved', t);
  }
  function summary() {
    return { time: (performance.now() - stats.t0) / 1000, taps: stats.taps, hits: stats.hits, hints: stats.hintsUsed, tapes: tapes.length, heartsLeft: hearts };
  }
  function progress() { return tapes.length ? tapes.filter(u => u.state === 'gone' || u.state === 'done').length / tapes.length : 0; }

  // hint: a tape+direction whose whole route is clear right now
  function findHint() {
    const cands = [];
    for (const t of tapes) if (t.state === 'idle') for (const dir of [1, -1]) if (routeClear(t, dir)) cands.push({ t, dir });
    if (!cands.length) return null;
    cands.sort((a, b) => a.t.L - b.t.L);
    return cands[0];
  }
  function showHint() {
    const h = findHint(); if (!h) return false;
    hint = Object.assign(h, { t0: time }); stats.hintsUsed++;
    // make sure the ball is on screen
    const p = h.dir > 0 ? startPos(h.t) : endPos(h.t);
    if (sx(p[0]) < 20 || sx(p[0]) > W - 20 || sy(p[1]) < view.top || sy(p[1]) > H - view.bottom) { cam.x = p[0]; cam.y = p[1]; clampCam(); }
    return true;
  }
  function tutorialTarget() {
    if (!tutorial || tutorial.done || opening < 1) return null;
    if (tutorial.type === 3) return null;
    const t = tapes.find(u => u.id === tutorial.tape && u.state === 'idle');
    if (!t) return null;
    let dir = routeClear(t, 1) ? 1 : routeClear(t, -1) ? -1 : 1;
    return { t, dir };
  }
  function refill(n) { hearts = n || maxHearts; frozen = false; }

  // ---------- render ----------
  function ballSprite(color, rpx) {
    const key = color + '|' + Math.round(rpx * dpr);
    if (ballCache[key]) return ballCache[key];
    const pal = PALETTE[color] || PALETTE.gray1;
    const R = Math.max(2, Math.round(rpx * dpr)), S = R * 2 + 4;
    const c = document.createElement('canvas'); c.width = c.height = S;
    const x = c.getContext('2d'), m = S / 2;
    let gr = x.createRadialGradient(m - R * 0.35, m - R * 0.4, R * 0.1, m, m, R);
    gr.addColorStop(0, css(mix(pal.ball, [255, 255, 255], 0.45)));
    gr.addColorStop(0.45, css(pal.ball));
    gr.addColorStop(0.92, css(mix(pal.ball, pal.dark, 0.6)));
    gr.addColorStop(1, css(pal.dark));
    x.fillStyle = gr; x.beginPath(); x.arc(m, m, R, 0, 7); x.fill();
    // rim light
    gr = x.createRadialGradient(m + R * 0.25, m + R * 0.35, R * 0.5, m, m, R * 1.02);
    gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.85, 'rgba(255,255,255,0)'); gr.addColorStop(1, 'rgba(255,255,255,0.25)');
    x.fillStyle = gr; x.beginPath(); x.arc(m, m, R, 0, 7); x.fill();
    // specular
    x.fillStyle = 'rgba(255,255,255,0.85)';
    x.beginPath(); x.ellipse(m - R * 0.38, m - R * 0.42, R * 0.22, R * 0.14, -0.7, 0, 7); x.fill();
    return ballCache[key] = c;
  }
  function drawBall(t, x, y, r, extra = {}) {
    let X = sx(x), Y = sy(y), R = r * cam.s;
    if (t.shake > 0) { const k = Math.sin(t.shake * 60) * 3 * (t.shake / 0.3); X += t.shakeDir[0] * k; Y -= t.shakeDir[1] * k; }
    const sc = extra.scale ?? 1;
    R *= sc;
    if (R < 0.5) return;
    if (shadowImg.complete && shadowImg.naturalWidth) {
      const s = R * 2.6; g.globalAlpha = 0.55 * (extra.alpha ?? 1);
      g.drawImage(shadowImg, X + R * 0.35 - s / 2, Y + R * 0.45 - s / 2, s, s); g.globalAlpha = 1;
    }
    const sp = ballSprite(t.color, R);
    g.globalAlpha = extra.alpha ?? 1;
    g.drawImage(sp, X - sp.width / dpr / 2, Y - sp.height / dpr / 2, sp.width / dpr, sp.height / dpr);
    if (t.flash > 0) { g.fillStyle = `rgba(255,40,40,${Math.min(0.75, t.flash * 2.2)})`; g.beginPath(); g.arc(X, Y, R, 0, 7); g.fill(); }
    g.globalAlpha = 1;
  }
  function strokeRange(t, s0, s1, width, style) {
    if (s1 - s0 < 1e-4) return;
    const a = at(t, s0), b = at(t, s1);
    g.beginPath(); g.moveTo(sx(a[0]), sy(a[1]));
    for (let i = a[2] + 1; i <= b[2]; i++) g.lineTo(sx(t.P[2 * i]), sy(t.P[2 * i + 1]));
    g.lineTo(sx(b[0]), sy(b[1]));
    g.lineWidth = width; g.strokeStyle = style; g.stroke();
  }
  function lineRange(t) {
    if (t.state === 'idle') return [0, t.L];
    if (t.state === 'gone' || t.state === 'done') return null;
    return t.dir > 0 ? [t.d, t.L] : [0, t.L - t.d];
  }
  function render() {
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    if (!level) return;
    g.lineCap = 'round'; g.lineJoin = 'round';
    const op = opening, ease = 1 - Math.pow(1 - op, 3);
    // lines
    for (const t of tapes) {
      let rg = lineRange(t); if (!rg) continue;
      if (op < 1) rg = [rg[0], rg[0] + (rg[1] - rg[0]) * ease];
      const w = Math.max(2.2, t.w * cam.s);
      const flash = t.flash > 0;
      strokeRange(t, rg[0], rg[1], w + 2.4, css(mix(t.pal.line, [0, 0, 0], 0.32), 0.9));
      strokeRange(t, rg[0], rg[1], w, flash ? css(mix(t.pal.line, [255, 30, 30], 0.7)) : css(t.pal.line));
      if (w > 4) strokeRange(t, rg[0], rg[1], w * 0.28, css(mix(t.pal.line, [255, 255, 255], 0.45), 0.55));
    }
    // hint / tutorial path highlight
    const ht = hint || tutorialTarget();
    if (ht && ht.t.state === 'idle') {
      const a = 0.35 + 0.25 * Math.sin(time * 6);
      strokeRange(ht.t, 0, ht.t.L, Math.max(2.2, ht.t.w * cam.s) + 8, `rgba(255,255,255,${a})`);
    }
    // balls
    const bs = ease;
    for (const t of tapes) {
      if (t.state === 'gone') continue;
      if (t.state === 'done') {
        const k = 1 - t.doneT / 0.25;
        const p = t.dir > 0 ? endPos(t) : startPos(t);
        drawBall(t, p[0], p[1], farR(t), { scale: 1 + (1 - k) * 0.3, alpha: k });
        continue;
      }
      if (t.state === 'idle') {
        const p = startPos(t), q = endPos(t);
        drawBall(t, p[0], p[1], t.rS, { scale: bs }); drawBall(t, q[0], q[1], t.rE, { scale: bs });
      } else {
        const far = t.dir > 0 ? endPos(t) : startPos(t);
        drawBall(t, far[0], far[1], farR(t));
      }
    }
    // moving balls on top
    for (const t of tapes) {
      if (t.state === 'move' || t.state === 'hit' || t.state === 'return') {
        const m = movingPos(t);
        // trail
        for (let k = 1; k <= 5; k++) {
          const dd = t.d - k * 0.09 * (t.state === 'return' ? -1 : 1);
          if (dd < 0 || dd > t.L) continue;
          const q = at(t, t.dir > 0 ? dd : t.L - dd);
          g.fillStyle = css(mix(t.pal.ball, [255, 255, 255], 0.3), 0.22 * (1 - k / 6));
          g.beginPath(); g.arc(sx(q[0]), sy(q[1]), originR(t) * cam.s * (1 - k * 0.12), 0, 7); g.fill();
        }
        let sc = 1;
        if (t.state === 'hit') sc = 1 - 0.25 * Math.sin(Math.min(1, t.hitT / 0.2) * Math.PI);
        drawBall(t, m[0], m[1], originR(t), { scale: sc });
      }
    }
    // effects
    for (const f of fx) {
      if (f.k === 'ring') {
        const k = f.t / f.dur, r = (0.45 + (3.25 - 0.45) * (1 - Math.pow(1 - k, 2))) * cam.s * 0.35;
        g.strokeStyle = `rgba(255,70,60,${(1 - k) * 0.8})`; g.lineWidth = 0.12 * cam.s * (1 - k * 0.5);
        g.beginPath(); g.arc(sx(f.x), sy(f.y), r, 0, 7); g.stroke();
      } else if (f.k === 'splash') {
        const t = f.t, rev = Math.min(1, t / 0.22), dis = Math.max(0, (t - 0.3) / 0.55);
        const S = f.r * cam.s * 6.5 * (0.6 + 0.4 * rev);
        if (f.img.complete) {
          g.save(); g.translate(sx(f.x), sy(f.y)); g.rotate(f.rot);
          g.globalAlpha = (1 - dis) * 0.95;
          const c = tintSplash(f.img, f.c);
          g.drawImage(c, -S / 2, -S / 2, S, S); g.restore(); g.globalAlpha = 1;
        }
      }
    }
    // hand pointer for hint/tutorial
    if (ht && ht.t.state === 'idle') {
      const p = ht.dir > 0 ? startPos(ht.t) : endPos(ht.t);
      UIHand(sx(p[0]), sy(p[1]));
    } else UIHand(null);
  }
  const splashCache = new Map();
  function tintSplash(img, c) {
    const k = img.src + c.join(',');
    if (splashCache.has(k)) return splashCache.get(k);
    const cv2 = document.createElement('canvas'); cv2.width = img.naturalWidth; cv2.height = img.naturalHeight;
    const x = cv2.getContext('2d'); x.drawImage(img, 0, 0); x.globalCompositeOperation = 'source-in';
    x.fillStyle = css(c); x.fillRect(0, 0, cv2.width, cv2.height);
    splashCache.set(k, cv2); return cv2;
  }
  let handEl = null;
  function UIHand(x, y) {
    if (!handEl) { handEl = document.getElementById('hand'); }
    if (x === null) { handEl.style.display = 'none'; return; }
    handEl.style.display = 'block';
    const b = 1 + 0.12 * Math.sin(time * 7);
    handEl.style.transform = `translate(${x}px,${y}px) scale(${b})`;
  }

  // ---------- input: tap, drag-pan, pinch / wheel zoom ----------
  function bindInput() {
    const pts = new Map(); let downAt = null, moved = false, pinch = null;
    const rel = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener('pointerdown', e => {
      cv.setPointerCapture(e.pointerId); const p = rel(e); pts.set(e.pointerId, p);
      if (pts.size === 1) { downAt = { p, cam: { x: cam.x, y: cam.y } }; moved = false; }
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), s: cam.s, c: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] }; moved = true; }
    });
    cv.addEventListener('pointermove', e => {
      if (!pts.has(e.pointerId)) return; const p = rel(e); pts.set(e.pointerId, p);
      if (pts.size >= 2 && pinch) {
        const [a, b] = [...pts.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        zoomAt(pinch.c[0], pinch.c[1], pinch.s * d / pinch.d);
      } else if (downAt && pts.size === 1) {
        const dx = p[0] - downAt.p[0], dy = p[1] - downAt.p[1];
        if (Math.hypot(dx, dy) > 8) moved = true;
        if (moved && cam.s > cam.fit * 1.02) { cam.x = downAt.cam.x - dx / cam.s; cam.y = downAt.cam.y + dy / cam.s; clampCam(); }
      }
    });
    const up = e => {
      if (!pts.has(e.pointerId)) return;
      const p = rel(e); pts.delete(e.pointerId);
      if (pts.size < 2) pinch = null;
      if (pts.size === 0) {
        if (!moved && downAt) { const h = pick(p[0], p[1]); if (h) tap(h.t, h.dir); }
        downAt = null;
        if (cam.s < cam.fit) { cam.s = cam.fit; clampCam(); }
      }
    };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('wheel', e => { e.preventDefault(); const p = rel(e); zoomAt(p[0], p[1], cam.s * Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  }
  function zoomAt(px, py, s) {
    const x = wx(px), y = wy(py);
    cam.s = Math.max(cam.minS, Math.min(cam.maxS, s));
    cam.x = x - (px - W / 2) / cam.s; cam.y = y + (py - view.top - (H - view.top - view.bottom) / 2) / cam.s;
    clampCam();
  }

  let last = performance.now();
  function loop(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (level) { update(dt); render(); }
    requestAnimationFrame(loop);
  }
  function emit(k, ...a) { if (ev[k]) ev[k](...a); }
  return {
    init, load, resize, setViewInsets, showHint, refill, findHint, progress, summary, ev,
    get hearts() { return hearts; }, get tapes() { return tapes; }, get level() { return level; },
    set frozen(v) { frozen = v; }, get frozen() { return frozen; },
    clear() { level = null; tapes = []; g && g.clearRect(0, 0, cv.width, cv.height); UIHand(null); },
    // test helpers
    _tap: (id, dir) => { const t = tapes.find(u => u.id === id); if (t && t.state === 'idle') tap(t, dir); },
    _routeClear: routeClear,
  };
})();
