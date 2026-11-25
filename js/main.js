'use strict';
(async () => {
  const qs = new URLSearchParams(location.search);
  const SKEY = 'lt_save' + (qs.get('slot') || '');
  const save = Object.assign({ idx: 0, hints: 3, today: 0, day: '', best: 0 }, JSON.parse(localStorage.getItem(SKEY) || '{}'));
  const persist = () => localStorage.setItem(SKEY, JSON.stringify(save));
  const today = new Date().toISOString().slice(0, 10);
  if (save.day !== today) { save.day = today; save.today = 0; persist(); }

  const bar = document.querySelector('#loading .bar i');
  const setLoad = f => bar.style.width = (f * 100) + '%';
  document.querySelector('link[rel=icon]').href = 'assets/icon.png';

  await UI.init(); setLoad(0.15);
  const CFG = await fetch('data/config.json').then(r => r.json()); setLoad(0.25);
  await document.fonts.load('40px BalooDa').catch(() => { });
  const [home, game, score, revive, fail, setting] = await Promise.all([
    UI.load('mainuipanel', 10), UI.load('gameuipanel', 20), UI.load('levelscorepanel', 40), UI.load('reviveuipanel', 45),
    UI.load('gamefailuipanel', 46), UI.load('settinguipanel', 50)]);
  setLoad(0.8);
  for (const p of [score, revive, fail, setting]) { p.el.classList.add('modal'); p.hide(); }
  game.hide();
  Board.init(document.getElementById('board'));
  Sfx.preload(['Sound_ClickTrue', 'Sound_Hit', 'Sound_ClickFalse', 'Sound_roll', 'Sound_Splash01', 'Sound_Splash02', 'Sound_Splash03', 'Sound_Splash04', 'Sound_ClickButton']);

  const DIFF = [null, ['ui.extra.hard', 'Hard', '#ec6362', 'Level_Hard'], ['ui.extra.super_hard', 'Super Hard', '#a63eff', 'Level_Veryhard'], [null, 'Nightmare', '#5a2bd6', 'Level_Veryhard']];
  const order = CFG.order;
  function levelName(i) { // i = 0-based progress index (loops after the list)
    if (i < order.length) return order[i];
    const ls = CFG.loopStart - 1, span = order.length - ls;
    return order[ls + ((i - order.length) % span)];
  }
  const diffOf = name => CFG.diff[name] || 0;
  const diffLabel = d => d ? UI.tr(DIFF[d][0], DIFF[d][1]) : '';
  const btnSound = () => Sfx.play('Sound_ClickButton');
  const toast = (text, ms = 1400) => {
    const t = document.createElement('div'); t.className = 'toast'; t.textContent = text;
    document.getElementById('ui').appendChild(t); setTimeout(() => t.remove(), ms);
  };

  // ---------------- home ----------------
  const H = {
    start: home.q('BasePanel/BottomLayer/btn_StartGame'), lvl: home.find('txt_LevelNumber'), diff: home.find('Difficulty'),
    nodes: [1, 2, 3, 4].map(i => home.find('LevelNode_' + i)),
  };
  for (const n of ['btn_Share', 'btn_SignIn', 'btn_SideBar', 'btn_AddShortCut', 'btn_Collect', 'ignore_GMButton', 'GMShowButton', 'Rank', 'Activity', 'ignore_CoinLayer'])
    home.findAll(n).forEach(x => x.hide());
  home.find('btn_Setting').on(() => { btnSound(); openSettings(false); });
  home.find('btn_Setting').findAll(n => n.name === 'icon_Flame' || n.name === 'txt_Days').forEach(x => x.hide());
  H.start.on(() => { btnSound(); startLevel(save.idx); });
  // daily challenge card (DailyChallengeSchedule: date -> level id)
  const chal = home.find('Challenge');
  const dailyId = (CFG.daily.find(d => d[0] === today) || CFG.daily[(new Date().getDate() + new Date().getMonth() * 31) % CFG.daily.length])[1];
  chal.find('Title').setText('Daily Challenge');
  chal.find('Date').setText(new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
  chal.find('Label').setText(UI.tr('ui.extra.start_challenge', 'Start Challenge'));
  const playDaily = () => { btnSound(); startLevel(-1, 'level' + dailyId); };
  chal.on(playDaily); chal.find('Action').on(playDaily);
  function refreshHome() {
    const n = save.idx;
    H.lvl.setText(String(n + 1));
    const d = diffOf(levelName(n));
    H.diff.setText(diffLabel(d)); if (d) H.diff.txtEl.style.color = DIFF[d][2];
    H.nodes.forEach((node, k) => {
      if (!node) return;
      node.find('Number').setText(String(n + 1 + k));
      const dd = diffOf(levelName(n + k));
      if (k > 0 && dd) node.el.style.filter = dd >= 2 ? 'hue-rotate(230deg) saturate(1.4)' : 'hue-rotate(320deg) saturate(1.3)';
      else node.el.style.filter = '';
    });
  }

  // ---------------- game HUD ----------------
  const G = {
    label: game.find('txt_LevelIndex'), hearts: [1, 2, 3].map(i => game.find('ImageHeart' + i)), heartAnim: game.find('HeartAnimaGroup'),
    fill: game.q('BasePanel/LeftLayer/LevelProgress/Fill'), hint: game.find('btn_PropHint'), setting: game.find('btn_Setting'),
    praise: game.find('txt_VictoryPraise'), startCard: game.find('img_StartCard'), clearCard: game.find('img_ClearCard'),
  };
  for (const n of ['ignore_GMShowButton', 'GmLevelIdentitySafeArea', 'CoinLayer', 'go_Controls']) game.findAll(n).forEach(x => x.hide());
  G.heartAnim.hide();
  game.find('GameplayBackgroundView').hide();
  game.find('LevelHintView').el.style.opacity = 1;
  G.hint.el.style.opacity = 1;
  G.hint.find('img_AdBadge').hide();
  const hintCount = G.hint.find('img_CountBK');
  game.find('TopLayer').find('ImageLevelMask').el.style.pointerEvents = 'none';
  G.setting.on(() => { btnSound(); openSettings(true); });
  G.hint.on(() => {
    btnSound();
    if (!cur || Board.frozen) return;
    if (save.hints <= 0) save.hints = 3; // no ads in the web build: refill for free
    if (Board.showHint()) { save.hints--; persist(); updateHintCount(); }
    else toast('No free move right now');
  });
  function updateHintCount() { hintCount.show(true); hintCount.find('txt_Count').setText(String(save.hints)); }
  function setHearts(n, lost) {
    G.hearts.forEach((h, i) => {
      const on = i < n;
      if (!on && h.active && lost) {
        h.el.classList.remove('heartloss'); void h.el.offsetWidth; h.el.classList.add('heartloss');
        setTimeout(() => { h.hide(); h.el.classList.remove('heartloss'); }, 600);
      } else h.show(on);
    });
  }

  let cur = null, curIdx = 0, revived = false;
  async function startLevel(idx, forced) {
    curIdx = idx;
    const name = forced || (qs.get('level') && idx === save.idx && !cur ? qs.get('level') : levelName(idx));
    let L;
    try { L = await fetch('data/levels/' + name + '.json').then(r => r.json()); }
    catch (e) { if (forced) return startLevel(save.idx); throw e; }
    cur = { name, L, diff: diffOf(name), idx };
    home.hide(); score.hide(); fail.hide(); revive.hide(); setting.hide();
    game.show();
    revived = false;
    const d = cur.diff;
    G.label.setText(idx < 0 ? 'Daily Challenge' : d ? diffLabel(d) : UI.fmt(UI.tr('ui.game.level_index', 'Level {0}'), idx + 1));
    G.label.txtEl.style.color = d ? DIFF[d][2] : '#a0602e';
    setHearts(3); updateHintCount();
    G.fill.setFill(0);
    layoutBoard();
    Board.load(L, { hearts: 3 });
    Sfx.play('Sound_level');
    // start hint card for hard levels
    G.startCard.hide(); G.clearCard.hide();
    const hh = CFG.hints[name];
    if (hh && hh.s && d >= 1) {
      G.startCard.show();
      G.startCard.find('txt_StartHint').setText(UI.fmt(CFG.hintTexts[hh.s[0]] || '', `<color=#FF9500>${hh.s[1].toFixed(2)}</color>`));
      G.startCard.el.classList.add('pop');
      setTimeout(() => G.startCard.hide(), 2200);
    }
    if (L.tut) {
      const msg = { 1: UI.tr('ui.tutorial.tap_remove', 'Tap to Remove'), 2: UI.tr('ui.tutorial.collision_warning', 'Ball collisions cost a life'), 3: UI.tr('ui.tutorial.pinch_zoom', 'Pinch to Zoom') }[L.tut.type];
      if (msg) showPraise(msg, 2600, '#956840');
    }
  }
  function layoutBoard() {
    const s = UI.scale;
    Board.resize();
    Board.setViewInsets(470 * s, 170 * s);
  }
  UI.onResize = () => { if (cur && game.active) layoutBoard(); else Board.resize(); };
  function showPraise(text, ms = 1200, color) {
    G.praise.show(); G.praise.setText(text);
    G.praise.txtEl.style.color = color || '#ea8e45';
    G.praise.el.classList.remove('pop'); void G.praise.el.offsetWidth; G.praise.el.classList.add('pop');
    clearTimeout(showPraise.t); showPraise.t = setTimeout(() => G.praise.hide(), ms);
  }

  Board.ev.onProgress = (n, tot) => G.fill.setFill(tot ? n / tot : 0);
  Board.ev.onHit = (t, h) => setHearts(h, true);
  Board.ev.onHeartsOut = () => setTimeout(openRevive, 350);
  Board.ev.onWin = s => onWin(s);

  // ---------------- win ----------------
  const S = {
    title: score.find('txt_Title'), diff: score.find('txt_Difficulty'), time: score.find('txt_Time'), score: score.find('txt_Score'),
    today: score.find('txt_TodayLevels'), acc: score.find('txt_Accuracy'), rings: score.find('txt_Rings'), hints: score.find('txt_Hints'),
    next: score.find('btn_NextLevel'), home: score.find('btn_Home'), stars: ['spine_StarLeft', 'spine_StarCenter', 'spine_StarRight'].map(n => score.find(n)),
    track: score.find('rect_LevelTrack'),
  };
  S.next.on(() => { btnSound(); startLevel(save.idx); });
  const restartCur = () => startLevel(curIdx, curIdx < 0 ? cur.name : undefined);
  S.home.on(() => { btnSound(); goHome(); });
  const PRAISE = ['ui.score_praise.flawless', 'ui.score_praise.no_mistakes', 'ui.score_praise.nice_move', 'ui.score_praise.sharp_eyes', 'ui.score_praise.clutch_win', 'ui.score_praise.comeback'];
  function onWin(s) {
    if (curIdx >= 0) save.idx = curIdx + 1;
    save.today++; persist();
    Sfx.play('Sound_GameWin');
    const stars = s.hits === 0 ? 3 : s.hits === 1 ? 2 : 1;
    const acc = s.taps ? Math.round(100 * (s.taps - s.hits) / s.taps) : 100;
    const pts = Math.max(100, Math.round(s.tapes * 50 * (1 + (cur.diff || 0) * 0.5) * (0.5 + acc / 200) + Math.max(0, 600 - s.time * 5)));
    const praiseKey = s.hits === 0 ? (s.hints ? PRAISE[2] : PRAISE[0]) : s.heartsLeft === 1 ? PRAISE[4] : PRAISE[3];
    S.title.setText(UI.tr(praiseKey, 'Awesome!'));
    S.diff.setText(cur.diff ? diffLabel(cur.diff) : 'Normal');
    const m = Math.floor(s.time / 60), sec = Math.floor(s.time % 60);
    S.time.setText(`${String(m).padStart(2, '0')}: ${String(sec).padStart(2, '0')}`);
    S.score.setText(String(pts)); S.today.setText(String(save.today));
    S.acc.setText(acc + '%'); S.rings.setText(String(s.tapes)); S.hints.setText(String(s.hints));
    // level track: previous/current/next numbers
    const imgs = ['img_Level0', 'img_Level1', 'img_Level2', 'img_Level3', 'img_Level4'].map(n => S.track.find(n));
    imgs.forEach((im, k) => {
      const li = curIdx - 1 + k; im.show(li >= 0);
      const txt = im.find(n => n.txtEl); if (txt) txt.setText(String(li + 1));
      const dd = diffOf(levelName(Math.max(0, li)));
      im.el.style.backgroundImage = `url("${UI.sprite(dd >= 2 ? 'Level_Veryhard' : dd === 1 ? 'Level_Hard' : 'Level_putong')}")`;
      im.extraTf = k === 1 ? 'scale(1.3)' : '';
    });
    S.track.find('img_PreviousLevel').hide();
    score.find('hlay_Level').show(curIdx >= 0);
    game.hide(); Board.clear();
    score.find('txt_TodayLevelsLabel').setText("Today's Levels");
    score.show(); score.el.classList.add('fadein');
    S.stars.forEach((st, i) => {
      st.el.style.visibility = 'hidden';
      setTimeout(() => {
        st.el.style.visibility = i < stars ? 'visible' : 'hidden';
        if (i < stars && st.spine) { st.spine.play('animation', false); Sfx.play('Sound_star'); }
      }, 350 + i * 320);
    });
    const hh = CFG.hints[cur.name];
    if (hh && hh.c && s.hits === 0) {
      G.clearCard.show(); G.clearCard.find('txt_ClearHint').setText(UI.fmt(CFG.hintTexts[hh.c[0]] || '', `<color=#61BE19>${hh.c[1].toFixed(2)}%</color>`).replace('%%', '%'));
    }
  }

  // ---------------- revive / fail ----------------
  const R = {
    name: revive.find('txt_PropName'), desc: revive.find('txt_PropDescription'), prog: revive.find('go_Progress'), fill: revive.find('img_ProgressFill'),
    marker: revive.find('rect_ProgressMarker'), ptxt: revive.find('txt_Progress'), hearts: [revive.find('HeartLeft'), revive.find('img_PropIcon'), revive.find('HeartRight')],
  };
  revive.find('btn_AdUse').find('Icon').hide();
  revive.find('btn_AdUse').find('FreeText').setText(UI.tr('ui.revive.refill', 'Refill'));
  revive.find('btn_AdUse').on(() => {
    btnSound(); revive.hide(); revived = true;
    Sfx.play('Sound_Resurrection'); Board.refill(3); setHearts(3);
  });
  revive.find('btn_Restart').on(() => { btnSound(); revive.hide(); restartCur(); });
  revive.find('btn_Close').on(() => { btnSound(); revive.hide(); openFail(); });
  function openRevive() {
    const p = Board.progress();
    let key = 'ui.revive.no_more_attempts', showProg = false;
    if (p >= 0.75) { key = 'ui.revive.almost_there'; showProg = true; } else if (p > 0.5) { key = 'ui.revive.keep_going'; showProg = true; }
    R.name.setText(UI.tr(key, 'No more attempts'));
    R.desc.setText(UI.tr('ui.revive.refill_free', 'Refill your lives and keep playing!'));
    R.prog.show(showProg); R.hearts.forEach(h => h.show(!showProg));
    if (showProg) {
      R.fill.d.r[6] = 600 * p; R.marker.d.r[4] = -300 + 600 * p; R.ptxt.setText(Math.round(p * 100) + '%');
    }
    revive.show(); revive.find('BasePanel').el.classList.add('pop');
    Sfx.play('Sound_GameFail');
  }
  const F = { pct: fail.find('txt_ProgressText'), player: fail.find('rect_Player') };
  fail.find('btn_BackHome').on(() => { btnSound(); fail.hide(); goHome(); });
  fail.find('btn_Retry').on(() => { btnSound(); fail.hide(); restartCur(); });
  fail.find('titleBanner').setImage({ sp: 'FailUI_Title_En', c: [1, 1, 1, 1] });
  function openFail() {
    const p = Board.progress();
    F.pct.setText((p * 100).toFixed(2) + '%');
    F.player.d.r[4] = -366 + (388 + 366) * p;
    fail.show(); fail.el.classList.add('fadein');
    Sfx.play('Sound_Boo');
  }

  // ---------------- settings ----------------
  setting.find('LanguageRow').hide();
  setting.find('GMShowButton').hide();
  const toggles = { btn_Music: 'music', btn_Sound: 'sound', btn_Vibrate: 'vibe' };
  function refreshToggles() {
    for (const [n, k] of Object.entries(toggles)) {
      const b = setting.find(n); b.find('Open').show(!!Sfx.S[k]); b.find('OffVisual').show(!Sfx.S[k]);
    }
  }
  for (const [n, k] of Object.entries(toggles)) setting.find(n).on(() => {
    Sfx.S[k] = !Sfx.S[k]; Sfx.apply(); btnSound(); refreshToggles();
    if (k === 'music') Sfx.bgm(Sfx.S.music);
  });
  setting.find('btn_Close').on(() => { btnSound(); setting.hide(); if (cur) Board.frozen = settingFrozen; });
  setting.find('btn_BackHome').on(() => { btnSound(); setting.hide(); goHome(); });
  setting.find('btn_Reset').on(() => { btnSound(); setting.hide(); if (cur) restartCur(); });
  let settingFrozen = false;
  function openSettings(inGame) {
    refreshToggles();
    setting.find('go_GameBtnGroup').show(inGame);
    if (inGame) { settingFrozen = Board.frozen; Board.frozen = true; }
    setting.show(); setting.find('BasePanel').el.classList.add('pop');
  }

  function goHome() {
    cur = null; Board.clear(); game.hide(); score.hide(); refreshHome(); home.show();
  }

  refreshHome();
  setLoad(1);
  const ld = document.getElementById('loading'); ld.style.opacity = 0; setTimeout(() => ld.remove(), 450);
  addEventListener('pointerdown', () => Sfx.bgm(true), { once: true });
  if (qs.get('level') || qs.get('play')) startLevel(save.idx);
  window.LT = { Board, startLevel, save, CFG, levelName };
})();
