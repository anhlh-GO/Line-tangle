// Unity uGUI prefab (exported JSON) -> DOM. Reference resolution 1080 wide.
'use strict';
const UI = (() => {
  const REF_W = 1080;
  let SP = {}, I18N = {}, root = null, refH = 1920;
  const tintCache = new Map();

  function tr(term, fallback) {
    const t = I18N[term];
    if (!t) return fallback;
    return t.en || t.zh || fallback;
  }
  function fmt(s, ...a) { return String(s).replace(/\{(\d)\}/g, (_, i) => a[+i]); }
  function rgba(c) { return `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${c[3]})`; }
  function spriteUrl(name) { const s = SP[name]; return s ? 'assets/sp/' + encodeURIComponent(s.f) : null; }

  // sprite multiplied by a colour (Unity Image.color) -> cached data URL
  function tinted(name, c) {
    const key = name + '|' + c.join(',');
    if (tintCache.has(key)) return tintCache.get(key);
    const p = new Promise(res => {
      const img = new Image();
      img.onload = () => {
        const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
        const g = cv.getContext('2d');
        g.drawImage(img, 0, 0);
        g.globalCompositeOperation = 'multiply';
        g.fillStyle = rgba([c[0], c[1], c[2], 1]); g.fillRect(0, 0, cv.width, cv.height);
        g.globalCompositeOperation = 'destination-in';
        g.drawImage(img, 0, 0);
        res(cv.toDataURL());
      };
      img.onerror = () => res(spriteUrl(name));
      img.src = spriteUrl(name);
    });
    tintCache.set(key, p);
    return p;
  }

  function richText(s) {
    const esc = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return esc
      .replace(/&lt;color=(#?[0-9A-Za-z]+)&gt;/g, (_, c) => `<span style="color:${c}">`)
      .replace(/&lt;\/color&gt;/g, '</span>')
      .replace(/&lt;size=(\d+)&gt;/g, (_, z) => `<span style="font-size:${z}px">`)
      .replace(/&lt;\/size&gt;/g, '</span>')
      .replace(/&lt;b&gt;/g, '<b>').replace(/&lt;\/b&gt;/g, '</b>')
      .replace(/\n/g, '<br>');
  }

  const ALIGN = [['flex-start', 'left', 'flex-start'], ['center', 'center', 'flex-start'], ['flex-end', 'right', 'flex-start'],
    ['flex-start', 'left', 'center'], ['center', 'center', 'center'], ['flex-end', 'right', 'center'],
    ['flex-start', 'left', 'flex-end'], ['center', 'center', 'flex-end'], ['flex-end', 'right', 'flex-end']];

  class Node {
    constructor(d, parent) {
      this.d = d; this.parent = parent; this.name = d.n; this.children = [];
      const el = this.el = document.createElement('div');
      el.className = 'u';
      el.dataset.n = d.n;
      this.active = !d.off;
      if (d.alpha !== undefined && d.alpha < 1) el.style.opacity = d.alpha;
      if (d.img) this.setImage(d.img);
      if (d.txt) this.makeText(d.txt);
      if (d.btn) el.classList.add('btn');
      if (d.mask) el.style.overflow = 'hidden';
      if (d.lay) el.classList.add('lay-' + d.lay.k);
      for (const c of d.ch || []) {
        const n = new Node(c, this); this.children.push(n); el.appendChild(n.el);
      }
      if (d.spine && typeof SpineUI !== 'undefined') this.spine = SpineUI.attach(this, d.spine);
      this.applyActive();
    }
    applyActive() { this.el.style.display = this.active ? '' : 'none'; }
    show(v = true) { this.active = v; this.applyActive(); if (v) this.layout(); return this; }
    hide() { return this.show(false); }
    setImage(im) {
      const el = this.el;
      this.img = im;
      if (im.sp && SP[im.sp]) {
        const s = SP[im.sp];
        const white = im.c[0] > 0.99 && im.c[1] > 0.99 && im.c[2] > 0.99;
        const apply = url => {
          if (im.type === 1 && s.b.some(v => v > 0)) {
            const m = im.ppum || 1;
            el.style.borderStyle = 'solid';
            el.style.borderWidth = `${s.b[3] / m}px ${s.b[2] / m}px ${s.b[1] / m}px ${s.b[0] / m}px`;
            el.style.borderImage = `url("${url}") ${s.b[3]} ${s.b[2]} ${s.b[1]} ${s.b[0]} fill stretch`;
            el.style.boxSizing = 'border-box';
            el.style.backgroundImage = '';
          } else {
            el.style.backgroundImage = `url("${url}")`;
            el.style.backgroundSize = im.pa ? 'contain' : '100% 100%';
            el.style.backgroundPosition = 'center';
            el.style.backgroundRepeat = 'no-repeat';
          }
        };
        if (white) apply(spriteUrl(im.sp)); else tinted(im.sp, im.c).then(apply);
        if (im.c[3] < 1) el.style.opacity = (this.d.alpha ?? 1) * im.c[3];
        if (im.type === 3) this.setFill(im.fa ?? 1);
      } else if (!im.sp) {
        if (im.c[3] > 0) el.style.backgroundColor = rgba(im.c);
      }
    }
    setFill(f) {
      const im = this.img; if (!im) return;
      f = Math.max(0, Math.min(1, f));
      im.fa = f;
      if (im.fm === 0) this.el.style.clipPath = im.fo === 1 ? `inset(0 0 0 ${(1 - f) * 100}%)` : `inset(0 ${(1 - f) * 100}% 0 0)`;
      else if (im.fm === 1) this.el.style.clipPath = `inset(${(1 - f) * 100}% 0 0 0)`;
      else this.el.style.clipPath = `inset(0 ${(1 - f) * 100}% 0 0)`;
    }
    makeText(t) {
      const sp = this.txtEl = document.createElement('span');
      sp.className = 'utxt';
      const a = ALIGN[t.al] || ALIGN[4];
      this.el.style.display = 'flex';
      this.el.style.justifyContent = a[0];
      this.el.style.alignItems = a[2];
      sp.style.textAlign = a[1];
      sp.style.fontSize = t.fs + 'px';
      sp.style.lineHeight = (t.ls || 1) * 1.15;
      sp.style.color = rgba(t.c);
      if (t.st === 1 || t.st === 3) sp.style.fontWeight = 'bold';
      const shadows = [];
      for (const [cls, fx] of this.d.fx || []) {
        const c = fx.m_EffectColor, dd = fx.m_EffectDistance;
        if (!c || !dd) continue;
        const col = rgba([c.r, c.g, c.b, c.a]);
        if (cls === 'Shadow') shadows.push(`${dd.x}px ${-dd.y}px 0 ${col}`);
        else {
          const w = Math.max(Math.abs(dd.x), Math.abs(dd.y));
          for (let k = 0; k < 16; k++) {
            const an = k / 16 * Math.PI * 2;
            shadows.push(`${(Math.cos(an) * w).toFixed(1)}px ${(Math.sin(an) * w).toFixed(1)}px 0 ${col}`);
          }
        }
      }
      if (shadows.length) sp.style.textShadow = shadows.join(',');
      this.el.appendChild(sp);
      let s = t.s;
      if (this.d.loc && this.d.loc !== '-') {
        const L = I18N[this.d.loc];
        if (L && L.t === 0) s = L.en || s;
      }
      this.setText(s);
    }
    setText(s) {
      if (!this.txtEl) { const t = this.find(n => n.txtEl); if (t) t.setText(s); return this; }
      this.text = s;
      this.txtEl.innerHTML = richText(String(s));
      if (this.d.txt && this.d.txt.bf) this.fitPending = true;
      return this;
    }
    find(pred) {
      if (typeof pred === 'string') { const nm = pred; pred = n => n.name === nm; }
      for (const c of this.children) { if (pred(c)) return c; const r = c.find(pred); if (r) return r; }
      return null;
    }
    findAll(pred, out = []) {
      if (typeof pred === 'string') { const nm = pred; pred = n => n.name === nm; }
      for (const c of this.children) { if (pred(c)) out.push(c); c.findAll(pred, out); }
      return out;
    }
    q(path) { // 'A/B/C'
      let n = this;
      for (const p of path.split('/')) { n = n.children.find(c => c.name === p) || n.find(p); if (!n) return null; }
      return n;
    }
    on(fn) { this.el.addEventListener('click', e => { e.stopPropagation(); fn(e); }); this.el.classList.add('btn'); return this; }
    // compute rect relative to parent of size (pw,ph)
    layout(pw, ph) {
      if (pw === undefined) { const p = this.parent; pw = p ? p.w : REF_W; ph = p ? p.h : refH; }
      const r = this.d.r, el = this.el;
      let x0 = 0, y0 = 0, w = pw, h = ph;
      if (r && !this.flexItem) {
        const [ax0, ay0, ax1, ay1, px, py, sx, sy, pvx, pvy] = r;
        const ox0 = px - sx * pvx, oy0 = py - sy * pvy, ox1 = px + sx * (1 - pvx), oy1 = py + sy * (1 - pvy);
        const X0 = ax0 * pw + ox0, X1 = ax1 * pw + ox1, Y0 = ay0 * ph + oy0, Y1 = ay1 * ph + oy1;
        x0 = X0; w = X1 - X0; h = Y1 - Y0; y0 = ph - Y1;
        el.style.left = x0 + 'px'; el.style.top = y0 + 'px';
        el.style.transformOrigin = `${pvx * 100}% ${(1 - pvy) * 100}%`;
      } else if (r && this.flexItem) {
        const [, , , , , , sx, sy] = r; w = sx; h = sy;
      }
      this.w = w; this.h = h;
      if (!this.txtEl || !this.flexItem) { el.style.width = Math.max(0, w) + 'px'; el.style.height = Math.max(0, h) + 'px'; }
      const tf = [];
      if (this.d.s) tf.push(`scale(${this.d.s[0]},${this.d.s[1]})`);
      if (this.d.rot) tf.push(`rotate(${-this.d.rot}deg)`);
      if (this.extraTf) tf.push(this.extraTf);
      el.style.transform = tf.join(' ');
      const lay = this.d.lay;
      for (const c of this.children) {
        c.flexItem = !!(lay && lay.k !== 'G' && !(c.d.le && c.d.le.m_IgnoreLayout));
        if (c.active) c.layout(w, h);
      }
      if (lay && lay.k === 'G' && lay.cs) {
        const kids = this.children.filter(c => c.active), cw = lay.cs.x, ch = lay.cs.y, gx = (lay.sp && lay.sp.x) || 0;
        const tot = kids.length * cw + Math.max(0, kids.length - 1) * gx;
        kids.forEach((c, i) => {
          c.el.style.left = ((w - tot) / 2 + i * (cw + gx)) + 'px'; c.el.style.top = ((h - ch) / 2) + 'px';
          c.el.style.width = cw + 'px'; c.el.style.height = ch + 'px'; c.w = cw; c.h = ch;
          for (const k of c.children) if (k.active) k.layout(cw, ch);
        });
      }
      if (lay && lay.k !== 'G') {
        el.style.display = this.active ? 'flex' : 'none';
        el.style.flexDirection = lay.k === 'H' ? 'row' : 'column';
        el.style.gap = (lay.sp || 0) + 'px';
        const al = ALIGN[lay.al] || ALIGN[4];
        el.style.justifyContent = lay.k === 'H' ? al[0] : al[2];
        el.style.alignItems = lay.k === 'H' ? al[2] : al[0];
        el.style.padding = `${lay.pad[2]}px ${lay.pad[1]}px ${lay.pad[3]}px ${lay.pad[0]}px`;
        el.style.boxSizing = 'border-box';
        for (const c of this.children) if (c.flexItem) {
          c.el.style.position = 'relative'; c.el.style.left = ''; c.el.style.top = ''; c.el.style.flex = 'none';
          if (c.txtEl && (lay.cw || lay.ch)) { c.el.style.width = 'auto'; c.el.style.height = 'auto'; c.txtEl.style.whiteSpace = 'pre'; }
        }
      }
      if (this.spine) this.spine.resize();
    }
  }

  async function init() {
    [SP, I18N] = await Promise.all([fetch('data/sprites.json').then(r => r.json()), fetch('data/i18n.json').then(r => r.json())]);
    root = document.getElementById('ui');
    resize();
    window.addEventListener('resize', resize);
  }
  const panels = [];
  function resize() {
    const app = document.getElementById('app');
    const W = innerWidth, H = innerHeight;
    const aw = Math.min(W, H * 0.62), ah = H;
    app.style.width = aw + 'px'; app.style.height = ah + 'px';
    const s = aw / REF_W; refH = ah / s;
    root.style.transform = `scale(${s})`; root.style.width = REF_W + 'px'; root.style.height = refH + 'px';
    UI.scale = s; UI.refH = refH; UI.appW = aw; UI.appH = ah;
    for (const p of panels) if (p.active) p.layout(REF_W, refH);
    if (UI.onResize) UI.onResize();
  }
  async function load(name, z = 10) {
    const d = await fetch('data/ui/' + name + '.json').then(r => r.json());
    const size = x => 1 + (x.ch || []).reduce((a, c) => a + size(c), 0);
    const rootD = d.reduce((a, b) => size(b) > size(a) ? b : a, d[0]);
    const n = new Node(rootD, null);
    n.el.classList.add('panel'); n.el.style.zIndex = z;
    root.appendChild(n.el);
    n.layout(REF_W, refH);
    panels.push(n);
    const show = n.show.bind(n);
    n.show = (v = true) => { show(v); if (v) n.layout(REF_W, refH); return n; };
    return n;
  }
  function sprite(name) { return spriteUrl(name); }
  return { init, load, tr, fmt, sprite, get SP() { return SP; }, resize, REF_W };
})();
