// Greedy solver over exported levels using the same blocking rule as js/board.js.
// usage: node tools/solve.mjs [levelName ...]   -> prints unsolvable levels
import fs from 'fs';
const dir = new URL('../data/levels/', import.meta.url);
const BALL_R = 0.2, SWEEP = 0.2, SKIN = +(process.env.SKIN || 0.1), SCALE = +(process.env.RS || 1);
function sample(segs) {
  const P = [];
  segs.forEach(([x0, y0, x1, y1, x2, y2, x3, y3], k) => {
    const len = Math.hypot(x1 - x0, y1 - y0) + Math.hypot(x2 - x1, y2 - y1) + Math.hypot(x3 - x2, y3 - y2);
    const n = Math.max(4, Math.ceil(len / 0.03));
    for (let i = k ? 1 : 0; i <= n; i++) { const t = i / n, u = 1 - t; P.push([u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3, u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3]); }
  });
  return P;
}
function solve(L) {
  const T = L.tapes.map(d => ({ id: d.id, P: sample(d.segs), rS: BALL_R * (d.ev || 1) * SCALE, rE: BALL_R * (d.eev || 1) * SCALE, gone: false }));
  const clear = (t, dir) => {
    const obs = [];
    for (const u of T) if (u !== t && !u.gone) { obs.push([...u.P[0], u.rS]); obs.push([...u.P[u.P.length - 1], u.rE]); }
    const rm = SWEEP * ((dir > 0 ? t.rS : t.rE) / BALL_R);
    const pts = dir > 0 ? t.P : [...t.P].reverse();
    for (const p of pts) for (const o of obs) { const lim = rm + o[2] - SKIN; if ((p[0] - o[0]) ** 2 + (p[1] - o[1]) ** 2 < lim * lim) return false; }
    return true;
  };
  const seq = [];
  for (; ;) {
    let found = null;
    for (const t of T) if (!t.gone) { for (const d of [1, -1]) if (clear(t, d)) { found = [t, d]; break; } if (found) break; }
    if (!found) break;
    found[0].gone = true; seq.push(found[0].id + (found[1] > 0 ? '+' : '-'));
  }
  const left = T.filter(t => !t.gone);
  return { ok: !left.length, left: left.map(t => t.id), seq, first: T.length };
}
const names = process.argv.slice(2).length ? process.argv.slice(2) : fs.readdirSync(dir).map(f => f.replace('.json', ''));
let bad = 0;
for (const n of names) {
  const L = JSON.parse(fs.readFileSync(new URL(n + '.json', dir)));
  const r = solve(L);
  if (!r.ok) { bad++; console.log('STUCK', n, 'tapes', r.first, 'left', r.left.length, r.left.slice(0, 6).join(',')); }
}
console.log('checked', names.length, 'stuck', bad);
