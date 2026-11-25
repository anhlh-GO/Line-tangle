import fs from 'fs';
const n=process.argv[2]; const L=JSON.parse(fs.readFileSync('data/levels/'+n+'.json'));
function sample(segs){const P=[];segs.forEach(([x0,y0,x1,y1,x2,y2,x3,y3],k)=>{const len=Math.hypot(x1-x0,y1-y0)+Math.hypot(x2-x1,y2-y1)+Math.hypot(x3-x2,y3-y2);const m=Math.max(4,Math.ceil(len/0.03));for(let i=k?1:0;i<=m;i++){const t=i/m,u=1-t;P.push([u*u*u*x0+3*u*u*t*x1+3*u*t*t*x2+t*t*t*x3,u*u*u*y0+3*u*u*t*y1+3*u*t*t*y2+t*t*t*y3])}});return P}
const T=L.tapes.map(d=>({id:d.id.slice(-3),P:sample(d.segs),r0:0.2*d.ev,r1:0.2*d.eev}));
// min clearance for each tape/dir vs every other ball (all tapes present)
const rows=[];
for(const t of T)for(const dir of [1,-1]){const pts=dir>0?t.P:[...t.P].reverse();const rm=0.2*(dir>0?t.r0:t.r1)/0.2;const bl=[];
 for(const u of T)if(u!==t)for(const [q,r] of [[u.P[0],u.r0],[u.P[u.P.length-1],u.r1]]){let md=1e9;for(const p of pts)md=Math.min(md,Math.hypot(p[0]-q[0],p[1]-q[1]));const pen=rm+r-md;if(pen>0)bl.push(u.id+':'+pen.toFixed(3))}
 rows.push(t.id+(dir>0?'+':'-')+' '+bl.join(' '))}
console.log(rows.join('\n'))
