# export every level bundle -> data/levels/<name>.json  (world-space bezier segments per tape)
import UnityPy,sys,json,glob,re,os
import numpy as np
src=sys.argv[1]; out=sys.argv[2]; os.makedirs(out,exist_ok=True)
only=sys.argv[3:] 
def qm(q):
    x,y,z,w=q['x'],q['y'],q['z'],q['w']
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def trs(t):
    M=np.eye(4); p=t['m_LocalPosition']; s=t['m_LocalScale']
    M[:3,:3]=qm(t['m_LocalRotation'])*np.array([s['x'],s['y'],s['z']]); M[:3,3]=[p['x'],p['y'],p['z']]; return M
def v3(d): return np.array([d['x'],d['y'],d['z']])
idx={}
for p in glob.glob(src+'/level_assets_*.bundle'):
    m=re.search(r'level_assets_((level)?\d+)_',p); idx[m.group(1)]=p
names=only or sorted(idx,key=lambda s:int(re.sub(r'\D','',s)))
for name in names:
    env=UnityPy.load(idx[name]); objs={o.path_id:o for o in env.objects}
    scr={o.path_id:o.read().m_ClassName for o in env.objects if o.type.name=='MonoScript'}
    T={};GO={};MB={}
    for o in env.objects:
        if o.type.name in('Transform','RectTransform'): T[o.path_id]=o.read_typetree()
        elif o.type.name=='GameObject': GO[o.path_id]=o.read_typetree()
        elif o.type.name=='MonoBehaviour':
            t=o.read_typetree(); MB[o.path_id]=(scr.get(t['m_Script']['m_PathID']),t)
    g2t={t['m_GameObject']['m_PathID']:pid for pid,t in T.items()}
    W={}
    def world(tp):
        if tp in W: return W[tp]
        t=T[tp]; f=t['m_Father']['m_PathID']
        M=trs(t) if not f else world(f)@trs(t); W[tp]=M; return M
    gomb={}
    for pid,(c,t) in MB.items(): gomb.setdefault(t['m_GameObject']['m_PathID'],{})[c]=(pid,t)
    tapes=[]; tut=None; boardDiff=0
    for g,cs in gomb.items():
        if 'TapeBoardController' in cs: boardDiff=cs['TapeBoardController'][1]['initialDifficulty']
        if 'TapeLevelTutorialAuthoring' in cs:
            tt=cs['TapeLevelTutorialAuthoring'][1]; tut={'type':tt['tutorialType'],'text':tt['instructionText'],'delay':tt['tutorialStartDelay'],'target':tt['targetTape']['m_PathID']}
    for g,cs in gomb.items():
        if 'TapePathAuthoring' not in cs: continue
        a=cs['TapePathAuthoring'][1]; ctl=cs['TapePathController'][1]
        pathMB=MB[ctl['path']['m_PathID']][1]; sc_pid=pathMB['splineContainer']['m_PathID']; sc=MB[sc_pid][1]
        scGo=sc['m_GameObject']['m_PathID']; M=world(g2t[scGo])
        spl=sc['m_Splines'][pathMB['splineIndex']]; K=spl['m_Knots']; closed=spl['m_Closed']
        def P(v): return (M@np.append(v,1))[:3]
        segs=[]; n=len(K)
        for i in range(n-1+(1 if closed else 0)):
            k0=K[i];k1=K[(i+1)%n]
            p0=v3(k0['Position']);p3=v3(k1['Position'])
            p1=p0+qm(k0['Rotation']['value'])@v3(k0['TangentOut']); p2=p3+qm(k1['Rotation']['value'])@v3(k1['TangentIn'])
            segs.append([round(float(c),4) for p in (P(p0),P(p1),P(p2),P(p3)) for c in p[:2]])
        zs=[float(P(v3(k['Position']))[2]) for k in K]
        rib=MB[cs['TapePathView'][1]['ribbonProperties']['m_PathID']][1]
        tgo=GO[g]; tapes.append({'id':a['tapeId'],'pid':g,'color':a['fixedColorId'],'cid':a['colorId'],'w':round(a['tapeWidth'],4),'speed':a['baseMoveSpeed'],'sweep':round(a['baseSweepRadius'],4),'click':round(a['baseClickRadius'],4),
            'ev':round(a['endpointVisualSize'],3),'eev':round(a['endpointEndVisualSize'],3),'eo':round(a['endpointVisualOffset']['y'],3),'epo':round(a['endpointPathOffset'],3),'gs':round(a['appliedGeometryScale'],3),
            'enc':a['isEncouragementPath'],'closed':closed,'segs':segs,'z':round(sum(zs)/len(zs),3),'on':tgo['m_IsActive']})
    if tut:
        for t in tapes:
            tg=MB.get(tut['target']) or T.get(tut['target'])
            if tg and (tg[1] if isinstance(tg,tuple) else tg)['m_GameObject']['m_PathID']==t['pid']: tut['tape']=t['id']
        tut.pop('target')
    for t in tapes: t.pop('pid')
    tapes.sort(key=lambda t:t['id'])
    json.dump({'name':name,'diff':boardDiff,'tut':tut,'tapes':tapes},open(f'{out}/{name}.json','w'),separators=(',',':'))
    print(name,len(tapes),tut or '')
