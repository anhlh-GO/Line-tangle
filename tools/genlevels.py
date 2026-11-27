# Generate new levels from line drawings (tools/shapes.py) matching target stats (tapes, blockers, rounds).
#
# Model: the drawing is turned into a graph (nodes = stroke ends, T-junctions, crossings). At each node the
# incident edge-ends are either paired (a tape passes straight through) or terminate. A terminating end is
# "attached" (its ball sits on the node, i.e. on every tape passing there -> it blocks them) or "detached"
# (trimmed back 0.55 so the ball sits clear). Trails are then cut into tapes. A hill-climb over node configs
# and cut length hits the targets; every candidate is re-checked with the game's real blocking rule.
#
# usage: python tools/genlevels.py [first_n=50] [only_index ...]
import json, os, sys, math, random
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import shapes

ROOT = os.path.join(os.path.dirname(__file__), '..')
BALL_R, SKIN, GAP, NODE_R = 0.2, 0.1, 0.55, 0.32
BLOCK_D = 2 * BALL_R - SKIN          # ball centre closer than this to a route blocks it
TURN = float(os.environ.get('TURN', 0.45))   # max cos between the two ends a tape may turn through at a junction
COLORS = ['blue1', 'blue2', 'brown1', 'gray1', 'green1', 'green2', 'orange1', 'pink1', 'purple1', 'red1', 'yellow1']

def dens(p, step=0.05):
    p = np.asarray(p, float); out = [p[0]]
    for a, b in zip(p[:-1], p[1:]):
        n = max(1, int(np.ceil(np.hypot(*(b - a)) / step)))
        for i in range(1, n + 1): out.append(a + (b - a) * i / n)
    return np.array(out)

