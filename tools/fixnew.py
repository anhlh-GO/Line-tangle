# Make every generated level pass the exact in-game rule: sample the exported bezier segments the same way
# tools/solve.mjs / js/board.js do, break any deadlock by pulling back blocking ball ends, re-export, repeat.
# Updates docs/levels/new_report.json "got" with the final exact metrics.
import json, os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import genlevels as G
ROOT = G.ROOT

def dense(segs):
    P = []
    for k, (x0, y0, x1, y1, x2, y2, x3, y3) in enumerate(segs):
        ln = np.hypot(x1 - x0, y1 - y0) + np.hypot(x2 - x1, y2 - y1) + np.hypot(x3 - x2, y3 - y2)
        n = max(4, int(np.ceil(ln / 0.03))); t = np.arange(1 if k else 0, n + 1) / n; u = 1 - t
        P.append(np.stack([u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3, u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3], 1))
    return np.concatenate(P)

rp = ROOT + '/docs/levels/new_report.json'; rep = json.load(open(rp))
byname = {e['name']: k for k, e in rep.items()}
names = sys.argv[1:] or sorted(byname, key=lambda s: int(s[3:]))
for nm in names:
    f = f'{ROOT}/data/levels/{nm}.json'; L = json.load(open(f))
    tapes = [{'p': dense(t['segs']), 'ev': t['ev'], 'eev': t['eev']} for t in L['tapes']]
    fixed = 0
    for it in range(4):
        b = G.real_check(tapes); m = G.metrics(b)
        if m: break
        before = [len(t['p']) for t in tapes]
        b = G.repair(tapes, steps=3 * len(tapes))
        fixed += sum(1 for t, n in zip(tapes, before) if len(t['p']) != n)
        for t, d in zip(tapes, L['tapes']): d['segs'] = G.to_segs(t['p'])
        tapes = [{'p': dense(t['segs']), 'ev': t['ev'], 'eev': t['eev']} for t in L['tapes']]
    b = G.real_check(tapes); m = G.metrics(b)
    json.dump(L, open(f, 'w'), separators=(',', ':'))
    e = rep[byname[nm]]; tgt = tuple(e['target'])
    if m: e['got'] = list(m)
    e['exact'] = bool(m); e['within'] = bool(m and G.within(m, tgt))
    print(nm, 'target', tgt, 'exact', m, 'within' if e['within'] else 'OFF', 'ends pulled', fixed, flush=True)
json.dump(rep, open(rp, 'w'), indent=0)
