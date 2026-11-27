# Recognisable line drawings for generated levels. Each shape(k) returns a list of strokes (Nx2 arrays,
# a closed stroke repeats its first point). k = detail level (more hatch lines / rays / petals).
import numpy as np

def _dens(pts, step=0.05):
    pts = np.asarray(pts, float)
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.ceil(np.hypot(*(b - a)) / step)))
        for i in range(1, n + 1): out.append(a + (b - a) * i / n)
    return np.array(out)

def P(*pts): return _dens(pts)
def L(a, b): return _dens([a, b])

def S(*pts, closed=False):
    """Catmull-Rom spline through pts."""
    p = np.asarray(pts, float)
    if closed: p = np.vstack([p[-1], p, p[0], p[1]])
    else: p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        n = max(2, int(np.hypot(*(p2 - p1)) / 0.05))
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(p[-2])
    return _dens(out)

def arc(c, r, a0, a1, ry=None, rot=0):
    ry = r if ry is None else ry
    n = max(8, int(abs(a1 - a0) / 360 * 2 * np.pi * max(r, ry) / 0.05))
    t = np.radians(np.linspace(a0, a1, n))
    x, y = r * np.cos(t), ry * np.sin(t)
    cr, sr = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    return np.stack([c[0] + x * cr - y * sr, c[1] + x * sr + y * cr], 1)

def circ(c, r, ry=None, rot=0, start=90): return arc(c, r, start, start + 360, ry, rot)

def rect(x0, y0, x1, y1): return P((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))

def poly(*pts): return P(*pts, pts[0])

# interior style, set by the generator per level: 'straight' | 'wave' | 'bow' | 'swirl'
STYLE = {'mode': 'wave', 'amp': 0.28, 'lam': 3.2, 'phase': 0.0, 'bow': 0.45}

def _curvy(a, b, d, nrm, spacing):
    """chord a->b bent according to STYLE; ends stay on the outline"""
    m = STYLE['mode'] if STYLE.get('_n', 0) <= 1 else 'bow'; n = max(8, int(np.hypot(*(b - a)) / 0.05))
    t = np.linspace(0, 1, n + 1)
    base = a[None, :] + (b - a)[None, :] * t[:, None]
    if m == 'straight': return base
    taper = np.sin(np.pi * t) ** 0.6
    x = base @ d
    if m == 'wave':
        off = STYLE['amp'] * spacing * np.sin(2 * np.pi * x / STYLE['lam'] + STYLE['phase']) * taper
    elif m == 'bow':
        off = STYLE['bow'] * spacing * np.sin(np.pi * t) * (0.6 if STYLE.get('_n', 0) > 1 else 1)
    else:  # swirl: wave whose amplitude grows towards one side
        off = STYLE['amp'] * spacing * 1.0 * np.sin(2 * np.pi * x / (STYLE['lam'] * 0.8) + STYLE['phase']) * taper * (0.4 + 0.6 * t)
    return base + nrm[None, :] * off[:, None]

def hatch(outline, angle, n, inset=0.0, lo=0.0, hi=1.0):
    """n chords clipped to closed outline (curved per STYLE); each ends on the outline."""
    o = np.asarray(outline, float)
    STYLE['_n'] = STYLE.get('_n', 0) + 1
    angle = angle + STYLE.get('tilt', 0)
    d = np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))]); nrm = np.array([-d[1], d[0]])
    proj = o @ nrm; pmin, pmax = proj.min(), proj.max()
    spacing = (pmax - pmin) * (hi - lo) / (n + 1) if n else 1
    res = []
    for i in range(n):
        f = lo + (hi - lo) * (i + 1) / (n + 1)
        c = pmin + (pmax - pmin) * f
        hits = []
        for a, b in zip(o[:-1], o[1:]):
            pa, pb = a @ nrm - c, b @ nrm - c
            if (pa < 0) != (pb < 0):
                t = pa / (pa - pb); q = a + (b - a) * t; hits.append(q)
        hits.sort(key=lambda q: q @ d)
        for j in range(0, len(hits) - 1, 2):
            a, b = hits[j], hits[j + 1]
            if np.hypot(*(b - a)) > 1.0 + 2 * inset:
                if inset: a, b = a + d * inset, b - d * inset
                res.append(_curvy(a, b, d, nrm, spacing))
    return res

def curl(p, ang, r=0.7, turns=1.3, sign=1):
    """small spiral curl starting at p heading ang"""
    t = np.linspace(0, 1, int(turns * 2 * np.pi * r / 0.05) + 2)
    a = np.radians(ang) - sign * np.pi / 2 + sign * t * turns * 2 * np.pi
    rr = r * (1 - 0.65 * t)
    c = np.asarray(p, float) + r * np.array([np.cos(np.radians(ang) + sign * np.pi / 2), np.sin(np.radians(ang) + sign * np.pi / 2)])
    return np.stack([c[0] + rr * np.cos(a), c[1] + rr * np.sin(a)], 1)

def ray_to(outline, p, ang):
    """segment from p in direction ang until it meets the closed outline"""
    o = np.asarray(outline, float); p = np.asarray(p, float); d = np.array([np.cos(np.radians(ang)), np.sin(np.radians(ang))])
    best = None
    for a, b in zip(o[:-1], o[1:]):
        e = b - a; den = d[0] * -e[1] - d[1] * -e[0]
        if abs(den) < 1e-9: continue
        w = a - p; t = (w[0] * -e[1] - w[1] * -e[0]) / den; u = (d[0] * w[1] - d[1] * w[0]) / den
        if t > 0.2 and 0 <= u <= 1 and (best is None or t < best): best = t
    return L(p, p + d * best) if best else None

def rays(c, r0, r1, n, a0=90, jitter=0):
    return [L((c[0] + r0 * np.cos(np.radians(a)), c[1] + r0 * np.sin(np.radians(a))), (c[0] + r1 * np.cos(np.radians(a)), c[1] + r1 * np.sin(np.radians(a))))
            for a in np.linspace(a0, a0 + 360, n, endpoint=False)]

