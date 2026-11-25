# export spine (skel/atlas/png) -> assets/spine, audio clips -> assets/audio, fonts -> assets/fonts
import UnityPy, sys, os, glob
src = sys.argv[1]; out = sys.argv[2]
for d in ('spine', 'audio', 'fonts'): os.makedirs(f'{out}/assets/{d}', exist_ok=True)
files = (glob.glob(src + '/ui_assets_assets/**/*.bundle', recursive=True) + glob.glob(src + '/shared_level*')
         + glob.glob(src + '/audio*/**/*.bundle', recursive=True) + glob.glob(src + '/audioball*')
         + glob.glob(src + '/shared_fonts_assets_assets/**/*.bundle', recursive=True))
env = UnityPy.load(*files)
pages = set()
for o in env.objects:
    tn = o.type.name
    if tn == 'TextAsset':
        d = o.read()
        if d.m_Name.endswith(('.skel', '.atlas')):
            b = d.m_Script.encode('utf-8', 'surrogateescape') if isinstance(d.m_Script, str) else bytes(d.m_Script)
            open(f'{out}/assets/spine/{d.m_Name}', 'wb').write(b)
            if d.m_Name.endswith('.atlas'):
                pages.add(b.decode('utf8', 'replace').strip().splitlines()[0].strip())
for o in env.objects:
    if o.type.name == 'Texture2D':
        d = o.read()
        if d.m_Name + '.png' in pages:
            d.image.save(f'{out}/assets/spine/{d.m_Name}.png')
    elif o.type.name == 'AudioClip':
        d = o.read()
        for name, data in d.samples.items():
            fn = f'{out}/assets/audio/{d.m_Name}' + os.path.splitext(name)[1]
            open(fn, 'wb').write(data); print('audio', fn, len(data))
    elif o.type.name == 'Font':
        d = o.read()
        if d.m_FontData:
            fd = bytes(d.m_FontData)
            ext = '.otf' if fd[:4] == b'OTTO' else '.ttf'
            open(f'{out}/assets/fonts/{d.m_Name}{ext}', 'wb').write(fd); print('font', d.m_Name, len(fd))
print('pages', pages)
