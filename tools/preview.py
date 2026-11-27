# render level json files to png thumbnails / a contact sheet
# python tools/preview.py out.png level1 new3 ...      (or "new*" for every generated level)
import json, os, sys, glob, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.join(os.path.dirname(__file__), '..')
PAL = {'blue1': (0, 136, 255), 'blue2': (1, 0, 178), 'brown1': (109, 40, 40), 'gray1': (126, 126, 126), 'green1': (27, 172, 0),
       'green2': (18, 113, 0), 'orange1': (232, 140, 8), 'pink1': (241, 93, 110), 'purple1': (104, 0, 199), 'red1': (219, 41, 28), 'yellow1': (213, 175, 8)}
LINE = {'blue1': (83, 172, 196), 'blue2': (16, 46, 175), 'brown1': (120, 42, 20), 'gray1': (147, 147, 147), 'green1': (102, 163, 3), 'green2': (13, 101, 0),
        'orange1': (222, 170, 0), 'pink1': (193, 124, 168), 'purple1': (128, 0, 168), 'red1': (200, 56, 56), 'yellow1': (230, 217, 5)}

def sample(segs):
    P = []
    for k, (x0, y0, x1, y1, x2, y2, x3, y3) in enumerate(segs):
        t = np.linspace(0, 1, 9)[(1 if k else 0):]; u = 1 - t
        P.append(np.stack([u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3, u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3], 1))
    return np.concatenate(P)

def render(L, size=360):
    T = [(sample(t['segs']), t) for t in L['tapes']]
    allP = np.concatenate([p for p, _ in T]); x0, y0 = allP.min(0) - 0.35; x1, y1 = allP.max(0) + 0.35
    SS = 3; W = size * SS; sc = W / max(x1 - x0, y1 - y0); ox = (W - (x1 - x0) * sc) / 2; oy = (W - (y1 - y0) * sc) / 2
    im = Image.new('RGB', (W, W), (254, 254, 246)); d = ImageDraw.Draw(im)
    tr = lambda p: (ox + (p[0] - x0) * sc, oy + (y1 - p[1]) * sc)
    for p, t in sorted(T, key=lambda x: -x[1].get('z', 0)):
        pts = [tr(q) for q in p]; w = max(SS * 1.5, t['w'] * 1.4 * sc)
        d.line(pts, fill=tuple(int(c * 0.65) for c in LINE[t['color']]), width=int(w + SS * 1.2), joint='curve'); d.line(pts, fill=LINE[t['color']], width=int(w), joint='curve')
    for p, t in T:
        for q, ev in ((p[0], t['ev']), (p[-1], t['eev'])):
            x, y = tr(q); R = max(SS * 2, 0.2 * ev * sc); c = PAL[t['color']]
            d.ellipse((x - R + R * .25, y - R + R * .3, x + R + R * .25, y + R + R * .3), fill=(225, 222, 205))
            d.ellipse((x - R, y - R, x + R, y + R), fill=c, outline=tuple(int(v * .5) for v in c), width=max(1, SS))
            d.ellipse((x - R * .55, y - R * .6, x - R * .1, y - R * .25), fill=tuple(min(255, v + 110) for v in c))
    return im.resize((size, size), Image.LANCZOS)

if __name__ == '__main__':
    out = sys.argv[1]; names = []
    for a in sys.argv[2:]:
        names += sorted([os.path.basename(f)[:-5] for f in glob.glob(f'{ROOT}/data/levels/{a}.json')], key=lambda s: int(''.join(c for c in s if c.isdigit()) or 0))
    C = 5; S = 300
    sheet = Image.new('RGB', (C * S, ((len(names) + C - 1) // C) * (S + 28)), (245, 244, 233)); d = ImageDraw.Draw(sheet)
    try: F = ImageFont.truetype(ROOT + '/assets/fonts/BalooDa-Regular.ttf', 18)
    except Exception: F = ImageFont.load_default()
    for i, n in enumerate(names):
        L = json.load(open(f'{ROOT}/data/levels/{n}.json'))
        x, y = (i % C) * S, (i // C) * (S + 28)
        sheet.paste(render(L, S - 10), (x + 5, y + 5))
        d.text((x + 8, y + S - 2), f"{n} {L.get('gen', {}).get('shape', '')} · {len(L['tapes'])} tapes", fill=(70, 50, 30), font=F)
    sheet.save(out)