def spiral(c, r0, r1, turns, a0=0):
    t = np.linspace(0, 1, int(turns * 2 * np.pi * r1 / 0.05))
    a = np.radians(a0) + t * turns * 2 * np.pi; r = r0 + (r1 - r0) * t
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], 1)

def zig(a, b, n, amp):
    a, b = np.asarray(a, float), np.asarray(b, float); d = b - a; nr = np.array([-d[1], d[0]]) / np.hypot(*d)
    return P(*[a + d * i / n + nr * (amp if i % 2 else -amp) * (0 < i < n) for i in range(n + 1)])

def wave(a, b, n, amp):
    a, b = np.asarray(a, float), np.asarray(b, float); d = b - a; nr = np.array([-d[1], d[0]]) / np.hypot(*d)
    pts = [a + d * i / (2 * n) + nr * (amp * (1 if i % 4 == 1 else -1 if i % 4 == 3 else 0)) for i in range(2 * n + 1)]
    return S(*pts)

# ------------------------------------------------------------------ shapes
SH = {}
def shape(f):
    def w(k):
        STYLE['_n'] = 0
        return f(k)
    w.__name__ = f.__name__; SH[f.__name__] = w; return w

@shape
def smiley(k):
    s = [L((-1.6, 0.9), (-1.6, 2.3)), L((1.6, 0.9), (1.6, 2.3)), arc((0, 0.6), 2.6, 205, 335)]
    if k > 0:
        face = circ((0, 0.3), 4.2); s.append(face)
        if k > 1: s += [arc((0, 0.3), 3.4, 30, 150)] + hatch(circ((0, 0.3), 4.2), 90, k - 1, lo=0.0, hi=0.25)
    return s

@shape
def umbrella(k):
    top = arc((0, 0), 5, 0, 180)
    scal = [arc((-5 + 1.25 * (2 * i + 1) * 2 / 2, 0), 1.25, 180, 360, 0.6) for i in range(4)]
    s = [top] + scal + [S((0, 5), (0, 0), (0, -4.5), (0.7, -5.4), (1.4, -4.6))]
    s += [S((0, 5), (x * 0.45, 2.5), (x, 0)) for x in (-2.5, 2.5)]
    s += hatch(np.vstack([top, top[:1]]), 0, k)
    return s

