# list method names of classes (metadata v31): python methods31.py meta.dat Class.Full.Name ...
import struct,sys
b=open(sys.argv[1],'rb').read()
H=struct.unpack_from('<62i',b,8); sec=[(H[2*i],H[2*i+1]) for i in range(31)]
S_OFF=sec[2][0]
def s(i):
    e=b.index(b'\0',S_OFF+i); return b[S_OFF+i:e].decode('utf8','replace')
def rows(k,fmt):
    off,size=sec[k]; sz=struct.calcsize(fmt); return [struct.unpack_from(fmt,b,off+i*sz) for i in range(size//sz)]
TD=rows(19,'<IIiiiiiIiiiiiiii'+'H'*8+'II'); MD=rows(5,'<IiiIiiIHHHH'); PD=rows(7,'<Iii') 
for i,t in enumerate(TD):
    ns=s(t[1]); n=s(t[0]); full=(ns+'.' if ns else '')+n
    if full in sys.argv[2:] or any(a.endswith('*') and full.startswith(a[:-1]) for a in sys.argv[2:]):
        print('==',full)
        print('  ',', '.join(s(MD[k][0]) for k in range(t[9],t[9]+t[16])))
