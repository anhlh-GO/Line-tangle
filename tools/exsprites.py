# export every Sprite as its own image -> assets/sp/<name>.webp ; data/sprites.json {name:{w,h,b:[l,b,r,t],ppu}}
import UnityPy, sys, json, os, glob, re
src = sys.argv[1]; out = sys.argv[2]; os.makedirs(out + '/assets/sp', exist_ok=True)
files = [f for f in glob.glob(src + '/**/*.bundle', recursive=True) if 'level_assets_' not in os.path.basename(f) or 'shared_level' in f]
env = UnityPy.load(*files)
SP = {}
def safe(n): return re.sub(r'[\\/:*?"<>|]', '_', n)
for o in env.objects:
    if o.type.name != 'Sprite': continue
    try:
        d = o.read(); n = d.m_Name
        if n in SP: continue
        im = d.image
        if im.width == 0: continue
        fn = safe(n) + '.webp'
        im.save(out + '/assets/sp/' + fn, 'WEBP', quality=92, method=6)
        b = d.m_Border
        SP[n] = {'f': fn, 'w': round(d.m_Rect.width), 'h': round(d.m_Rect.height), 'b': [round(b.x), round(b.y), round(b.z), round(b.w)], 'ppu': d.m_PixelsToUnits}
    except Exception as e:
        print('fail', o.path_id, e)
json.dump(SP, open(out + '/data/sprites.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
print('sprites', len(SP))
