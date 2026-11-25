# per-level stats (blocker graph, solve depth, crossings, features) + level images
# python tools/levelstats.py <outdir>   -> outdir/stats.json, outdir/img/<level>.png, outdir/sheets/main_XX.png
import json, os, sys, math, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = sys.argv[1]; os.makedirs(OUT + '/img', exist_ok=True); os.makedirs(OUT + '/sheets', exist_ok=True)
CFG = json.load(open(ROOT + '/data/config.json', encoding='utf8'))
BALL_R, SWEEP, SKIN = 0.2, 0.2, 0.1
PAL = {'blue1': (0, 136, 255), 'blue2': (1, 0, 178), 'brown1': (109, 40, 40), 'gray1': (126, 126, 126), 'green1': (27, 172, 0),
       'green2': (18, 113, 0), 'orange1': (232, 140, 8), 'pink1': (241, 93, 110), 'purple1': (104, 0, 199), 'red1': (219, 41, 28), 'yellow1': (213, 175, 8)}
LINE = {'blue1': (83, 172, 196), 'blue2': (16, 46, 175), 'brown1': (120, 42, 20), 'gray1': (147, 147, 147), 'green1': (102, 163, 3), 'green2': (13, 101, 0),
        'orange1': (222, 170, 0), 'pink1': (193, 124, 168), 'purple1': (128, 0, 168), 'red1': (200, 56, 56), 'yellow1': (230, 217, 5)}
DIFF = ['Normal', 'Hard', 'Super Hard', 'Nightmare']
TUT = {1: 'Tap to remove', 2: 'Collision costs a life', 3: 'Pinch to zoom'}

def sample(segs):
    P = []
    for k, (x0, y0, x1, y1, x2, y2, x3, y3) in enumerate(segs):
        n = max(4, math.ceil((math.hypot(x1 - x0, y1 - y0) + math.hypot(x2 - x1, y2 - y1) + math.hypot(x3 - x2, y3 - y2)) / 0.03))
        t = np.linspace(0, 1, n + 1)[(1 if k else 0):]; u = 1 - t
        P.append(np.stack([u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3, u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3], 1))
    return np.concatenate(P)

def seg_cross(A, B):
    # count proper intersections between polylines A and B (downsampled)
    a = A[::3]; b = B[::3]
    if len(a) < 2 or len(b) < 2: return 0
    p, r = a[:-1], a[1:] - a[:-1]; q, s = b[:-1], b[1:] - b[:-1]
    # bbox prefilter
    amin, amax = np.minimum(a[:-1], a[1:]), np.maximum(a[:-1], a[1:]); bmin, bmax = np.minimum(b[:-1], b[1:]), np.maximum(b[:-1], b[1:])
    ov = (amin[:, None, 0] <= bmax[None, :, 0]) & (bmin[None, :, 0] <= amax[:, None, 0]) & (amin[:, None, 1] <= bmax[None, :, 1]) & (bmin[None, :, 1] <= amax[:, None, 1])
    I, J = np.nonzero(ov)
    if not len(I): return 0
    rr, ss, qp = r[I], s[J], q[J] - p[I]
    den = rr[:, 0] * ss[:, 1] - rr[:, 1] * ss[:, 0]
    ok = np.abs(den) > 1e-12
    t = np.where(ok, (qp[:, 0] * ss[:, 1] - qp[:, 1] * ss[:, 0]) / np.where(ok, den, 1), -1)
    w = np.where(ok, (qp[:, 0] * rr[:, 1] - qp[:, 1] * rr[:, 0]) / np.where(ok, den, 1), -1)
    hit = ok & (t >= 0) & (t < 1) & (w >= 0) & (w < 1)
    return int(hit.sum())

