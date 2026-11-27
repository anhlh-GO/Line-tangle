# Give every existing level new tape colours: each tape gets a colour different from its old one, and tapes
# whose balls touch / sit on each other get different colours. Original colours are kept in "color0".
import json, os, glob, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
ROOT = os.path.join(os.path.dirname(__file__), '..')
COLORS = ['blue1', 'blue2', 'brown1', 'gray1', 'green1', 'green2', 'orange1', 'pink1', 'purple1', 'red1', 'yellow1']

def sample(segs):
    P = []
    for k, (x0, y0, x1, y1, x2, y2, x3, y3) in enumerate(segs):
        t = np.linspace(0, 1, 9)[(1 if k else 0):]; u = 1 - t
        P.append(np.stack([u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3, u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3], 1))
    return np.concatenate(P)

n_lv = n_tp = 0
for f in sorted(glob.glob(ROOT + '/data/levels/*.json')):
    name = os.path.basename(f)[:-5]
    if name.startswith('new'): continue
    L = json.load(open(f)); T = L['tapes']
    if any('color0' in t for t in T): continue          # already recoloured
    P = [sample(t['segs']) for t in T]
    nb = [set() for _ in T]
    for i in range(len(T)):
        for j in range(len(T)):
            if i == j: continue
            for c in (P[j][0], P[j][-1]):
                if np.min(np.hypot(*(P[i] - c).T)) < 0.6: nb[i].add(j); nb[j].add(i); break
    rng = random.Random(name)
    # shift the palette as a whole (keeps the level's colour balance), then repair conflicts
    perm = COLORS[:];
    while True:
        rng.shuffle(perm)
        if all(a != b for a, b in zip(COLORS, perm)): break
    mp = dict(zip(COLORS, perm))
    new = [mp.get(t['color'], rng.choice(COLORS)) for t in T]
    for _ in range(3):
        for i in sorted(range(len(T)), key=lambda i: -len(nb[i])):
            bad = {new[j] for j in nb[i]} | {T[i]['color']}
            if new[i] in bad:
                opts = [c for c in COLORS if c not in bad] or [c for c in COLORS if c != T[i]['color']]
                new[i] = rng.choice(opts)
    for t, c in zip(T, new):
        t['color0'] = t['color']; t['color'] = c; t['cid'] = COLORS.index(c)
    json.dump(L, open(f, 'w'), separators=(',', ':'))
    n_lv += 1; n_tp += len(T)
print('recoloured levels', n_lv, 'tapes', n_tp)
