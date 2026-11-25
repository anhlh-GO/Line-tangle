# Line Tangle: Untangle Puzzle — HTML5 port

Web port of the Android game *Line Tangle* (`line.tangle.twist.away.puzzle` 1.1130), rebuilt from the xapk's own assets:
587 levels (Unity Addressables), UI prefabs, sprites, Spine animations, sounds and fonts.

Run: `node "../.claude/serve.mjs" . 8850` then open http://localhost:8850 (launch config `line-tangle`).

## Rules (from the IL2CPP metadata + level data)
Each tape is a spline with a ball at both ends. Tap a ball: it rolls along its own tape to the other end, eating the line.
If another tape's ball sits on the route the ball bounces back and you lose a heart (3 per level).
Contacts that only graze (< 0.1 world units overlap) do not block — with that rule every level is solvable
(`node tools/solve.mjs`).

Level order = scheme 4 ("C") from `LevelSchemes`, 400 levels, looping from level 22; difficulty from `LevelConfig`.

## Layout
- `index.html`, `css/`, `js/` — `ui.js` (Unity uGUI prefab JSON -> DOM), `spineui.js` (spine-canvas 4.0), `board.js` (gameplay), `audio.js`, `main.js` (flow)
- `data/levels/*.json` — world-space bezier segments per tape; `data/ui/*.json` — prefabs; `data/config.json`, `data/i18n.json`, `data/sprites.json`
- `assets/` — sprites (`sp/`), spine, audio (mp3), fonts; `vendor/spine-canvas.min.js`
- `tools/` — exporters (UnityPy): `exlevels.py`, `exui.py`, `exsprites.py`, `exmedia.py`; IL2CPP v31 helpers (`elfreg.py`, `meta31.py`, `methods31.py`, `doc.py`); `solve.mjs`

URL params: `?level=level50` (play a given level), `?slot=x` (separate save slot), `?play=1`.
