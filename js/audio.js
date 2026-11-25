'use strict';
const Sfx = (() => {
  let ctx = null, master = null, sfxGain = null, bgmGain = null;
  const buf = {}, pending = {};
  const S = { sound: true, music: true, vibe: true };
  try { Object.assign(S, JSON.parse(localStorage.getItem('lt_audio') || '{}')); } catch (e) { }
  let bgmSrc = null, rollSrc = null, rollCount = 0;
  function ensure() {
    if (ctx) return ctx;
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return null;
    ctx = new AC(); master = ctx.createGain(); master.connect(ctx.destination);
    sfxGain = ctx.createGain(); sfxGain.connect(master); bgmGain = ctx.createGain(); bgmGain.gain.value = 0.45; bgmGain.connect(master);
    apply();
    return ctx;
  }
  function load(name) {
    if (buf[name]) return Promise.resolve(buf[name]);
    if (pending[name]) return pending[name];
    if (!ensure()) return Promise.resolve(null);
    return pending[name] = fetch('assets/audio/' + name + '.mp3').then(r => r.arrayBuffer())
      .then(a => new Promise((res, rej) => ctx.decodeAudioData(a, res, rej))).then(b => (buf[name] = b)).catch(() => null);
  }
  function play(name, { vol = 1, rate = 1 } = {}) {
    if (!S.sound || !ensure()) return;
    load(name).then(b => {
      if (!b) return;
      const s = ctx.createBufferSource(); s.buffer = b; s.playbackRate.value = rate;
      const g = ctx.createGain(); g.gain.value = vol; s.connect(g); g.connect(sfxGain); s.start();
    });
  }
  function bgm(on = true) {
    if (!ensure()) return;
    if (!on || !S.music) { if (bgmSrc) { bgmSrc.stop(); bgmSrc = null; } return; }
    if (bgmSrc) return;
    load('BGMMain').then(b => {
      if (!b || bgmSrc || !S.music) return;
      bgmSrc = ctx.createBufferSource(); bgmSrc.buffer = b; bgmSrc.loop = true; bgmSrc.connect(bgmGain); bgmSrc.start();
    });
  }
  // looping roll sound while any ball moves
  function roll(delta, rate = 1) {
    rollCount = Math.max(0, rollCount + delta);
    if (!ensure()) return;
    if (rollCount > 0 && !rollSrc && S.sound) {
      load('Sound_roll').then(b => {
        if (!b || rollSrc || rollCount === 0) return;
        rollSrc = ctx.createBufferSource(); rollSrc.buffer = b; rollSrc.loop = true; rollSrc.playbackRate.value = rate;
        const g = ctx.createGain(); g.gain.value = 0.55; rollSrc.connect(g); g.connect(sfxGain); rollSrc.start();
      });
    } else if (rollCount === 0 && rollSrc) { rollSrc.stop(); rollSrc = null; }
  }
  function apply() {
    localStorage.setItem('lt_audio', JSON.stringify(S));
    if (sfxGain) sfxGain.gain.value = S.sound ? 1 : 0;
    if (ctx && !S.music) bgm(false);
  }
  function vibrate(ms) { if (S.vibe && navigator.vibrate && (!navigator.userActivation || navigator.userActivation.hasBeenActive)) try { navigator.vibrate(ms); } catch (e) { } }
  function unlock() { if (ensure() && ctx.state === 'suspended') ctx.resume(); }
  ['pointerdown', 'touchend', 'keydown'].forEach(ev => addEventListener(ev, unlock, { passive: true }));
  return { play, bgm, roll, vibrate, S, apply, preload: n => n.forEach(load) };
})();