def cum(p): return np.concatenate([[0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])

# ---------------------------------------------------------------- drawing -> graph
class Graph:
    def __init__(self, strokes):
        cs = []
        for s in strokes:
            s = dens(s)
            if len(s) < 3 or cum(s)[-1] < 0.6: continue
            closed = np.hypot(*(s[0] - s[-1])) < 1e-3
            cs.append({'p': s, 'closed': closed})
        self.curves = cs
        # snap open ends onto other curves (T junctions) / other ends
        for i, c in enumerate(cs):
            if c['closed']: continue
            for e in (0, -1):
                q = c['p'][e]; best = (NODE_R, None)
                for j, d in enumerate(cs):
                    pts = d['p'] if j != i else (c['p'][12:] if e == 0 else c['p'][:-12])
                    if len(pts) == 0: continue
                    dd = np.hypot(*(pts - q).T); k = int(dd.argmin())
                    if dd[k] < best[0]: best = (dd[k], pts[k])
                if best[1] is not None: c['p'][e] = best[1]
        # events along each curve: (index, position)
        ev = [[] for _ in cs]
        for i, c in enumerate(cs):
            if not c['closed']: ev[i] += [0, len(c['p']) - 1]
        for i, c in enumerate(cs):           # ends lying on other curves
            if c['closed']: continue
            for e in (0, len(c['p']) - 1):
                q = c['p'][e]
                for j, d in enumerate(cs):
                    if j == i: continue
                    dd = np.hypot(*(d['p'] - q).T); k = int(dd.argmin())
                    if dd[k] < 0.06: ev[j].append(k)
        for i in range(len(cs)):             # crossings
            a = cs[i]['p']
            for j in range(i + 1, len(cs)):
                b = cs[j]['p']
                for ia, ib in self._cross(a, b): ev[i].append(ia); ev[j].append(ib)
        # nodes: cluster event positions
        pos = []; ref = []
        for i, c in enumerate(cs):
            for k in sorted(set(ev[i])):
                pos.append(c['p'][k]); ref.append((i, k))
        pos = np.array(pos) if pos else np.zeros((0, 2))
        par = list(range(len(pos)))
        def find(x):
            while par[x] != x: par[x] = par[par[x]]; x = par[x]
            return x
        for a in range(len(pos)):
            for b in range(a + 1, len(pos)):
                if np.hypot(*(pos[a] - pos[b])) < NODE_R: par[find(a)] = find(b)
        roots = sorted({find(a) for a in range(len(pos))}); rid = {r: n for n, r in enumerate(roots)}
        self.nodes = [{'pos': None, 'ends': []} for _ in roots]
        acc = {}
        for a in range(len(pos)): acc.setdefault(rid[find(a)], []).append(pos[a])
        for n, l in acc.items(): self.nodes[n]['pos'] = np.mean(l, 0)
        evn = [dict() for _ in cs]
        for a, (i, k) in enumerate(ref): evn[i][k] = rid[find(a)]
        # edges between consecutive events
        self.edges = []
        for i, c in enumerate(cs):
            ks = sorted(evn[i]); p = c['p']
            if c['closed']:
                if not ks:
                    self.edges.append({'p': p, 'n': (None, None), 'loop': True}); continue
                for a, b in zip(ks, ks[1:] + [ks[0] + len(p) - 1]):
                    seg = p[a:b + 1] if b < len(p) else np.vstack([p[a:], p[1:b - len(p) + 2]])
                    self._add_edge(seg, evn[i][a], evn[i][b % (len(p) - 1)] if b >= len(p) - 1 else evn[i][b])
            else:
                for a, b in zip(ks[:-1], ks[1:]):
                    self._add_edge(p[a:b + 1], evn[i][a], evn[i][b])
        for ei, e in enumerate(self.edges):
            if e.get('loop'): continue
            for end in (0, 1):
                nd = e['n'][end]; pts = e['p'] if end == 0 else e['p'][::-1]
                k = min(len(pts) - 1, 6); d = pts[k] - pts[0]; d = d / (np.hypot(*d) + 1e-9)
                self.nodes[nd]['ends'].append((ei, end, d))
        for e in self.edges: e['len'] = cum(e['p'])[-1]

    def _add_edge(self, seg, na, nb):
        if len(seg) < 2: return
        seg = seg.copy(); seg[0] = self.nodes[na]['pos'] if self.nodes[na]['pos'] is not None else seg[0]
        seg[-1] = self.nodes[nb]['pos'] if self.nodes[nb]['pos'] is not None else seg[-1]
        if cum(seg)[-1] < 0.25: return
        self.edges.append({'p': seg, 'n': (na, nb)})

    @staticmethod
    def _cross(a, b):
        a2, b2 = a[::2], b[::2]
        out = []
        amin, amax = np.minimum(a2[:-1], a2[1:]), np.maximum(a2[:-1], a2[1:])
        bmin, bmax = np.minimum(b2[:-1], b2[1:]), np.maximum(b2[:-1], b2[1:])
        ov = (amin[:, None, 0] <= bmax[None, :, 0]) & (bmin[None, :, 0] <= amax[:, None, 0]) & (amin[:, None, 1] <= bmax[None, :, 1]) & (bmin[None, :, 1] <= amax[:, None, 1])
        for i, j in zip(*np.nonzero(ov)):
            p, r = a2[i], a2[i + 1] - a2[i]; q, s = b2[j], b2[j + 1] - b2[j]
            den = r[0] * s[1] - r[1] * s[0]
            if abs(den) < 1e-12: continue
            t = ((q - p)[0] * s[1] - (q - p)[1] * s[0]) / den; u = ((q - p)[0] * r[1] - (q - p)[1] * r[0]) / den
            if 0 <= t < 1 and 0 <= u < 1: out.append((2 * i, 2 * j))
        # drop crossings next to curve ends (those are T junctions already)
        return [(i, j) for i, j in out if 4 < i < len(a) - 5 and 4 < j < len(b) - 5]

# ---------------------------------------------------------------- configuration -> tapes
def random_config(g, nd, rng, ppass=0.85, patt=0.8):
    ends = g.nodes[nd]['ends']
    if len(ends) <= 1: return {'pairs': [], 'att': None}
    idx = list(range(len(ends))); rng.shuffle(idx); used = set(); pairs = []
    for a in idx:
        if a in used: continue
        cand = [b for b in idx if b != a and b not in used and np.dot(ends[a][2], ends[b][2]) < TURN]
        if cand and rng.random() < ppass:
            b = min(cand, key=lambda b: np.dot(ends[a][2], ends[b][2])) if rng.random() < 0.65 else rng.choice(cand)
            pairs.append((a, b)); used |= {a, b}
    term = [a for a in idx if a not in used]
    att = rng.choice(term) if term and rng.random() < patt else None
    return {'pairs': pairs, 'att': att}

def build(g, cfg, Lp, rng_cut):
    """returns tapes (polyline, meta) + block edges, or None"""
    partner = {}; term = {}
    for nd, node in enumerate(g.nodes):
        c = cfg[nd]; ends = node['ends']
        for a, b in c['pairs']:
            ka, kb = (ends[a][0], ends[a][1]), (ends[b][0], ends[b][1]); partner[ka] = kb; partner[kb] = ka
        for a in range(len(ends)):
            k = (ends[a][0], ends[a][1])
            if k in partner: continue
            term[k] = 'free' if len(ends) == 1 else ('att' if a == c['att'] else 'det')
    # walk trails
    seen = set(); trails = []
    def walk(ei, end0):
        seq = []; e, s = ei, end0
        while True:
            seq.append((e, s)); seen.add(e)
            k_out = (e, 1 - s)
            if k_out in partner:
                ne, ns = partner[k_out]
                if ne in seen: return seq, True
                e, s = ne, ns
            else: return seq, False
    for k, kind in term.items():
        if k[0] in seen: continue
        seq, cl = walk(k[0], k[1]); trails.append(seq)
    for ei, e in enumerate(g.edges):
        if ei in seen: continue
        if e.get('loop'): trails.append([(ei, 0)]); seen.add(ei); continue
        seq, cl = walk(ei, 0); trails.append(seq)
    tapes = []; node_hosts = {}
    for seq in trails:
        pts = []; nodes_at = []   # (arc length, node id)
        for e, s in seq:
            p = g.edges[e]['p'] if s == 0 else g.edges[e]['p'][::-1]
            if pts:
                pts.extend(p[1:])
            else: pts.extend(p)
        P = np.array(pts); C = cum(P); L = C[-1]
        first, last = seq[0], seq[-1]
        e0 = g.edges[first[0]]; closed = e0.get('loop') or ((last[0], 1 - last[1]) in partner)
        # node positions along trail
        acc = 0.0
        for e, s in seq:
            ed = g.edges[e]
            if ed.get('loop'): break
            na, nb = (ed['n'][0], ed['n'][1]) if s == 0 else (ed['n'][1], ed['n'][0])
            nodes_at.append((acc, na)); acc += ed['len']; nodes_at.append((acc, nb))
        inner = sorted({(round(a, 3), n) for a, n in nodes_at if (0 < a < L) or closed})
        # end treatment
        if closed:
            a_s, a_e = 0.0, L; st_kind = en_kind = 'cut'
        else:
            st_kind = term.get((first[0], first[1]), 'free'); en_kind = term.get((last[0], 1 - last[1]), 'free')
            a_s = GAP if st_kind == 'det' else 0.0; a_e = L - (GAP if en_kind == 'det' else 0.0)
        span = a_e - a_s
        if span < 0.9: continue            # tiny stub: leave it out of the drawing
        n = max(1, min(int(round(span / Lp)), int(span // 1.2)))
        # cut positions avoiding nodes
        node_arcs = [a for a, _ in nodes_at]
        def ok_cut(x): return all(abs(x - a) > 0.55 for a in node_arcs) and (closed or (x - a_s > 1.2 and a_e - x > 1.2))
        cuts = []
        if closed:
            off = rng_cut.random() * span
            for i in range(n):
                base = (off + span * i / n) % L
                for d in sorted(np.linspace(-span / n * 0.35, span / n * 0.35, 15), key=abs):
                    x = (base + d) % L
                    if ok_cut(x) and ok_cut(x - L) and ok_cut(x + L): cuts.append(x); break
            if not cuts: continue
            cuts.sort()
        else:
            for i in range(1, n):
                base = a_s + span * i / n
                for d in sorted(np.linspace(-span / n * 0.35, span / n * 0.35, 15), key=abs):
                    if ok_cut(base + d): cuts.append(base + d); break
            cuts = sorted(set(cuts))
        # pieces
        if closed:
            bounds = [(cuts[i] + GAP / 2, cuts[(i + 1) % len(cuts)] - GAP / 2 + (L if i == len(cuts) - 1 else 0)) for i in range(len(cuts))]
        else:
            b = [a_s] + cuts + [a_e]
            bounds = [(b[i] + (GAP / 2 if i > 0 else 0), b[i + 1] - (GAP / 2 if i < len(b) - 2 else 0)) for i in range(len(b) - 1)]
        PP = np.vstack([P, P[1:]]) if closed else P; CC = cum(PP)
        for (x0, x1) in bounds:
            if x1 - x0 < 0.9: continue
            i0, i1 = np.searchsorted(CC, x0), np.searchsorted(CC, x1)
            seg = PP[max(0, i0):min(len(PP), i1 + 1)]
            if len(seg) < 3: continue
            t = {'p': seg, 'len': x1 - x0, 'nodes': []}
            # which nodes this piece passes through (strictly inside) and its attached ends
            for a, nd in nodes_at + ([(a + L, nd) for a, nd in nodes_at] if closed else []):
                if x0 + 0.05 < a < x1 - 0.05: t['nodes'].append(nd)
            if not closed:
                if x0 == a_s == 0.0 and st_kind == 'att': t['att0'] = g.edges[first[0]]['n'][first[1]]
                if abs(x1 - a_e) < 1e-9 and a_e == L and en_kind == 'att': t['att1'] = g.edges[last[0]]['n'][1 - last[1]]
            tapes.append(t)
    # dependencies: X attached at node v blocks every tape passing through v
    pass_at = {}
    for ti, t in enumerate(tapes):
        for nd in t['nodes']: pass_at.setdefault(nd, set()).add(ti)
    block = [set() for _ in tapes]   # block[y] = tapes whose balls sit on y
    for ti, t in enumerate(tapes):
        for k in ('att0', 'att1'):
            if k in t:
                for y in pass_at.get(t[k], ()):
                    if y != ti: block[y].add(ti)
    return tapes, block

def metrics_relaxed(block):
    n = len(block); gone = set(); rounds = 0
    while len(gone) < n:
        free = [i for i in range(n) if i not in gone and not (block[i] - gone)]
        if not free: break
        gone |= set(free); rounds += 1
    return n, sum(len(b) for b in block), rounds, n - len(gone)

def metrics(block):
    n = len(block); gone = set(); rounds = 0
    while len(gone) < n:
        free = [i for i in range(n) if i not in gone and not (block[i] - gone)]
        if not free: return None
        gone |= set(free); rounds += 1
    return n, sum(len(b) for b in block), rounds

# ---------------------------------------------------------------- real-rule check (same as tools/solve.mjs, SKIN 0.1)
def real_check(tapes):
    routes = [t['p'] for t in tapes]
    owner = np.repeat(np.arange(len(tapes)), 2)
    B = np.array([q for t in tapes for q in (t['p'][0], t['p'][-1])])
    if any(t.get('ev', 1) != 1 or t.get('eev', 1) != 1 for t in tapes):
        rad = np.array([BALL_R * r for t in tapes for r in (t.get('ev', 1), t.get('eev', 1))])
        block = [set() for _ in routes]
        for i, r in enumerate(routes):
            rr = BALL_R * max(tapes[i].get('ev', 1), tapes[i].get('eev', 1))
            for j in range(len(B)):
                if owner[j] == i: continue
                lim = rr + rad[j] - SKIN
                if np.min(np.hypot(*(r - B[j]).T)) < lim: block[i].add(int(owner[j]))
        return block
    block = [set() for _ in routes]
    for i, r in enumerate(routes):
        lo, hi = r.min(0) - BLOCK_D, r.max(0) + BLOCK_D
        m = (B[:, 0] >= lo[0]) & (B[:, 0] <= hi[0]) & (B[:, 1] >= lo[1]) & (B[:, 1] <= hi[1]) & (owner != i)
        idx = np.nonzero(m)[0]
        if not len(idx): continue
        d = np.hypot(r[None, :, 0] - B[idx, None, 0], r[None, :, 1] - B[idx, None, 1]).min(1)
        for j in idx[d < BLOCK_D]: block[i].add(int(owner[j]))
    return block

def _trim(t, end, d):
    p = t['p'] if end == 1 else t['p'][::-1]
    C = cum(p); L = C[-1]
    if L - d < 0.9: return False
    k = np.searchsorted(C, L - d); q = np.vstack([p[:k], [p[k - 1] + (p[k] - p[k - 1]) * ((L - d - C[k - 1]) / max(1e-9, C[k] - C[k - 1]))]])
    t['p'] = q if end == 1 else q[::-1]; t['len'] = L - d
    t.pop('att1' if end == 1 else 'att0', None)
    return True

def repair(tapes, steps=None):
    """break deadlocks: pull back the ball ends that sit on another stuck tape's route"""
    steps = steps or 2 * len(tapes) + 4
    for _ in range(steps):
        b = real_check(tapes); n = len(b); gone = set()
        while True:
            free = [i for i in range(n) if i not in gone and not (b[i] - gone)]
            if not free: break
            gone |= set(free)
        S = [i for i in range(n) if i not in gone]
        if not S: return b
        did = False
        for i in sorted(S, key=lambda i: (len(b[i] - gone), i)):
            r = tapes[i]['p']; ri = BALL_R * max(tapes[i].get('ev', 1), tapes[i].get('eev', 1))
            for j in sorted(b[i] - gone):
                for end in (0, 1):
                    q = tapes[j]['p'][0 if end == 0 else -1]; rj = BALL_R * tapes[j].get('ev' if end == 0 else 'eev', 1)
                    lim = ri + rj - SKIN
                    if np.min(np.hypot(*(r - q).T)) < lim + 0.02:
                        for d in (0.35, 0.6, 0.9, 1.3, 1.8):
                            tt = dict(tapes[j])
                            if not _trim(tt, end, d): break
                            if np.min(np.hypot(*(r - tt['p'][0 if end == 0 else -1]).T)) >= lim + 0.05:
                                tapes[j] = tt; did = True; break
            if did: break
        if not did: return b
    return real_check(tapes)

def score(m, tgt):
    T, E, R = m; t, e, r = tgt
    def rel(a, b, slack): return max(0.0, abs(a - b) - slack) / max(b, 1)
    return rel(T, t, max(1, 0.12 * t)) * 3 + rel(E, e, max(1, 0.12 * e)) * 2 + rel(R, r, max(1, 0.12 * r)) * 2

def within(m, tgt):
    T, E, R = m; t, e, r = tgt
    tol = float(os.environ.get('TOL', 0.15))
    ok = lambda a, b: abs(a - b) <= max(1, round(tol * b))
    okT = abs(T - t) <= (round(tol * t) if t <= 6 else max(1, round(tol * t)))
    return okT and ok(E, e) and ok(R, r)

def prep(shape, k, tgt, Lavg, boost=1.0):
    strokes = shapes.SH[shape](k)
    tot = sum(cum(shapes._dens(s))[-1] for s in strokes)
    scale = (max(1.0, tgt[0] * Lavg / tot) if tgt[0] > 4 else max(0.6, tgt[0] * Lavg / tot)) * boost
    g = Graph([np.asarray(s) * scale for s in strokes])
    j3 = sum(1 for n in g.nodes if len(n['ends']) == 3); short = sum(1 for e in g.edges if e['len'] < 0.8)
    return g, scale, j3, short

def search(shape, k, tgt, Lavg, seed, iters=2500, pre=None):
    rng = random.Random(seed); np.random.seed(seed)
    g, scale, _, _ = pre or prep(shape, k, tgt, Lavg)
    if not g.edges or not g.nodes: return None
    junctions = sum(1 for n in g.nodes if len(n['ends']) >= 3)
    cfg = [random_config(g, nd, rng, ppass=1.0, patt=1.0) for nd in range(len(g.nodes))]
    Lp = Lavg
    for _ in range(30):   # make sure the start state is valid
        r0 = build(g, cfg, Lp, random.Random(seed))
        if r0 and metrics(r0[1]): break
        cfg = [random_config(g, nd, rng, ppass=1.0, patt=rng.random()) for nd in range(len(g.nodes))]; Lp *= 1.1
    cur = build(g, cfg, Lp, random.Random(seed)); best = None
    def ev(res):
        if not res or not res[0]: return 1e9, None
        res[1][:] = repair(res[0])
        T, E, R, stuck = metrics_relaxed(res[1])
        if stuck: return 5 + score((T, E, R), tgt) + 0.3 * stuck, None
        return score((T, E, R), tgt), (T, E, R)
    cs, cm = ev(cur)
    for it in range(iters):
        ncfg = list(cfg); nLp = Lp
        r = rng.random()
        if r < 0.15: nLp = min(14, max(1.6, Lp * rng.choice([0.85, 0.92, 1.08, 1.18])))
        else:
            for _ in range(rng.choice([1, 1, 2])):
                nd = rng.randrange(len(g.nodes)); ncfg[nd] = random_config(g, nd, rng, ppass=rng.choice([0.6, 0.85, 1.0]), patt=rng.choice([0.5, 0.8, 1.0]))
        res = build(g, ncfg, nLp, random.Random(seed))
        s, m = ev(res)
        temp = 0.15 * (1 - it / iters) + 0.005
        if s <= cs or (s < 1e8 and rng.random() < math.exp(-(s - cs) / temp)):
            cfg, Lp, cs, cm, cur = ncfg, nLp, s, m, res
        if m and (best is None or s < best[0]): best = (s, m)
        if m and within(m, tgt):
            for t in res[0]: t['p'] = dense(to_segs(t['p']))
            rb = real_check(res[0]); rm = metrics(rb)
            if os.environ.get('DBG'): print('   model ok', m, 'real', rm, flush=True)
            if rm and within(rm, tgt):
                return {'tapes': res[0], 'block': rb, 'm': rm, 'shape': shape, 'k': k, 'scale': scale, 'junctions': junctions}
    if os.environ.get('DBG'): print('  ', shape, k, 'J', junctions, 'best', best, flush=True)
    return None

# ---------------------------------------------------------------- export
def to_segs(p):
    C = cum(p); L = C[-1]; n = max(2, int(L / 0.3)); idx = np.searchsorted(C, np.linspace(0, L, n + 1)); idx[-1] = len(p) - 1
    q = p[np.unique(idx)]
    if len(q) < 2: q = p[[0, -1]]
    ext = np.vstack([2 * q[0] - q[1], q, 2 * q[-1] - q[-2]]); segs = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        c1 = p1 + (p2 - p0) / 6; c2 = p2 - (p3 - p1) / 6
        segs.append([round(float(v), 4) for v in (*p1, *c1, *c2, *p2)])
    return segs

def dense(segs):
    """sample exported bezier segments like tools/solve.mjs (step 0.03)"""
    P = []
    for k, (x0, y0, x1, y1, x2, y2, x3, y3) in enumerate(segs):
        ln = np.hypot(x1 - x0, y1 - y0) + np.hypot(x2 - x1, y2 - y1) + np.hypot(x3 - x2, y3 - y2)
        n = max(4, int(np.ceil(ln / 0.03))); t = np.arange(1 if k else 0, n + 1) / n; u = 1 - t
        P.append(np.stack([u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3, u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3], 1))
    return np.concatenate(P)

def colorize(tapes, rng):
    n = len(tapes); nb = [set() for _ in range(n)]
    ends = [(i, t['p'][0]) for i, t in enumerate(tapes)] + [(i, t['p'][-1]) for i, t in enumerate(tapes)]
    for i, t in enumerate(tapes):
        for j, c in ends:
            if j != i and np.min(np.hypot(*(t['p'][::4] - c).T)) < 0.8: nb[i].add(j); nb[j].add(i)
    col = [None] * n
    for i in sorted(range(n), key=lambda i: -len(nb[i])):
        used = {col[j] for j in nb[i]}
        opts = [c for c in COLORS if c not in used] or COLORS
        col[i] = rng.choice(opts)
    return col

def add_big_balls(res, want, tgt, rng):
    """enlarge up to `want` free-standing end balls (ev 1.6-2.2) while the level stays solvable and on target"""
    tapes = res['tapes']; placed = 0
    ends = [(i, e) for i in range(len(tapes)) for e in (0, 1)]; rng.shuffle(ends)
    for i, e in ends:
        if placed >= want: break
        key = 'ev' if e == 0 else 'eev'
        if tapes[i].get('ev', 1) != 1 or tapes[i].get('eev', 1) != 1: continue
        tapes[i][key] = round(rng.uniform(1.6, 2.2), 2)
        b = real_check(tapes); m = metrics(b)
        if m and within(m, tgt): placed += 1; res['block'] = b; res['m'] = m
        else: tapes[i][key] = 1.0
    return placed

def export(name, res, tut, rng):
    tapes = res['tapes']; cols = colorize(tapes, rng)
    out = []
    for i, t in enumerate(tapes):
        out.append({'id': 'TapeUnit%03d' % (i + 1), 'color': cols[i], 'cid': COLORS.index(cols[i]), 'w': 0.07, 'speed': 5.0, 'sweep': 0.2, 'click': 0.35,
                    'ev': t.get('ev', 1.0), 'eev': t.get('eev', 1.0), 'eo': 0.2, 'epo': 0.0, 'gs': 1.0, 'enc': 0, 'closed': 0, 'segs': to_segs(t['p']), 'z': 0.0, 'on': True})
    allp = np.vstack([t['p'] for t in tapes]); c = (allp.min(0) + allp.max(0)) / 2
    for t in out:
        t['segs'] = [[round(v - (c[0] if i % 2 == 0 else c[1]), 4) for i, v in enumerate(s)] for s in t['segs']]
    if tut is not None:
        tut = dict(tut)
        if tut.get('type') == 1: tut['tape'] = out[0]['id']
        if tut.get('type') == 2:
            blocked = [i for i, b in enumerate(res['block']) if b]
            if blocked: tut['tape'] = out[blocked[0]]['id']
    return {'name': name, 'diff': 0, 'tut': tut, 'tapes': out, 'gen': {'shape': res['shape'], 'k': res['k']}}

def set_style(i):
    r = random.Random(1000 + i)
    shapes.STYLE.update(mode=['wave', 'bow', 'swirl', 'wave'][i % 4], phase=r.random() * 6.28, lam=r.uniform(2.4, 3.6), tilt=r.uniform(-12, 12),
                        amp=r.uniform(0.22, 0.3), bow=r.uniform(0.35, 0.55))

def solve_one(args):
    import time
    i, src, s, tut, cand, budget = args
    set_style(i)
    tgt = (s['tapes'], s['edges'], s['rounds']); Lavg = min(6.5, max(3.6, s['avgLen']))
    t0 = time.time(); found = None
    extra = [x for x in os.environ.get('SPARES', 'flower,spiderweb,snail,lollipop,catface,moon,car,cherries,pumpkin,raincloud').split(',') if x]
    seed = 0; npass = 0
    VAR = [None, dict(mode='bow'), dict(mode='wave', amp=0.15), dict(mode='bow', bow=0.3), dict(mode='wave', amp=0.1)] + ([dict(mode='straight')] if os.environ.get('STRAIGHT') else [])
    while time.time() - t0 < budget and not found:
        set_style(i)
        if VAR[npass % len(VAR)]: shapes.STYLE.update(VAR[npass % len(VAR)])
        npass += 1
        for shp in cand + [x for x in extra if x not in cand]:
            if time.time() - t0 > budget * (0.12 * npass + 0.3): break
            scored = []
            for k in list(range(0, 24)) + list(range(24, 81, 3)):
                try: pre = prep(shp, k, tgt, Lavg, 1.0)
                except Exception: continue
                g, sc, j3, short = pre
                j4 = sum(1 for n in g.nodes if len(n['ends']) == 4)
                jj = j3 + 0.4 * j4; pen = abs(jj - 1.3 * tgt[1] - 1) + 3 * max(0, 1.0 * tgt[1] - jj) + 0.6 * max(0, short - 0.15 * len(g.edges))
                scored.append((pen, k, 1.0, pre))
                if j3 > 2.2 * tgt[1] + 8: break
            scored.sort(key=lambda x: x[0])
            for _, k, boost, pre in scored[:3] + [(0, k, b, None) for _, k, _, _ in scored[:1] for b in (0.82, 1.3)]:
                if pre is None:
                    try: pre = prep(shp, k, tgt, Lavg, boost)
                    except Exception: continue
                try: r = search(shp, k, tgt, Lavg, seed * 7919 + i, iters=3000, pre=pre)
                except Exception as ex: print('  search error', shp, k, ex, flush=True); r = None
                seed += 1
                if r: found = r; break
                if time.time() - t0 > budget: break
            if found or time.time() - t0 > budget: break
    if not found: return i, None
    name = 'new%d' % (i + 1)
    bigs = 0
    for f in s['features']:
        if f.startswith('Big balls x'): bigs = int(f.split('x')[1])
    if bigs == 0 and random.Random(i).random() < 0.25: bigs = 1 + random.Random(i).randrange(2)
    found['big'] = add_big_balls(found, min(bigs, 6), tgt, random.Random(i)) if bigs else 0
    lv = export(name, found, tut, random.Random(i))
    lv['diff'] = s['diff']; lv['replaces'] = src
    json.dump(lv, open(f'{ROOT}/data/levels/{name}.json', 'w'), separators=(',', ':'))
    return i, {'name': name, 'replaces': src, 'shape': found['shape'], 'k': found['k'], 'target': tgt, 'got': found['m'], 'diff': s['diff'], 'big': found.get('big', 0), 'style': '%s %.2f' % (shapes.STYLE['mode'], shapes.STYLE['amp'] if shapes.STYLE['mode'] != 'bow' else shapes.STYLE['bow']), 'secs': round(time.time() - t0), 'tol': float(os.environ.get('TOL', 0.15))}

if __name__ == '__main__':
    from multiprocessing import Pool
    CFG = json.load(open(ROOT + '/data/config.json', encoding='utf8'))
    order = CFG.get('origOrder', CFG['order'])
    S = json.load(open(ROOT + '/docs/levels/stats.json'))
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    only = [int(x) for x in sys.argv[2:]]
    budget = float(os.environ.get('BUDGET', 300))
    plan = json.load(open(ROOT + '/tools/genplan.json'))
    rp = ROOT + '/docs/levels/new_report.json'
    report = json.load(open(rp)) if os.path.exists(rp) else {}
    jobs = []
    for i in range(N):
        if only and (i + 1) not in only: continue
        src = order[i]; L0 = json.load(open(f'{ROOT}/data/levels/{src}.json'))
        jobs.append((i, src, S[src], L0.get('tut'), plan.get(str(i + 1), []), budget))
    with Pool(min(14, len(jobs))) as pool:
        for i, r in pool.imap_unordered(solve_one, jobs):
            if r: report[str(i + 1)] = r; print(i + 1, r['shape'], 'k', r['k'], 'target', r['target'], 'got', r['got'], r['secs'], 's', flush=True)
            else: print('FAILED', i + 1, flush=True)
            json.dump(report, open(rp, 'w'), indent=0)
