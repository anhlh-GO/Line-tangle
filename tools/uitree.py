import json,sys
def p(n,d):
    s='  '*d+n['n']+(' OFF' if n.get('off') else '')
    if 'r' in n: s+=' r'+str(n['r'])
    if 'img' in n: s+=' IMG(%s %s t%s)'%(n['img'].get('sp'),n['img']['c'],n['img'].get('type'))
    if 'txt' in n: s+=' TXT(%r fs%s %s)'%(n['txt']['s'][:30],n['txt']['fs'],n['txt']['c'])
    for k in('loc','btn','spine','lay','alpha','cls','s','mask'):
        if k in n: s+=' %s=%s'%(k,n[k])
    print(s[:260])
    for c in n.get('ch',[]): p(c,d+1)
for n in json.load(open(sys.argv[1],encoding='utf8')): p(n,0)
