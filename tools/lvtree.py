# print hierarchy of a level bundle with transforms + MB summaries
import UnityPy,sys,json
env=UnityPy.load(sys.argv[1]); L=int(sys.argv[2]) if len(sys.argv)>2 else 300
objs={o.path_id:o for o in env.objects}
scr={}
for o in env.objects:
    if o.type.name=='MonoScript': d=o.read(); scr[o.path_id]=d.m_ClassName
gos={};tr={}
for o in env.objects:
    if o.type.name=='GameObject': gos[o.path_id]=o.read_typetree()
for o in env.objects:
    if o.type.name in('Transform','RectTransform'): tr[o.path_id]=o.read_typetree()
def comps(g):
    out=[]
    for c in g['m_Component']:
        pid=c['component']['m_PathID']; o=objs.get(pid)
        if not o: continue
        if o.type.name=='MonoBehaviour':
            t=o.read_typetree(); out.append((scr.get(t['m_Script']['m_PathID'],'?'),t))
        elif o.type.name not in('Transform','RectTransform'):
            try: t=o.read_typetree()
            except: t={}
            out.append((o.type.name,t))
    return out
def r(v):
    if isinstance(v,float): return round(v,3)
    if isinstance(v,dict): return {k:r(x) for k,x in v.items() if k not in('m_GameObject','m_Script','m_Name','m_Enabled','m_ObjectHideFlags','m_CorrespondingSourceObject','m_PrefabInstance','m_PrefabAsset')}
    if isinstance(v,list): return [r(x) for x in v]
    return v
roots=[p for p,t in tr.items() if t['m_Father']['m_PathID']==0]
def walk(p,d):
    t=tr[p]; g=gos[t['m_GameObject']['m_PathID']]
    lp=t['m_LocalPosition'];ls=t['m_LocalScale'];q=t['m_LocalRotation']
    print('  '*d+'%s%s pos(%.3f,%.3f,%.3f) rot(%.3f,%.3f,%.3f,%.3f) s(%.2f,%.2f,%.2f)'%(g['m_Name'],'' if g['m_IsActive'] else ' [OFF]',lp['x'],lp['y'],lp['z'],q['x'],q['y'],q['z'],q['w'],ls['x'],ls['y'],ls['z']))
    for n,c in comps(g):
        print('  '*d+'  - '+n+' '+json.dumps(r(c))[:L])
    for ch in t['m_Children']: walk(ch['m_PathID'],d+1)
for p in roots: walk(p,0)