def analyse(name):
    L = json.load(open(f'{ROOT}/data/levels/{name}.json'))
    T = []
    for d in L['tapes']:
        P = sample(d['segs']); seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        T.append({'id': d['id'], 'P': P, 'len': float(seg.sum()), 'rS': BALL_R * d['ev'], 'rE': BALL_R * d['eev'], 'color': d['color'], 'ev': d['ev'], 'eev': d['eev'], 'w': d['w'], 'enc': d['enc'], 'z': d['z']})
    n = len(T)
    balls = [(i, T[i]['P'][0], T[i]['rS']) for i in range(n)] + [(i, T[i]['P'][-1], T[i]['rE']) for i in range(n)]
    # blockers[i][dir] = set of tapes whose balls sit on route of tape i in that direction; graze = near misses
    block = [[set(), set()] for _ in range(n)]; graze = 0
    for i, t in enumerate(T):
        for di, r0 in ((0, t['rS']), (1, t['rE'])):
            rm = SWEEP * r0 / BALL_R
            for j, c, r in balls:
                if j == i: continue
                dist = np.min(np.hypot(t['P'][:, 0] - c[0], t['P'][:, 1] - c[1]))
                pen = rm + r - dist
                if pen > SKIN: block[i][di].add(j)
                elif pen > 0 and di == 0: graze += 1
    # a tape is free when one direction is clear; peel in rounds
    gone = set(); rounds = [];
    while len(gone) < n:
        free = [i for i in range(n) if i not in gone and any(not (b - gone) for b in block[i])]
        if not free: break
        rounds.append(free); gone |= set(free)
    solvable = len(gone) == n
    edges = sum(min(len(block[i][0]), len(block[i][1])) for i in range(n))   # blockers on the easier side
    pairs = set()
    for i in range(n):
        for b in block[i][0] | block[i][1]: pairs.add((i, b))
    both = sum(1 for i in range(n) if block[i][0] and block[i][1])
    mx = max((min(len(block[i][0]), len(block[i][1])) for i in range(n)), default=0)
    cross = 0
    for i in range(n):
        for j in range(i + 1, n): cross += seg_cross(T[i]['P'], T[j]['P'])
    allP = np.concatenate([t['P'] for t in T]); x0, y0 = allP.min(0); x1, y1 = allP.max(0)
    feats = []
    if L.get('tut'): feats.append('Tutorial: ' + TUT.get(L['tut']['type'], str(L['tut']['type'])))
    big = sum(1 for t in T if t['ev'] > 1 or t['eev'] > 1); small = sum(1 for t in T if t['ev'] < 1 or t['eev'] < 1)
    if big: feats.append(f'Big balls x{big}')
    if small: feats.append(f'Small balls x{small}')
    if any(t['enc'] for t in T): feats.append('Praise path')
    if len({round(t['z'], 2) for t in T}) > 3: feats.append('Layered depth')
    widths = sorted({t['w'] for t in T})
    return {'name': name, 'tapes': n, 'colors': len({t['color'] for t in T}), 'colorList': sorted({t['color'] for t in T}),
            'pathLen': round(sum(t['len'] for t in T), 1), 'avgLen': round(sum(t['len'] for t in T) / n, 2), 'longest': round(max(t['len'] for t in T), 2),
            'free0': len(rounds[0]) if rounds else 0, 'rounds': len(rounds), 'roundSizes': [len(r) for r in rounds], 'edges': edges, 'pairs': len(pairs),
            'blockedBoth': both, 'maxBlockers': mx, 'graze': graze, 'crossings': cross, 'w': round((x1 - x0), 2), 'h': round((y1 - y0), 2),
            'lineWidth': widths, 'solvable': solvable, 'features': feats, 'tut': L.get('tut'),
            '_T': T, '_rounds': rounds}

