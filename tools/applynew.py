# Put the generated levels new1..newN at the front of the main play order (data/config.json).
# The original order is kept as "origOrder"; every generated level is solver-checked first.
import json, os, glob, subprocess, sys
ROOT = os.path.join(os.path.dirname(__file__), '..')
cfgp = ROOT + '/data/config.json'
C = json.load(open(cfgp, encoding='utf8'))
orig = C.setdefault('origOrder', list(C['order']))
rep = json.load(open(ROOT + '/docs/levels/new_report.json'))
names = []
for i in range(1, 51):
    r = rep.get(str(i))
    if not r: print('missing', i); names.append(orig[i - 1]); continue
    names.append(r['name'])
    C['diff'][r['name']] = r['diff']
out = subprocess.run(['node', ROOT + '/tools/solve.mjs'] + [n for n in names if n.startswith('new')], capture_output=True, text=True).stdout
print(out.strip().splitlines()[-1])
if 'stuck 0' not in out: sys.exit('solver found stuck levels:\n' + out)
C['order'] = names + orig[50:]
json.dump(C, open(cfgp, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
print('order[:52] =', C['order'][:52])
