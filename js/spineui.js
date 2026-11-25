// SkeletonGraphic replacement: spine-canvas 4.0 skeleton drawn into a canvas inside a UI node.
'use strict';
const SpineUI = (() => {
  const am = new spine.AssetManager('assets/spine/');
  const cache = {};
  const live = new Set();
  function loadData(sk) {
    const base = sk.replace(/_SkeletonData$/, '');
    if (cache[base]) return cache[base];
    am.loadBinary(base + '.skel'); am.loadTextureAtlas(base + '.atlas');
    cache[base] = new Promise((res, rej) => {
      const t = setInterval(() => {
        if (!am.isLoadingComplete()) return;
        clearInterval(t);
        try {
          const atlas = am.require(base + '.atlas');
          const bin = new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas));
          res(bin.readSkeletonData(am.require(base + '.skel')));
        } catch (e) { console.warn('spine', base, e); rej(e); }
      }, 30);
    });
    return cache[base];
  }
  class Inst {
    constructor(node, cfg) {
      this.node = node; this.cfg = cfg; this.pad = 2.2;
      const cv = this.cv = document.createElement('canvas');
      cv.className = 'spinecv';
      node.el.appendChild(cv);
      this.ctx = cv.getContext('2d');
      this.renderer = new spine.SkeletonRenderer(this.ctx); this.renderer.triangleRendering = true;
      this.ready = loadData(cfg.sk).then(data => {
        this.data = data;
        this.skel = new spine.Skeleton(data);
        if (cfg.skin && data.findSkin(cfg.skin)) this.skel.setSkinByName(cfg.skin);
        this.skel.setToSetupPose();
        this.state = new spine.AnimationState(new spine.AnimationStateData(data));
        if (cfg.anim) this.play(cfg.anim, !!cfg.loop);
        this.resize();
        return this;
      }).catch(() => null);
      live.add(this);
    }
    play(name, loop = false, onDone) {
      if (!this.state) { this.ready.then(() => this.play(name, loop, onDone)); return; }
      if (!this.data.findAnimation(name)) { const a = this.data.animations[0]; if (!a) return; name = a.name; }
      this.skel.setToSetupPose();
      const e = this.state.setAnimation(0, name, loop);
      this.t0 = performance.now();
      if (onDone) e.listener = { complete: () => onDone() };
      return e;
    }
    anims() { return this.data ? this.data.animations.map(a => a.name) : []; }
    resize() {
      const n = this.node, w = Math.max(n.w || 100, 10), h = Math.max(n.h || 100, 10);
      const S = Math.max(w, h) * this.pad;
      const res = Math.min(2, (UI.scale || 1) * devicePixelRatio);
      this.cv.width = Math.ceil(S * res); this.cv.height = Math.ceil(S * res);
      this.cv.style.width = S + 'px'; this.cv.style.height = S + 'px';
      const pv = n.d.r ? [n.d.r[8], n.d.r[9]] : [0.5, 0.5];
      this.cv.style.left = (w * pv[0] - S / 2) + 'px'; this.cv.style.top = (h * (1 - pv[1]) - S / 2) + 'px';
      this.S = S; this.res = res;
    }
    draw(dt) {
      if (!this.skel || !this.node.el.isConnected || this.node.el.offsetParent === null) return;
      this.state.update(dt); this.state.apply(this.skel);
      this.skel.updateWorldTransform();
      const c = this.ctx, S = this.S, r = this.res;
      c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.cv.width, this.cv.height);
      c.setTransform(r, 0, 0, -r, S / 2 * r, S / 2 * r);
      const col = this.cfg.c; this.skel.color.set(col[0], col[1], col[2], col[3]);
      this.renderer.draw(this.skel);
    }
  }
  let last = performance.now();
  function tick(now) {
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    for (const s of live) s.draw(dt);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  return { attach: (node, cfg) => cfg.sk ? new Inst(node, cfg) : null };
})();
