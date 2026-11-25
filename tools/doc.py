# print readable class docs: python doc.py Class1 Class2 ...  (or prefix*)
import json,sys
C=json.load(open('classes.json'))
def show(k):
    c=C[k]; print('=== %s : %s'%(k,c['parent']), c.get('doc',''))
    for f in c['fields']:
        if f['a']&0x10: continue
        ser='SerializeField' in f['ca'] or (f['a']&7)==6
        print('  %s%s %s%s%s'%('*' if ser else ' ',f['n'],f['t'],(' ['+f['hdr']+']') if 'hdr' in f else '',(' -- '+f['tip']) if 'tip' in f else ''))
for a in sys.argv[1:]:
    if a.endswith('*'):
        for k in sorted(C):
            if k.startswith(a[:-1]) and '<' not in k and '/' not in k: show(k)
    else: show(a)
