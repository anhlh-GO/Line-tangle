# IL2CPP global-metadata v31 reader -> classes.json (fields, parents, attrs) [+ methods.json]
import struct,sys,pickle,json,os
b=open(sys.argv[1],'rb').read(); T=pickle.load(open(sys.argv[2],'rb'))
H=struct.unpack_from('<62i',b,8)
sec=[(H[2*i],H[2*i+1]) for i in range(31)]
S_OFF=sec[2][0]
def s(i):
    e=b.index(b'\0',S_OFF+i); return b[S_OFF+i:e].decode('utf8','replace')
def rows(k,fmt):
    off,size=sec[k]; sz=struct.calcsize(fmt); return [struct.unpack_from(fmt,b,off+i*sz) for i in range(size//sz)]
# typedef: 0 name,1 ns,2 byval,3 decl,4 parent,5 elem,6 genc,7 flags,8 fieldStart,9 methodStart,10 ev,11 prop,12 nested,13 iface,14 vt,15 ioff,
#          16 mcount,17 pcount,18 fcount,19 ecount,20 ncount,21 vtcount,22 icount,23 iocount,24 bits,25 token
TD=rows(19,'<IIiiiiiIiiiiiiii'+'H'*8+'II')
FD=rows(11,'<IiI')
MFMT=os.environ.get('MFMT','<IiiIiiIHHHH')
MD=rows(5,MFMT)
IM=rows(20,'<IIiIiIiIII')
NT=rows(15,'<i')
types=T['types']; gen=T['gen']; arr=T['arr']
tdname=[]
for t in TD:
    ns=s(t[1]); n=s(t[0]); tdname.append((ns+'.' if ns else '')+n)
decl={}
for i,t in enumerate(TD):
    for k in range(t[12],t[12]+t[20]): decl[NT[k][0]]=i
def full(i,d=0):
    if i in decl and d<10: return full(decl[i],d+1)+'/'+s(TD[i][0])
    return tdname[i]
tdname=[full(i) for i in range(len(TD))]
PRIM={1:'void',2:'bool',3:'char',4:'sbyte',5:'byte',6:'short',7:'ushort',8:'int',9:'uint',0xa:'long',0xb:'ulong',0xc:'float',0xd:'double',0xe:'string',0x18:'IntPtr',0x19:'UIntPtr',0x1c:'object'}
def tname(ti,depth=0):
    if ti<0 or depth>20: return '?'
    d,bits=types[ti]; t=(bits>>16)&0xff
    if t in PRIM: return PRIM[t]
    if t in (0x11,0x12): return tdname[d] if d<len(tdname) else '?td%d'%d
    if t==0x1d: return tname(arr[ti],depth+1)+'[]'
    if t==0x14: return tname(arr.get(ti,-1),depth+1)+'[,]' if ti in arr else '?[,]'
    if t==0x15:
        g,args=gen[ti]; return tname(g,depth+1)+'<'+','.join(tname(a,depth+1) for a in args)+'>'
    if t in (0x13,0x1e): return 'T'
    return '?t%x'%t
ADR=rows(25,'<II'); AD_OFF=sec[24][0]
def cu(o):
    x=b[o]
    if x&0x80==0: return x,1
    if x&0xc0==0x80: return ((x&0x3f)<<8)|b[o+1],2
    if x&0xe0==0xc0: return ((x&0x1f)<<24)|(b[o+1]<<16)|(b[o+2]<<8)|b[o+3],4
    return struct.unpack_from('<I',b,o+1)[0],5
ADI={}
for img in IM:
    for k in range(img[8],img[8]+img[9]): ADI[(img[0],ADR[k][0])]=k
def ci(o):
    v,l=cu(o)
    if v==0xffffffff: return -2**31,l
    return (-(v>>1)-1 if v&1 else v>>1),l
class Bad(Exception): pass
def val(o,t=None):
    if t is None:
        t=b[o]; o+=1
        if t==0x55:
            _,l=ci(o); o+=l; t=None
            # enum: underlying assume int32
            return struct.unpack_from('<i',b,o)[0],o+4
    if t==2 or t==4 or t==5: return b[o],o+1
    if t==3 or t==6 or t==7: return struct.unpack_from('<H',b,o)[0],o+2
    if t in(8,9): return struct.unpack_from('<i',b,o)[0],o+4
    if t in(0xa,0xb): return struct.unpack_from('<q',b,o)[0],o+8
    if t==0xc: return round(struct.unpack_from('<f',b,o)[0],5),o+4
    if t==0xd: return struct.unpack_from('<d',b,o)[0],o+8
    if t==0xe:
        n,l=ci(o); o+=l
        if n<0: return None,o
        return b[o:o+n].decode('utf8','replace'),o+n
    if t==0xff:
        n,l=ci(o); o+=l; return 'type%d'%n,o
    raise Bad(t)
ATTRARGS={}
def attrs_for(img,token,args=None):
    k=ADI.get((img[0],token))
    if k is None: return []
    o=AD_OFF+ADR[k][1]; n,l=cu(o); o+=l
    res=[]
    for j in range(n):
        mi=struct.unpack_from('<I',b,o+4*j)[0]
        if mi<len(MD): res.append(tdname[MD[mi][1]] if 0<=MD[mi][1]<len(tdname) else '?')
    if args is not None:
        p=o+4*n
        try:
            for j in range(n):
                ac,l=cu(p); p+=l; fc,l=cu(p); p+=l; pc,l=cu(p); p+=l
                av=[]
                for _ in range(ac):
                    v,p=val(p); av.append(v)
                for _ in range(fc+pc):
                    v,p=val(p); _,l=ci(p); p+=l
                args.append((res[j].split('.')[-1],av))
        except Exception: pass
    return res
tdimg={}
for img in IM:
    for k in range(img[2],img[2]+img[3]): tdimg[k]=img
out={}
for i,t in enumerate(TD):
    img=tdimg.get(i); asm=s(img[0]) if img else ''
    fields=[]
    for k in range(t[8],t[8]+t[18]):
        n,ti,tok=FD[k]
        d,bits=types[ti]; at=bits&0xffff
        aa=[]
        ca=attrs_for(img,tok,aa) if img else []
        fd={'n':s(n),'t':tname(ti),'a':at,'ca':[c.split('.')[-1] for c in ca],'k':(bits>>16)&0xff}
        for an,av in aa:
            if an in('TooltipAttribute','HeaderAttribute') and av: fd['tip' if an[0]=='T' else 'hdr']=av[0]
            if an=='RangeAttribute': fd['rng']=av
        fields.append(fd)
    par=tname(t[4]) if t[4]>=0 else None
    ta=[]
    if img: attrs_for(img,t[25],ta)
    out[tdname[i]]={'asm':asm,'parent':par,'flags':t[7],'fields':fields}
    for an,av in ta:
        if an in('TooltipAttribute','HelpURLAttribute','AddComponentMenu') and av: out[tdname[i]]['doc']=av
json.dump(out,open(sys.argv[3],'w'),indent=0)
for k in sys.argv[4:]:
    print(k,json.dumps(out.get(k))[:1500])
#print('methods sample',[ (s(m[0]),tdname[m[1]] if 0<=m[1]<len(tdname) else m[1]) for m in MD[100:105]])
