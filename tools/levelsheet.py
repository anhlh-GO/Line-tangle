# build docs/Line-Tangle-Levels.xlsx from docs/levels/stats.json + images
import json, os, io
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..')
D = ROOT + '/docs/levels'
S = json.load(open(D + '/stats.json')); C = json.load(open(ROOT + '/data/config.json', encoding='utf8'))
SCH = json.load(open(ROOT + '/work/ta/LevelSchemes.txt', encoding='utf8'))['schemes']
inSch = {}
for s in SCH:
    for i, l in enumerate(s['levels']): inSch.setdefault(l['address'], []).append(f"{s['id']}#{i + 1}")
DIFF = ['Normal', 'Hard', 'Super Hard', 'Nightmare']
DFILL = ['FFF7EFE2', 'FFFCE3E1', 'FFEEDDFF', 'FFDCD3FA']
HDR = PatternFill('solid', fgColor='FF8A5A2B'); HF = Font(bold=True, color='FFFFFFFF')
thin = Side(style='thin', color='FFE2D6BD')
TH = 96  # thumbnail px

def thumb(name):
    im = Image.open(f'{D}/img/{name}.png').resize((TH, TH), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); b.seek(0)
    x = XImage(b); x.width = TH; x.height = TH; return x

def feats(s): return '; '.join(f for f in s['features'] if not f.startswith('Layered'))

COLS = [('#', 6), ('Image', 14), ('Level', 11), ('Difficulty', 11), ('Tapes', 7), ('Colors', 7), ('Blockers', 9), ('Free at start', 8), ('Rounds', 8),
        ('Round sizes', 22), ('Blocked both ways', 9), ('Max blockers', 8), ('Crossings', 9), ('Grazes', 7), ('Total length', 9), ('Longest tape', 9),
        ('Size W x H', 11), ('Line width', 8), ('Features', 30), ('Start hint', 22), ('Clear hint', 22), ('Daily dates', 12), ('Schemes (id#pos)', 22)]

def hint(h):
    return (C['hintTexts'].get(str(h[0]), '') .replace('{0}', f'{h[1]:.2f}')) if h else ''

def row(s, idx):
    return [idx, None, s['name'], DIFF[s['diff']], s['tapes'], s['colors'], s['edges'], s['free0'], s['rounds'], ' '.join(map(str, s['roundSizes'])),
            s['blockedBoth'], s['maxBlockers'], s['crossings'], s['graze'], s['pathLen'], s['longest'], f"{s['w']} x {s['h']}", ','.join(map(str, s['lineWidth'])),
            feats(s), hint(s['startHint']), hint(s['clearHint']), ', '.join(s['daily']), ', '.join(inSch.get(s['name'], []))]

def sheet(ws, names, idxf):
    for c, (h, w) in enumerate(COLS, 1):
        cell = ws.cell(1, c, h); cell.fill = HDR; cell.font = HF; cell.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[1].height = 32; ws.freeze_panes = 'C2'
    for r, nm in enumerate(names, 2):
        s = S[nm]
        for c, v in enumerate(row(s, idxf(r - 1, nm)), 1):
            cell = ws.cell(r, c, v); cell.alignment = Alignment(vertical='center', wrap_text=c in (10, 19, 20, 21, 22, 23)); cell.border = Border(bottom=thin)
            if c == 4: cell.fill = PatternFill('solid', fgColor=DFILL[s['diff']])
        ws.row_dimensions[r].height = TH * 0.78
        ws.add_image(thumb(nm), f'B{r}')
    ws.auto_filter.ref = f'A1:{get_column_letter(len(COLS))}{len(names) + 1}'

wb = Workbook()
# summary
ws = wb.active; ws.title = 'Summary'
order = C['order']; M = [S[a] for a in order]
import statistics as st
lines = [('Line Tangle: Untangle Puzzle 1.1130 — level data', ''), ('Level assets in the build', len(S)), ('Main play order (scheme 4 "C", first 50 replaced by new levels)', len(order)), ('New levels at the front', sum(1 for a in order[:50] if a.startswith('new'))),
         ('Loop after level 400 restarts at', f'#{C["loopStart"]}'), ('Levels only in other schemes', len(set(n for n in S if not n.startswith('new')) - set(order))), ('Daily challenge days scheduled', len(C['daily'])), ('', '')]
lines.append(('Difficulty (main order)', 'Levels | median tapes | median blockers | median rounds'))
for d in range(4):
    g = [s for s in M if s['diff'] == d]
    lines.append((DIFF[d], f"{len(g)} | {st.median([s['tapes'] for s in g])} | {st.median([s['edges'] for s in g])} | {st.median([s['rounds'] for s in g])}"))