def render(s, size=360, label=True):
    T = s['_T']; allP = np.concatenate([t['P'] for t in T]); x0, y0 = allP.min(0) - 0.35; x1, y1 = allP.max(0) + 0.35
    SS = 3; W = size * SS; sc = W / max(x1 - x0, y1 - y0); ox = (W - (x1 - x0) * sc) / 2; oy = (W - (y1 - y0) * sc) / 2
    im = Image.new('RGB', (W, W), (254, 254, 246)); d = ImageDraw.Draw(im)
    tr = lambda p: (ox + (p[0] - x0) * sc, oy + (y1 - p[1]) * sc)
    order = sorted(range(len(T)), key=lambda i: -T[i]['z'])
    for i in order:
        t = T[i]; pts = [tr(p) for p in t['P'][::2]] + [tr(t['P'][-1])]; w = max(SS * 1.5, t['w'] * 1.4 * sc)
        dark = tuple(int(c * 0.65) for c in LINE[t['color']])
        d.line(pts, fill=dark, width=int(w + SS * 1.2), joint='curve'); d.line(pts, fill=LINE[t['color']], width=int(w), joint='curve')
    for i in order:
        t = T[i]
        for p, r in ((t['P'][0], t['rS']), (t['P'][-1], t['rE'])):
            x, y = tr(p); R = max(SS * 2, r * sc)
            d.ellipse((x - R + R * .25, y - R + R * .3, x + R + R * .25, y + R + R * .3), fill=(225, 222, 205))
            d.ellipse((x - R, y - R, x + R, y + R), fill=PAL[t['color']], outline=tuple(int(c * .5) for c in PAL[t['color']]), width=max(1, SS))
            d.ellipse((x - R * .55, y - R * .6, x - R * .1, y - R * .25), fill=tuple(min(255, c + 110) for c in PAL[t['color']]))
    return im.resize((size, size), Image.LANCZOS)

try: FONT = ImageFont.truetype(ROOT + '/assets/fonts/BalooDa-Regular.ttf', 22); FS = ImageFont.truetype(ROOT + '/assets/fonts/BalooDa-Regular.ttf', 15)
except Exception: FONT = FS = ImageFont.load_default()

names = sorted([os.path.basename(f)[:-5] for f in glob.glob(ROOT + '/data/levels/*.json')], key=lambda s: int(''.join(c for c in s if c.isdigit())))
order = CFG['order']; pos = {}
for i, a in enumerate(order): pos.setdefault(a, i + 1)
daily = {}
for dte, lid in CFG['daily']: daily.setdefault('level%d' % lid, []).append(dte)
stats = {}
for nm in names:
    s = analyse(nm); render(s).save(f'{OUT}/img/{nm}.png')
    s['diff'] = CFG['diff'].get(nm, 0); s['order'] = pos.get(nm); s['daily'] = daily.get(nm, [])
    s['startHint'] = CFG['hints'].get(nm, {}).get('s'); s['clearHint'] = CFG['hints'].get(nm, {}).get('c')
    s.pop('_T'); s.pop('_rounds'); stats[nm] = s
    if not s['solvable']: print('UNSOLVABLE', nm)
json.dump(stats, open(OUT + '/stats.json', 'w'), indent=0)
# gallery sheets: main order, 20 per sheet (5 x 4)
DC = [(150, 110, 60), (236, 99, 98), (166, 62, 255), (90, 43, 214)]
for k in range(0, len(order), 20):
    sheet = Image.new('RGB', (5 * 300, 4 * 352), (245, 244, 233)); d = ImageDraw.Draw(sheet)
    for j, nm in enumerate(order[k:k + 20]):
        s = stats[nm]; cx, cy = (j % 5) * 300, (j // 5) * 352
        sheet.paste(Image.open(f'{OUT}/img/{nm}.png').resize((290, 290), Image.LANCZOS), (cx + 5, cy + 5))
        d.text((cx + 10, cy + 298), f'#{k + j + 1}  {nm}', fill=(70, 50, 30), font=FONT)
        d.text((cx + 10, cy + 324), f"{DIFF[s['diff']]} · {s['tapes']} tapes · {s['edges']} blockers · {s['rounds']} rounds", fill=DC[s['diff']], font=FS)
    sheet.save(f'{OUT}/sheets/main_{k // 20 + 1:02d}.png', optimize=True)
print('levels', len(stats), 'main', len(order))
