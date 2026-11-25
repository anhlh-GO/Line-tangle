# export UI prefabs -> data/ui/<name>.json (RectTransform tree + Image/Text/Button/Spine/CanvasGroup/Layout) and data/i18n.json
import UnityPy, sys, json, os, glob, re, math
src = sys.argv[1]; out = sys.argv[2]; os.makedirs(out + '/data/ui', exist_ok=True)
files = (glob.glob(src + '/ui_assets_assets/**/*.bundle', recursive=True) + glob.glob(src + '/shared_ui_assets_*.bundle')
         + glob.glob(src + '/repeat_assets_*.bundle') + glob.glob(src + '/shared_fonts_assets_assets/**/*.bundle', recursive=True)
         + glob.glob(src + '/localization*') + glob.glob(src + '/avatar*') + glob.glob(src + '/shared_level*'))
env = UnityPy.load(*files)

for o in env.objects:
    if o.type.name == 'MonoBehaviour':
        try: t = o.read_typetree()
        except Exception: continue
        if t.get('m_Name') == 'I2Languages':
            L = {}
            for term in t['mSource']['mTerms']:
                L[term['Term']] = {'en': term['Languages'][1], 'zh': term['Languages'][0], 't': term['TermType']}
            json.dump(L, open(out + '/data/i18n.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
            print('terms', len(L))

def r3(v): return round(v, 3)
def col(c): return [r3(c['r']), r3(c['g']), r3(c['b']), r3(c['a'])]

def export(sf):
    objs = sf.objects
    T = {pid: o for pid, o in objs.items() if o.type.name in ('RectTransform', 'Transform')}
    def sprite_name(co):
        try:
            d = co.read(); sp = getattr(d, 'm_Sprite', None)
            if sp is None or sp.path_id == 0: return None
            return sp.read().m_Name
        except Exception:
            return '?'
    def walk(pid):
        t = T[pid].read_typetree(); g = objs[t['m_GameObject']['m_PathID']].read_typetree()
        n = {'n': g['m_Name']}
        if not g['m_IsActive']: n['off'] = 1
        if 'm_AnchorMin' in t:
            n['r'] = [r3(t['m_AnchorMin']['x']), r3(t['m_AnchorMin']['y']), r3(t['m_AnchorMax']['x']), r3(t['m_AnchorMax']['y']),
                      r3(t['m_AnchoredPosition']['x']), r3(t['m_AnchoredPosition']['y']), r3(t['m_SizeDelta']['x']), r3(t['m_SizeDelta']['y']),
                      r3(t['m_Pivot']['x']), r3(t['m_Pivot']['y'])]
        s = t['m_LocalScale']
        if (r3(s['x']), r3(s['y'])) != (1, 1): n['s'] = [r3(s['x']), r3(s['y'])]
        q = t['m_LocalRotation']
        if abs(q['z']) > 1e-3: n['rot'] = r3(math.degrees(2 * math.atan2(q['z'], q['w'])))
        for c in g['m_Component']:
            co = objs.get(c['component']['m_PathID'])
            if not co: continue
            tn = co.type.name
            if tn == 'CanvasGroup':
                n['alpha'] = r3(co.read_typetree()['m_Alpha'])
            if tn != 'MonoBehaviour': continue
            try:
                ct = co.read_typetree(); cls = co.read().m_Script.read().m_ClassName
            except Exception:
                continue
            if not ct.get('m_Enabled', 1): continue
            if cls in ('Image', 'RawImage'):
                im = {'c': col(ct['m_Color'])}
                sp = sprite_name(co)
                if sp: im['sp'] = sp
                for k, kk in (('m_Type', 'type'), ('m_FillMethod', 'fm'), ('m_FillAmount', 'fa'), ('m_PreserveAspect', 'pa'), ('m_FillOrigin', 'fo'), ('m_PixelsPerUnitMultiplier', 'ppum')):
                    if k in ct: im[kk] = r3(ct[k]) if isinstance(ct[k], float) else ct[k]
                n['img'] = im
            elif cls == 'Text':
                fd = ct['m_FontData']; fn = None
                try: fn = co.read().m_FontData.m_Font.read().m_Name
                except Exception: pass
                n['txt'] = {'s': ct['m_Text'], 'c': col(ct['m_Color']), 'fs': fd['m_FontSize'], 'al': fd['m_Alignment'], 'st': fd['m_FontStyle'],
                            'bf': fd['m_BestFit'], 'min': fd['m_MinSize'], 'max': fd['m_MaxSize'], 'f': fn, 'ls': r3(fd['m_LineSpacing'])}
            elif cls == 'Localize':
                n['loc'] = ct.get('mTerm') or ct.get('mTermSecondary')
            elif cls in ('Button', 'GameButton'):
                n['btn'] = 1
            elif cls == 'SkeletonGraphic':
                try: sk = co.read().skeletonDataAsset.read().m_Name
                except Exception: sk = None
                n['spine'] = {'sk': sk, 'anim': ct.get('startingAnimation'), 'loop': ct.get('startingLoop'), 'skin': ct.get('initialSkinName'), 'c': col(ct['m_Color'])}
            elif cls in ('HorizontalLayoutGroup', 'VerticalLayoutGroup', 'GridLayoutGroup'):
                p = ct['m_Padding']
                n['lay'] = {'k': cls[0], 'pad': [p['m_Left'], p['m_Right'], p['m_Top'], p['m_Bottom']], 'sp': ct.get('m_Spacing'), 'al': ct['m_ChildAlignment'],
                            'cw': ct.get('m_ChildControlWidth'), 'ch': ct.get('m_ChildControlHeight'), 'ew': ct.get('m_ChildForceExpandWidth'), 'eh': ct.get('m_ChildForceExpandHeight'),
                            'cs': ct.get('m_CellSize')}
            elif cls == 'LayoutElement':
                n['le'] = {k: ct[k] for k in ('m_IgnoreLayout', 'm_MinWidth', 'm_MinHeight', 'm_PreferredWidth', 'm_PreferredHeight', 'm_FlexibleWidth', 'm_FlexibleHeight') if k in ct}
            elif cls in ('Shadow', 'Outline', 'ContinuousTextOutline'):
                d = {k: v for k, v in ct.items() if k not in ('m_GameObject', 'm_Script', 'm_Name', 'm_Enabled')}
                n.setdefault('fx', []).append([cls, json.loads(json.dumps(d))])
            elif cls in ('RectMask2D', 'Mask'):
                n['mask'] = 1
            else:
                n.setdefault('cls', []).append(cls)
        ch = [walk(c['m_PathID']) for c in t['m_Children']]
        if ch: n['ch'] = ch
        return n
    roots = [pid for pid, o in T.items() if o.read_typetree()['m_Father']['m_PathID'] == 0]
    return [walk(p) for p in roots]

for path, f in env.files.items():
    m = re.search(r'([a-z0-9_]+)\.prefab', path)
    if not m: continue
    for cab in f.files.values():
        if not hasattr(cab, 'objects'): continue
        try:
            tree = export(cab)
        except Exception:
            import traceback; traceback.print_exc(); continue
        json.dump(tree, open(out + '/data/ui/' + m.group(1) + '.json', 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
        print('ui', m.group(1), len(json.dumps(tree)))