lines += [('', ''), ('Column guide', '')]
guide = {'Blockers': 'Balls of other tapes lying on this tape route, counted on the easier side of each tape, summed over the level',
         'Free at start': 'Tapes that can be removed immediately', 'Rounds': 'Removal waves when every free tape is removed each wave (dependency depth)',
         'Round sizes': 'Tapes removed in each wave', 'Blocked both ways': 'Tapes blocked from both ends at the start', 'Max blockers': 'Most blockers on one tape (easier side)',
         'Crossings': 'Points where tapes cross (visual tangle, never blocks)', 'Grazes': 'Ball contacts under 0.1 units, ignored by the rule',
         'Total length / Longest tape': 'World units (ball radius = 0.2)', 'Schemes (id#pos)': 'Scheme id and position: 1 all, 2 A test, 3 B test, 4 C (default), 5 v1.3 test, 6 test 6'}
lines += list(guide.items())
for r, (a, b) in enumerate(lines, 1):
    ws.cell(r, 1, a).font = Font(bold=r == 1 or a in ('Difficulty (main order)', 'Column guide'), size=14 if r == 1 else 11); ws.cell(r, 2, b)
ws.column_dimensions['A'].width = 38; ws.column_dimensions['B'].width = 110

sheet(wb.create_sheet('Main order (400)'), order, lambda i, nm: i)
rest = sorted(set(S) - set(order), key=lambda s: int(''.join(c for c in s if c.isdigit())))
allnames = sorted([n for n in S if not n.startswith('new')], key=lambda s: int(''.join(c for c in s if c.isdigit())))
sheet(wb.create_sheet('All 587 levels'), allnames, lambda i, nm: order.index(nm) + 1 if nm in order else '')
dl = [('level%d' % lid, dte) for dte, lid in C['daily'] if ('level%d' % lid) in S]
ws = wb.create_sheet('Daily challenge'); sheet(ws, [n for n, _ in dl], lambda i, nm: i)
ws.cell(1, 1, 'Day')

# ---- new levels (generated, replace main order 1-50)
REP = json.load(open(D + '/new_report.json')) if os.path.exists(D + '/new_report.json') else {}
SOLV = json.load(open(D + '/new_solver.json')) if os.path.exists(D + '/new_solver.json') else {}
if REP:
    ws = wb.create_sheet('New levels (50)', 1)
    NC = [('#', 6), ('New image', 14), ('New level', 10), ('Shape', 12), ('Line style', 11), ('Difficulty', 11), ('Replaces', 10), ('Old image', 14),
          ('Target tapes', 8), ('New tapes', 8), ('Δ tapes', 8), ('Target blockers', 9), ('New blockers', 9), ('Δ blockers', 9),
          ('Target rounds', 8), ('New rounds', 8), ('Δ rounds', 8), ('Big balls', 7), ('Free at start', 8), ('Round sizes', 22), ('Crossings', 9), ('Tolerance', 9), ('Solver', 10)]
    for c, (h, w) in enumerate(NC, 1):
        cell = ws.cell(1, c, h); cell.fill = HDR; cell.font = HF; cell.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[1].height = 32; ws.freeze_panes = 'D2'
    pct = lambda a, b: f'{(a - b) / b * 100:+.0f}%' if b else ''
    for r, i in enumerate(range(1, 51), 2):
        e = REP.get(str(i))
        if not e:
            ws.cell(r, 1, i); ws.cell(r, 3, '(kept)'); ws.cell(r, 7, order[i - 1]); ws.row_dimensions[r].height = TH * 0.78
            ws.add_image(thumb(order[i - 1]), f'H{r}'); continue
        nm = e['name']; sN = S.get(nm, {}); (t, b, k) = e['target']; T, B, K = sN['tapes'], sN['edges'], sN['rounds']
        vals = [i, None, nm, e['shape'], e.get('style', ''), DIFF[e['diff']], e['replaces'], None, t, T, pct(T, t), b, B, pct(B, b), k, K, pct(K, k),
                e.get('big', 0), sN.get('free0', ''), ' '.join(map(str, sN.get('roundSizes', []))), sN.get('crossings', ''), '±%d%%' % round(e.get('tol', 0.15) * 100), SOLV.get(nm, 'ok')]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r, c, v); cell.alignment = Alignment(vertical='center', wrap_text=c == 20); cell.border = Border(bottom=thin)
            if c == 6: cell.fill = PatternFill('solid', fgColor=DFILL[e['diff']])
        ws.row_dimensions[r].height = TH * 0.78
        ws.add_image(thumb(nm), f'B{r}'); ws.add_image(thumb(e['replaces']), f'H{r}')
    if 'origOrder' in C: sheet(wb.create_sheet('Original main order (400)'), C['origOrder'], lambda i, nm: i)
wb.save(ROOT + '/docs/Line-Tangle-Levels.xlsx')
print('ok', os.path.getsize(ROOT + '/docs/Line-Tangle-Levels.xlsx'))