@shape
def house(k):
    s = [rect(-4, -4, 4, 1.5), poly((-5, 1.5), (0, 6), (5, 1.5)), rect(-1, -4, 1, -0.6), rect(-3.4, -2.6, -1.8, -0.6), rect(1.8, -2.6, 3.4, -0.6),
         P((2.6, 3.9), (2.6, 6.5), (3.6, 6.5), (3.6, 3.0))]
    s += [L((-2.6, -2.6), (-2.6, -0.6)), L((2.6, -2.6), (2.6, -0.6))]
    s += hatch(poly((-5, 1.5), (0, 6), (5, 1.5)), 0, k // 2 + 1) + hatch(rect(-4, -4, 4, 1.5), 90, k // 2, lo=0.0, hi=0.15)
    return s

@shape
def heart(k):
    h = S((0, -4.5), (-3.2, -1.2), (-4.4, 1.6), (-3.2, 3.6), (-1.2, 3.6), (0, 2.2), (1.2, 3.6), (3.2, 3.6), (4.4, 1.6), (3.2, -1.2), (0, -4.5))
    return [h] + hatch(h, 45, k) + (hatch(h, -45, k // 2) if k > 4 else [])

@shape
def star(k):
    pts = [(np.cos(np.radians(90 + 36 * i)) * (5 if i % 2 == 0 else 2.1), np.sin(np.radians(90 + 36 * i)) * (5 if i % 2 == 0 else 2.1)) for i in range(10)]
    o = poly(*pts)
    s = [o] + [L(pts[i], (0, 0)) for i in range(0, 10, 2)]
    if k > 0: s += [circ((0, 0), 1.1)]
    s += hatch(o, 0, k)
    return s

@shape
def fish(k):
    body = S((-4, 0), (-1.5, 2.6), (2, 2.2), (4.4, 0), (2, -2.2), (-1.5, -2.6), (-4, 0))
    tail = P((-4, 0), (-6.3, 2.2), (-6.3, -2.2), (-4, 0))
    s = [body, tail, circ((2.6, 0.6), 0.45), arc((1.2, 0), 2.3, -60, 60), S((0, 2.4), (-0.5, 3.6), (-2, 3.9), (-2.4, 2.5))]
    s += hatch(body, 75, k)
    return s

@shape
def pine(k):
    s = [P((-1, -6), (-1, -4.5)), P((1, -6), (1, -4.5)), L((-1, -6), (1, -6))]
    tiers = [((-5, -4.5), (0, -0.5), (5, -4.5)), ((-4, -1.5), (0, 2.3), (4, -1.5)), ((-3, 1.2), (0, 5.5), (3, 1.2))]
    for a, b, c in tiers: s.append(P(c, a, b, c))
    s += [L((0, -0.5), (0, -4.5)), L((0, 2.3), (0, -1.5))]
    for i, (a, b, c) in enumerate(tiers):
        s += hatch(poly(a, b, c), 0, max(0, (k - i) // 2))
    return s

@shape
def apple(k):
    body = S((0, 2.8), (-2.2, 3.6), (-4.2, 1.6), (-4, -2), (-2, -4.6), (0, -4), (2, -4.6), (4, -2), (4.2, 1.6), (2.2, 3.6), (0, 2.8))
    leaf = S((0.3, 4.2), (1.6, 5.6), (3.4, 5.4), (2.2, 4.0), (0.3, 4.2))
    s = [body, S((0, 2.8), (0.2, 4.2), (-0.4, 5.6)), leaf, L((0.6, 4.4), (2.7, 5.2)), arc((-1.8, 0.8), 1.6, 110, 200)]
    s += hatch(body, 90, k)
    return s

@shape
def mug(k):
    body = P((-3.5, 3.5), (-3.5, -3.2), (-2.6, -4.2), (2.6, -4.2), (3.5, -3.2), (3.5, 3.5), (-3.5, 3.5))
    s = [body, S((3.5, 2.4), (5.6, 2.2), (5.8, -1.2), (3.5, -2.2)), S((3.5, 1.2), (4.6, 1.0), (4.6, -0.6), (3.5, -1.0))]
    s += [S((-1.5, 4.2), (-1.0, 5.0), (-1.6, 5.8), (-1.0, 6.6)), S((1, 4.2), (1.5, 5.0), (0.9, 5.8), (1.5, 6.6))]
    s += hatch(body, 90, k) + hatch(body, 0, k // 3)
    return s

@shape
def balloons(k):
    s = []
    for (cx, cy, r) in ((-2.4, 2.2, 2.2), (2.4, 2.8, 2.3), (0, 4.6, 2.0)):
        b = circ((cx, cy), r, r * 1.2); s.append(b); s += hatch(b, 30, k // 3)
    s += [S((-2.4, -0.4), (-1.2, -3), (0, -6)), S((2.4, 0.0), (1.2, -3), (0, -6)), S((0, 2.2), (0.4, -2), (0, -6))]
    return s

@shape
def sailboat(k):
    hull = P((-5, -1.5), (5, -1.5), (3.6, -3.6), (-3.6, -3.6), (-5, -1.5))
    s1 = poly((-0.3, -1.0), (-0.3, 6), (-4.5, -1.0)); s2 = poly((0.4, 0), (0.4, 5.2), (3.8, 0))
    s = [hull, L((0, -1.5), (0, 6.6)), s1, s2, wave((-6, -4.6), (6, -4.6), 4, 0.5)]
    s += hatch(s1, 0, k // 2) + hatch(s2, 0, k // 2) + hatch(hull, 90, k // 3)
    return s

@shape
def rocket(k):
    body = S((0, 6.5), (-1.9, 3.5), (-2, -2.5), (2, -2.5), (2, 3.5), (0, 6.5))
    s = [body, circ((0, 2), 0.9), P((-2, -0.5), (-3.6, -3.5), (-2, -2.5)), P((2, -0.5), (3.6, -3.5), (2, -2.5)),
         S((-1.2, -2.5), (-0.6, -4.6), (0, -3.6), (0.6, -4.6), (1.2, -2.5)), L((-1.95, 4.2), (1.95, 4.2))]
    s += hatch(body, 0, k)
    return s

@shape
def flower(k):
    n = 6 + k // 3
    s = [circ((0, 2), 1.2)]
    for i in range(n):
        a = 90 + 360 * i / n
        s.append(circ((np.cos(np.radians(a)) * 2.5, 2 + np.sin(np.radians(a)) * 2.5), 1.35, 0.85, rot=a))
    s += [S((0, 0.8), (0.3, -2), (0, -6)), S((0.1, -3), (2, -2.2), (3.2, -2.8), (2, -3.8), (0.1, -3.6)), S((0.05, -4.4), (-2, -3.6), (-3.2, -4.2), (-2, -5.2), (0, -5.0))]
    s += hatch(circ((0, 2), 1.2), 0, min(2, k // 4))
    return s

@shape
def butterfly(k):
    s = [S((0, 3.2), (0.3, 0), (0, -3.6)), np.vstack([S((0.1, 3), (-0.8, 4.6), (-1.6, 5.4)), curl((-1.6, 5.4), 125, 0.55, sign=1)[1:]]),
         np.vstack([S((0.1, 3), (1.0, 4.6), (1.8, 5.4)), curl((1.8, 5.4), 55, 0.55, sign=-1)[1:]])]
    wings = [S((0.1, 1.5), (-2.5, 4.5), (-5, 3.6), (-4.4, 0.5), (0.1, 0.2), closed=False),
             S((0.1, 1.5), (2.7, 4.5), (5.2, 3.6), (4.6, 0.5), (0.2, 0.2)),
             S((0.1, -0.4), (-3.6, -0.8), (-4, -3.4), (-1.4, -3.6), (0.0, -1.6)),
             S((0.2, -0.4), (3.8, -0.8), (4.2, -3.4), (1.6, -3.6), (0.2, -1.6))]
    s += wings + [circ((-2.6, 2.2), 0.8), circ((2.8, 2.2), 0.8)]
    for w in wings: s += hatch(np.vstack([w, w[:1]]), 60, k // 4)
    return s

@shape
def icecream(k):
    cone = P((-3, 0), (0, -7), (3, 0), (-3, 0))
    s = [cone, S((-3, 0), (-3.6, 1.6), (-1.6, 3.0), (0, 2.4), (1.6, 3.0), (3.6, 1.6), (3, 0)), S((-1.6, 3.0), (-1.2, 4.8), (0.6, 5.4), (1.6, 3.0)),
         circ((0.4, 6.2), 0.6)]
    s += hatch(cone, 60, k // 2 + 1) + hatch(cone, -60, k // 2 + 1)
    return s

@shape
def mushroom(k):
    cap = S((-5, 0.5), (-4.4, 3.6), (0, 5.6), (4.4, 3.6), (5, 0.5))
    s = [cap, L((-5, 0.5), (5, 0.5)), S((-1.4, 0.5), (-1.8, -3), (-1.4, -5), (1.4, -5), (1.8, -3), (1.4, 0.5)),
         circ((-2.4, 2.8), 0.7), circ((1.2, 3.8), 0.8), circ((2.9, 2.0), 0.55)]
    s += hatch(np.vstack([cap, cap[:1]]), 90, k // 2) + hatch(P((-1.4, 0.5), (-1.8, -3), (-1.4, -5), (1.4, -5), (1.8, -3), (1.4, 0.5), (-1.4, 0.5)), 0, k // 3)
    return s

@shape
def crown(k):
    o = P((-5, -2), (-5, 3), (-2.6, 0.6), (0, 4.4), (2.6, 0.6), (5, 3), (5, -2), (-5, -2))
    s = [o, L((-5, -0.6), (5, -0.6)), circ((-5, 3.6), 0.5), circ((0, 5.0), 0.55), circ((5, 3.6), 0.5), circ((-2.5, -1.3), 0.45), circ((2.5, -1.3), 0.45)]
    s += hatch(o, 90, k)
    return s

@shape
def key(k):
    s = [circ((-3.2, 0), 2.4), circ((-3.2, 0), 1.0), L((-0.8, 0.5), (5.5, 0.5)), L((-0.8, -0.5), (5.5, -0.5)), L((5.5, 0.5), (5.5, -0.5))]
    for i in range(2 + k // 3): x = 4.6 - 1.2 * i; s.append(P((x, -0.5), (x, -2.0), (x - 0.7, -2.0), (x - 0.7, -0.5)))
    s += hatch(circ((-3.2, 0), 2.4), 0, k // 3)
    return s

@shape
def bell(k):
    b = S((-4.5, -2.5), (-3.4, 0), (-3, 3), (-1.6, 4.8), (0, 5.2), (1.6, 4.8), (3, 3), (3.4, 0), (4.5, -2.5))
    s = [b, L((-4.5, -2.5), (4.5, -2.5)), circ((0, -3.4), 0.9), arc((0, 5.6), 0.8, -60, 240), L((-3.6, -1.2), (3.6, -1.2))]
    s += hatch(np.vstack([b, b[:1]]), 0, k)
    return s

@shape
def anchor(k):
    s = [circ((0, 5), 0.9), L((0, 4.1), (0, -4.6)), L((-2.6, 2.6), (2.6, 2.6)), arc((0, -1), 3.6, 200, 340),
         P((-3.6, -1.6), (-4.4, -0.6)), P((3.6, -1.6), (4.4, -0.6)), S((-3.4, -2.2), (-2, -4.2), (0, -4.6), (2, -4.2), (3.4, -2.2))]
    s += [L((-0.9 - 0.6 * i, -3.9 + 0.05 * i), (-0.9 - 0.6 * i, -1.5)) for i in range(k // 3)]
    return s

@shape
def leaf(k):
    o = S((0, -5), (-3.4, -1.6), (-3.2, 2.6), (0, 6), (3.2, 2.6), (3.4, -1.6), (0, -5))
    s = [o, L((0, -6.6), (0, 6))]
    n = max(1, k)
    for i in range(n):
        y = -3.6 + 8.2 * (i + 0.5) / n
        s += [v for v in (ray_to(o, (0, y), 156), ray_to(o, (0, y + 0.45), 24)) if v is not None]
    return s

@shape
def sun(k):
    n = 8 + k
    s = [circ((0, 0), 2.6), circ((0, 0), 1.6)] + rays((0, 0), 2.6, 5, n)
    s += [arc((0, 0), 0.9, 200, 340), circ((-0.6, 0.5), 0.2), circ((0.6, 0.5), 0.2)] if k > 2 else []
    return [x for x in s if len(x) > 3 and np.ptp(x[:, 0]) + np.ptp(x[:, 1]) > 0.5]

@shape
def raincloud(k):
    c = S((-4.5, 0), (-5, 2), (-3, 3.4), (-1.6, 5), (1, 4.8), (2.6, 3.4), (4.6, 3.2), (5, 0.8), (3.6, 0), (-4.5, 0))
    s = [c, L((-4.5, 0), (3.6, 0))]
    for i in range(3 + k // 2):
        x = -3.8 + 7.4 * i / max(1, 2 + k // 2); s.append(L((x, -0.8), (x - 0.8, -3.4)))
    s += hatch(c, 0, k // 3)
    return s

@shape
def bird(k):
    body = S((-3.6, 0), (-1, 2.4), (2.4, 2.2), (4, 0.6), (2.4, -1.8), (-1.4, -2.0), (-3.6, 0))
    s = [body, P((4, 0.8), (5.6, 0.4), (4, 0)), circ((2.6, 0.9), 0.35), S((-1, 1.2), (0.6, 4.2), (2, 4.6), (1.4, 1.6)),
         P((-3.6, 0), (-5.8, 1.2), (-5.4, -0.6), (-3.6, 0)), L((0, -2.0), (0, -3.6)), L((1, -2.0), (1, -3.6)), L((-0.8, -3.6), (1.8, -3.6))]
    s += hatch(body, 80, k)
    return s

@shape
def snowman(k):
    s = [circ((0, -3.5), 3), circ((0, 1.6), 2.2), circ((0, 5.2), 1.5), rect(-1.4, 6.4, 1.4, 8.2), L((-2.2, 6.4), (2.2, 6.4)),
         S((-2.1, 1.8), (-3.6, 2.6), (-4.6, 4.0)), S((2.1, 1.8), (3.6, 2.6), (4.6, 4.0)), L((0, 5.0), (1.3, 4.6))]
    s += hatch(circ((0, -3.5), 3), 90, k // 2) + hatch(circ((0, 1.6), 2.2), 90, k // 3)
    return s

@shape
def bulb(k):
    b = S((-1.6, -1.5), (-2.4, 0.8), (-3.6, 3.2), (-2.6, 5.8), (0, 6.6), (2.6, 5.8), (3.6, 3.2), (2.4, 0.8), (1.6, -1.5))
    s = [b, P((-1.6, -1.5), (-1.6, -3.8), (1.6, -3.8), (1.6, -1.5)), L((-1.6, -1.5), (1.6, -1.5)), zig((-1.4, 1.2), (1.4, 1.2), 4, 0.6),
         L((-1.0, -1.5), (-1.4, 1.2)), L((1.0, -1.5), (1.4, 1.2))]
    s += [L((-1.6, -2.3 - 0.5 * i), (1.6, -2.3 - 0.5 * i)) for i in range(min(3, 1 + k // 4))] + hatch(np.vstack([b, b[:1]]), 0, k // 2, lo=0.4)
    return s

@shape
def cupcake(k):
    w = P((-3.6, 0), (-2.6, -4.5), (2.6, -4.5), (3.6, 0), (-3.6, 0))
    s = [w, S((-3.6, 0), (-4.2, 1.6), (-2.6, 2.8), (-1.2, 4.2), (1.4, 4.0), (2.8, 2.8), (4.2, 1.6), (3.6, 0)), S((-2.6, 2.8), (0, 2.2), (2.8, 2.8)),
         circ((0.2, 5), 0.75)]
    s += hatch(w, 90, k) + [S((-0.4, 5.6), (-0.2, 6.4), (0.6, 7.0))]
    return s

@shape
def owl(k):
    body = S((0, 5.4), (-3.6, 3.6), (-4, -1.4), (-2.4, -4.8), (0, -5.2), (2.4, -4.8), (4, -1.4), (3.6, 3.6), (0, 5.4))
    s = [body, circ((-1.6, 2.2), 1.4), circ((1.6, 2.2), 1.4), circ((-1.6, 2.2), 0.5), circ((1.6, 2.2), 0.5), P((-0.5, 0.6), (0, -0.4), (0.5, 0.6)),
         P((-2.6, 4.4), (-3.4, 6.4), (-1.4, 5.1)), P((2.6, 4.4), (3.4, 6.4), (1.4, 5.1))]
    for i in range(k // 2):
        y = -1.6 - 0.9 * i; s.append(P((-1.4, y), (0, y - 0.6), (1.4, y)))
    return s

@shape
def pear(k):
    b = S((0, 4.4), (-1.2, 3.6), (-1.6, 1.4), (-3.6, -1.6), (-3, -4.4), (0, -5.2), (3, -4.4), (3.6, -1.6), (1.6, 1.4), (1.2, 3.6), (0, 4.4))
    return [b, S((0, 4.4), (0.3, 5.6), (1, 6.4)), S((0.4, 5.2), (2, 6.0), (3, 5.2), (0.4, 5.2))] + hatch(b, 20, k)

@shape
def cherries(k):
    s = [circ((-2.4, -2.5), 2.1), circ((2.4, -2.0), 2.1), S((-2.2, -0.4), (-1.2, 3), (0.6, 5.6)), S((2.2, 0.1), (1.6, 3), (0.6, 5.6)),
         S((0.6, 5.6), (2.4, 6.6), (4, 5.6), (2.2, 5.0), (0.6, 5.6))]
    s += hatch(circ((-2.4, -2.5), 2.1), 45, k // 2) + hatch(circ((2.4, -2.0), 2.1), 45, k // 2)
    return s

@shape
def watermelon(k):
    o = arc((0, 2), 6, 180, 360); i1 = arc((0, 2), 5, 185, 355)
    s = [np.vstack([o, P((6, 2), (-6, 2))[1:]]), i1]
    s += [circ((x, y), 0.3, 0.45) for x, y in ((-2.6, 0), (0, -1.2), (2.6, 0), (-1.2, -0.2), (1.3, -0.4))][: 2 + k // 3]
    s += hatch(np.vstack([o, o[:1]]), 90, k)
    return s

@shape
def pumpkin(k):
    s = [circ((0, -0.5), 2.0, 3.6), circ((-2.4, -0.5), 2.6, 3.4), circ((2.4, -0.5), 2.6, 3.4), P((-0.4, 3.0), (-0.2, 4.8), (0.8, 5.0), (0.6, 3.0)),
         P((-1.6, 0.4), (-0.6, 1.2), (-1.8, 1.4), (-1.6, 0.4)), P((1.6, 0.4), (0.6, 1.2), (1.8, 1.4), (1.6, 0.4)), zig((-2, -1.6), (2, -1.6), 4, 0.4)]
    s += hatch(circ((-2.4, -0.5), 2.6, 3.4), 90, k // 4) + hatch(circ((2.4, -0.5), 2.6, 3.4), 90, k // 4) + [curl((0.8, 5.0), 20, 0.6)]
    return s

@shape
def ghost(k):
    g = S((-3.6, -4.4), (-3.8, 1), (-2.4, 4.4), (0, 5.4), (2.4, 4.4), (3.8, 1), (3.6, -4.4))
    bottom = wave((3.6, -4.4), (-3.6, -4.4), 3, 0.7)
    s = [np.vstack([g, bottom[1:]]), circ((-1.3, 1.8), 0.6, 0.9), circ((1.3, 1.8), 0.6, 0.9), circ((0, -0.6), 0.7, 0.9),
         S((-3.7, -0.6), (-5.4, 0.4), (-5.6, 1.8)), S((3.7, -0.6), (5.4, 0.4), (5.6, 1.8))]
    s += hatch(np.vstack([g, bottom[1:]]), 90, k // 2, lo=0.0, hi=1.0)
    return s

@shape
def gem(k):
    o = poly((-5, 2), (-3, 4.2), (3, 4.2), (5, 2), (0, -5))
    s = [o, L((-5, 2), (5, 2)), P((-3, 4.2), (-1.5, 2), (0, 4.2), (1.5, 2), (3, 4.2)), L((-1.5, 2), (0, -5)), L((1.5, 2), (0, -5))]
    s += hatch(poly((-5, 2), (5, 2), (0, -5)), 0, k)
    return s

@shape
def hourglass(k):
    s = [rect(-3.6, 5, 3.6, 5.8), rect(-3.6, -5.8, 3.6, -5), L((-3, 5), (-3, -5)), L((3, 5), (3, -5)),
         S((-2.4, 5), (-2.2, 2), (-0.3, 0), (-2.2, -2), (-2.4, -5)), S((2.4, 5), (2.2, 2), (0.3, 0), (2.2, -2), (2.4, -5))]
    s += [L((-2.2 + 0.2 * i, -4.4 + 0.9 * i), (2.2 - 0.2 * i, -4.4 + 0.9 * i)) for i in range(min(4, k // 2))]
    return s

@shape
def kite(k):
    o = poly((0, 6), (-3.6, 1.6), (0, -4), (3.6, 1.6))
    s = [o, L((0, 6), (0, -4)), L((-3.6, 1.6), (3.6, 1.6)), S((0, -4), (-1, -5.6), (0.6, -7), (-0.4, -8.6))]
    for y in (-5.4, -7.2): s.append(poly((-0.2, y), (-1.2, y + 0.6), (-1.2, y - 0.6))) if False else None
    s += hatch(o, 45, k // 2) + hatch(o, -45, k // 2)
    return s

@shape
def glasses(k):
    s = [circ((-3.2, 0), 2.4), circ((3.2, 0), 2.4), arc((0, 0.3), 0.9, 20, 160), L((-5.6, 0.6), (-7, 2.2)), L((5.6, 0.6), (7, 2.2))]
    s += hatch(circ((-3.2, 0), 2.4), 60, k // 2) + hatch(circ((3.2, 0), 2.4), 60, k // 2)
    return s

@shape
def envelope(k):
    s = [rect(-5, -3.4, 5, 3.4), P((-5, 3.4), (0, -0.6), (5, 3.4)), L((-5, -3.4), (-1.6, 0.6)), L((5, -3.4), (1.6, 0.6)), circ((0, -0.6), 0.6)]
    s += hatch(rect(-5, -3.4, 5, 3.4), 0, k // 2)
    return s

@shape
def gift(k):
    s = [rect(-4.4, -4.4, 4.4, 1.6), rect(-5, 1.6, 5, 3.4), L((-0.7, -4.4), (-0.7, 3.4)), L((0.7, -4.4), (0.7, 3.4)),
         S((0, 3.4), (-2.2, 5.6), (-3.6, 4.6), (-2, 3.4)), S((0, 3.4), (2.2, 5.6), (3.6, 4.6), (2, 3.4))]
    s += hatch(rect(-4.4, -4.4, 4.4, 1.6), 45, k)
    return s

@shape
def notes(k):
    s = [circ((-3, -3), 1.3, 0.9, rot=20), circ((2.6, -2), 1.3, 0.9, rot=20), L((-1.8, -2.6), (-1.8, 4)), L((3.8, -1.6), (3.8, 5)),
         P((-1.8, 4), (3.8, 5)), P((-1.8, 2.8), (3.8, 3.8))]
    s += [L((-1.8, 1.6 - 0.9 * i), (3.8, 2.6 - 0.9 * i)) for i in range(k // 3)]
    return s

@shape
def rainbow(k):
    n = 3 + k // 2
    s = [arc((0, -2), 6 - 0.9 * i, 0, 180) for i in range(n) if 6 - 0.9 * i > 1.0]
    s += [L((-6, -2), (-6 + 0.9 * (len(s) - 1), -2)), L((6, -2), (6 - 0.9 * (len(s) - 1), -2))]
    s += [S((-7, -2), (-6.6, -0.8), (-5.2, -1.0), (-4.2, -2)), S((7, -2), (6.6, -0.8), (5.2, -1.0), (4.2, -2))]
    return s

@shape
def lollipop(k):
    s = [circ((0, 2.5), 3.6), spiral((0, 2.5), 0.3, 3.0, 2 + k // 4), L((0, -1.1), (0, -7))]
    s += rays((0, 2.5), 3.6, 4.6, k // 2) if k > 3 else []
    return s

@shape
def teapot(k):
    b = S((-3.6, -3), (-4.4, 0), (-3.4, 2.6), (0, 3.4), (3.4, 2.6), (4.4, 0), (3.6, -3), (-3.6, -3))
    s = [b, S((-1.8, 3.2), (0, 4.6), (1.8, 3.2)), circ((0, 5.1), 0.5), S((4.2, 1.4), (6.2, 1.2), (6.0, -1.6), (4.2, -1.8)),
         S((-4.2, 0), (-5.6, 0.6), (-6.6, 2.6)), L((-3.6, -3), (3.6, -3))]
    s += hatch(b, 0, k)
    return s

@shape
def turtle(k):
    shell = S((-4.4, 0), (-3, 3.2), (0, 4.0), (3, 3.2), (4.4, 0), (-4.4, 0))
    s = [shell, L((-4.4, 0), (4.4, 0)), circ((5.6, 0.8), 1.1), P((-3, 0), (-3.6, -1.6), (-2.2, -1.6), (-2, 0)), P((2, 0), (2.2, -1.6), (3.6, -1.6), (3, 0)),
         P((-4.4, 0), (-5.6, -0.4))]
    s += hatch(np.vstack([shell, shell[:1]]), 60, k // 2) + hatch(np.vstack([shell, shell[:1]]), -60, k // 2)
    return s

@shape
def snail(k):
    s = [spiral((0.6, 1.4), 0.4, 3.2, 2.2 + k / 6), S((-4.6, -2.0), (-3, -1.9), (2, -1.9), (4.6, -1.6), (6.4, 0), (6.6, 1.6)),
         L((-4.6, -2.0), (5.6, -2.6)), L((6.0, 1.0), (6.4, 3.2)), L((6.6, 1.0), (7.4, 3.0))]
    s += rays((0.6, 1.4), 0.6, 3.3, k // 2) if k > 1 else []
    return s

@shape
def cactus(k):
    t = P((-1.2, -5), (-1.2, 4.2), (0, 5.4), (1.2, 4.2), (1.2, -5))
    s = [t, L((-1.2, -5), (1.2, -5)), P((-1.2, 0), (-3.4, 0), (-3.4, 3)), P((-1.2, 1.2), (-2.4, 1.2), (-2.4, 3)), L((-3.4, 3), (-2.4, 3)),
         P((1.2, 1.5), (3.2, 1.5), (3.2, 4.4)), P((1.2, 2.6), (2.2, 2.6), (2.2, 4.4)), L((3.2, 4.4), (2.2, 4.4)),
         rect(-2.8, -7, 2.8, -5)]
    s += hatch(P((-1.2, -5), (-1.2, 4.2), (0, 5.4), (1.2, 4.2), (1.2, -5), (-1.2, -5)), 0, k)
    return s

@shape
def bottle(k):
    b = P((-1, 6), (-1, 4), (-2.6, 2), (-2.6, -5), (2.6, -5), (2.6, 2), (1, 4), (1, 6), (-1, 6))
    s = [b, rect(-1.3, 6, 1.3, 7), L((-2.6, -1), (2.6, -1)), L((-2.6, -3.4), (2.6, -3.4))]
    s += hatch(b, 30, k)
    return s

@shape
def shield(k):
    o = S((-4.4, 4.4), (-4.4, 0), (-3, -3.6), (0, -5.6), (3, -3.6), (4.4, 0), (4.4, 4.4))
    o = np.vstack([o, P((4.4, 4.4), (-4.4, 4.4))[1:]])
    s = [o, L((0, 4.4), (0, -5.6)), L((-4.4, 1.2), (4.4, 1.2))]
    s += hatch(o, 45, k)
    return s

@shape
def castle(k):
    top = [(-5, 3)]
    for i in range(5): x = -5 + 2 * i; top += [(x, 4.2), (x + 1, 4.2), (x + 1, 3), (x + 2, 3)]
    top[-1] = (5, 3)
    s = [P((-5, 3), (-5, -4), (5, -4), (5, 3)), P(*top), P((-1.2, -4), (-1.2, -1.2), (0, 0), (1.2, -1.2), (1.2, -4)), rect(-3.6, -0.8, -2.4, 1.2), rect(2.4, -0.8, 3.6, 1.2)]
    s += hatch(rect(-5, -4, 5, 3), 0, k // 2)
    return s

@shape
def car(k):
    body = P((-5.6, -1), (-5.6, 1), (-3, 1.4), (-1.8, 3.4), (2.4, 3.4), (3.6, 1.4), (5.6, 1), (5.6, -1), (-5.6, -1))
    s = [body, circ((-3.2, -1.4), 1.3), circ((3.2, -1.4), 1.3), L((0.3, 3.4), (0.3, 1.4)), L((-3, 1.4), (3.6, 1.4))]
    s += rays((-3.2, -1.4), 0, 1.3, 3 + k // 4) + rays((3.2, -1.4), 0, 1.3, 3 + k // 4) if k > 1 else []
    s += hatch(body, 90, k // 2, lo=0.0, hi=1.0)
    return s

@shape
def catface(k):
    h = circ((0, 0), 4.2)
    s = [h, P((-3.6, 2.2), (-3.4, 5.6), (-1.4, 3.9)), P((3.6, 2.2), (3.4, 5.6), (1.4, 3.9)), circ((-1.5, 0.8), 0.7, 0.9), circ((1.5, 0.8), 0.7, 0.9),
         P((-0.5, -0.6), (0, -1.1), (0.5, -0.6), (-0.5, -0.6)), S((0, -1.1), (-0.6, -1.9), (-1.4, -1.6)), S((0, -1.1), (0.6, -1.9), (1.4, -1.6))]
    s += [L((-1.6, -1.0 + 0.5 * i), (-5.2, -1.6 + 0.9 * i)) for i in range(2)] + [L((1.6, -1.0 + 0.5 * i), (5.2, -1.6 + 0.9 * i)) for i in range(2)]
    s += hatch(h, 90, k // 2, lo=0.0, hi=0.3) + hatch(h, 90, k // 2, lo=0.7, hi=1.0)
    return s

@shape
def moon(k):
    m = np.vstack([arc((0, 0), 5, 70, 290), arc((2.2, 0), 4.2, 245, 115)[1:]])
    s = [m]
    for (x, y, r) in ((4.6, 4.6, 1.2), (5.6, -2.6, 0.9), (2.6, 6.4, 0.7)):
        pts = [(x + np.cos(np.radians(90 + 72 * i * 2)) * r, y + np.sin(np.radians(90 + 72 * i * 2)) * r) for i in range(5)]
        s.append(poly(*pts))
    s += hatch(m, 30, k)
    return s

@shape
def fishbone(k):
    n = 3 + k // 2
    s = [L((-5.6, 0), (4.4, 0)), S((4.4, 0), (5.2, 1.0), (6.4, 0.6), (6.8, 0), (6.4, -0.6), (5.2, -1.0), (4.4, 0)), circ((5.8, 0.2), 0.25),
         P((-5.6, 0), (-7, 1.4)), P((-5.6, 0), (-7, -1.4))]
    for i in range(n):
        x = -4.6 + 8.2 * i / n; h = 2.6 * np.sin(np.pi * (i + 0.5) / n) + 0.8
        s += [L((x, 0), (x - 1.0, h)), L((x + 0.45, 0), (x - 0.55, -h))]
    return s

@shape
def tree(k):
    s = [S((0, -6), (0.2, -2), (0, 1)), L((-1.5, -6), (1.5, -6))]
    def br(p, ang, ln, d):
        q = (p[0] + ln * np.cos(np.radians(ang)), p[1] + ln * np.sin(np.radians(ang)))
        s.append(L(p, q))
        if d > 0:
            for da in (-32, 32):
                m = (p[0] + (q[0] - p[0]) * 0.55, p[1] + (q[1] - p[1]) * 0.55)
                br(m, ang + da, ln * 0.62, d - 1)
    br((0, 1), 90, 5.2, min(3, 1 + k // 4))
    br((0.1, -2.2), 140, 3.2, min(2, k // 5)); br((0.1, -1.4), 40, 3.0, min(2, k // 5))
    return s

@shape
def spiderweb(k):
    n = 6 + k // 4
    s = rays((0, 0), 0, 5.6, n)
    for r in np.linspace(1.4, 5, 2 + k // 3):
        pts = [(r * np.cos(np.radians(360 * i / n + 90)), r * np.sin(np.radians(360 * i / n + 90))) for i in range(n)]
        s.append(poly(*pts))
    return s

@shape
def guitar(k):
    b = S((0, 0.6), (-2.4, 1.8), (-3.2, -0.6), (-3.8, -3.4), (-2.2, -5.6), (0, -5.8), (2.2, -5.6), (3.8, -3.4), (3.2, -0.6), (2.4, 1.8), (0, 0.6))
    s = [b, circ((0, -2.2), 1.2), rect(-0.6, 0.6, 0.6, 7), rect(-1, 7, 1, 8.4), L((-1.2, -4.4), (1.2, -4.4))]
    s += [L((-0.6, 1.8 + 1.1 * i), (0.6, 1.8 + 1.1 * i)) for i in range(min(5, 1 + k // 2))] + hatch(b, 0, k // 3, lo=0, hi=0.25)
    return s

@shape
def bus(k):
    body = P((-6, -2), (-6, 3.6), (5.4, 3.6), (6, 2.4), (6, -2), (-6, -2))
    s = [body, circ((-3.6, -2.4), 1.1), circ((3.6, -2.4), 1.1), L((-6, 0.8), (6, 0.8))]
    n = 3 + k // 2
    for i in range(n):
        x0 = -5.4 + 10.2 * i / n; x1 = x0 + 10.2 / n - 0.6; s.append(rect(x0, 1.3, x1, 3.0))
    return s

@shape
def robot(k):
    s = [rect(-3, 0, 3, 4.6), circ((-1.3, 2.8), 0.6), circ((1.3, 2.8), 0.6), L((-1.4, 1.2), (1.4, 1.2)), L((0, 4.6), (0, 5.8)), circ((0, 6.3), 0.5),
         rect(-3.6, -5.6, 3.6, -0.5), P((-3.6, -1.4), (-5.4, -3.6)), P((3.6, -1.4), (5.4, -3.6)), rect(-2.6, -7.8, -1.0, -5.6), rect(1.0, -7.8, 2.6, -5.6)]
    s += hatch(rect(-3.6, -5.6, 3.6, -0.5), 0, k // 2) + hatch(rect(-3, 0, 3, 4.6), 90, k // 4, lo=0.0, hi=0.3)
    return s

@shape
def penguin(k):
    b = S((0, 5.4), (-2.6, 3.6), (-3.4, -1.2), (-2.6, -4.6), (0, -5.4), (2.6, -4.6), (3.4, -1.2), (2.6, 3.6), (0, 5.4))
    belly = S((0, 2.6), (-1.8, 0.4), (-1.8, -3), (0, -4.4), (1.8, -3), (1.8, 0.4), (0, 2.6))
    s = [b, belly, circ((-0.9, 3.4), 0.35), circ((0.9, 3.4), 0.35), P((-0.5, 2.6), (0, 1.8), (0.5, 2.6)),
         S((-3.2, 1), (-4.6, -1.6), (-3.2, -2.6)), S((3.2, 1), (4.6, -1.6), (3.2, -2.6)), P((-2, -5.0), (-2.4, -6), (-0.6, -5.4)), P((2, -5.0), (2.4, -6), (0.6, -5.4))]
    s += hatch(belly, 0, k)
    return s

@shape
def octopus(k):
    h = S((-3.6, 0), (-3.8, 3), (-2, 5.4), (0, 5.8), (2, 5.4), (3.8, 3), (3.6, 0))
    s = [np.vstack([h, P((3.6, 0), (-3.6, 0))[1:]]), circ((-1.3, 2.6), 0.6), circ((1.3, 2.6), 0.6)]
    for i in range(6):
        x = -3.0 + 6.0 * i / 5; s.append(S((x, 0), (x + (0.8 if i % 2 else -0.8), -2.2), (x, -4.2), (x + (-0.9 if i % 2 else 0.9), -5.8)))
    s += hatch(np.vstack([h, h[:1]]), 0, k // 2, lo=0.3)
    return s

@shape
def window(k):
    o = rect(-4, -4, 4, 4)
    s = [o, L((0, -4), (0, 4)), L((-4, 0.6), (4, 0.6)), P((-4.6, 4), (0, 6.2), (4.6, 4), (-4.6, 4))]
    s += hatch(rect(-4, -4, 4, 4), 90, k // 2) + hatch(rect(-4, -4, 4, 4), 0, k // 3)
    return s

@shape
def flag(k):
    f = S((-3, 4.6), (-0.6, 5.4), (1.8, 4.2), (4.6, 5.0), (4.6, 0.4), (1.8, -0.4), (-0.6, 0.8), (-3, 0.0))
    s = [L((-3, 6.2), (-3, -6)), np.vstack([f, f[:1]]) if False else f, L((-4.4, -6), (-1.6, -6))]
    s += hatch(np.vstack([f, P((-3, 0.0), (-3, 4.6))[1:]]), 90, k)
    return s

ORDER = ['smiley', 'umbrella', 'house', 'heart', 'star', 'fish', 'pine', 'apple', 'mug', 'balloons', 'sailboat', 'rocket', 'flower', 'butterfly',
         'icecream', 'mushroom', 'crown', 'key', 'bell', 'anchor', 'leaf', 'sun', 'raincloud', 'bird', 'snowman', 'bulb', 'cupcake', 'owl', 'pear',
         'cherries', 'watermelon', 'pumpkin', 'ghost', 'gem', 'hourglass', 'kite', 'glasses', 'envelope', 'gift', 'notes', 'rainbow', 'lollipop',
         'teapot', 'turtle', 'snail', 'cactus', 'bottle', 'shield', 'castle', 'car', 'catface', 'moon', 'fishbone', 'tree', 'spiderweb', 'guitar',
         'bus', 'robot', 'penguin', 'octopus', 'window', 'flag']
