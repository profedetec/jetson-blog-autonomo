import re,sys,statistics as st,collections
from datetime import datetime
runs=[];cur=None
for line in open(sys.argv[1],errors='replace'):
    m=re.match(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',line)
    ts=datetime.strptime(m.group(1),'%Y-%m-%d %H:%M:%S') if m else None
    if 'SALON DE TEC' in line:
        cur={'start':ts,'end':ts,'out':'sin desenlace','words':None,'model':None,'refresh':True,'retries':0,'dry':False};runs.append(cur);continue
    if not cur: continue
    if ts: cur['end']=ts
    if 'omitido (--no-refresh)' in line: cur['refresh']=False
    if 'dry-run' in line.lower() or 'DRY' in line: cur['dry']=True
    mm=re.search(r'Borrador: (\d+) palabras',line)
    if mm: cur['words']=int(mm.group(1))
    mm=re.search(r'(?:redactado con|Modelo usado|con el modelo|vía) ([\w./:-]+)',line)
    if mm and cur['model'] is None: cur['model']=mm.group(1)
    if 'Corto (' in line: cur['retries']+=1
    if 'Artículo publicado correctamente' in line: cur['out']='publicado'
    elif 'Ningún modelo produjo' in line and '[ERROR]' in line: cur['out']='redacción insuficiente'
    elif 'rechaza las credenciales' in line and '[ERROR]' in line: cur['out']='login/red'
    elif re.search(r'L[íi]mite diario|cuota diaria',line) and cur['out']=='sin desenlace': cur['out']='cuota diaria'
    elif 'Ningún candidato' in line or 'No hay tweets' in line: cur['out']='sin candidatos'
    elif '[ERROR]' in line and cur['out']=='sin desenlace': cur['out']='otro error: '+line[30:90].strip()
print('corridas',len(runs))
cron=[r for r in runs if r['start'].minute<=1 and r['start'].hour in (0,6,12,18) and r['refresh']]
for name,R in (('todas',runs),('cron',cron)):
    c=collections.Counter(r['out'] for r in R); print(name,len(R),c.most_common())
pub=[r for r in cron if r['out']=='publicado']
d=[(r['end']-r['start']).total_seconds()/60 for r in pub]
print('duración publicadas min: mediana %.1f media %.1f p10 %.1f p90 %.1f max %.1f'%(st.median(d),st.mean(d),sorted(d)[len(d)//10],sorted(d)[9*len(d)//10],max(d)))
w=[r['words'] for r in pub if r['words']]
print('palabras: n %d mediana %d media %.0f min %d max %d sd %.0f'%(len(w),st.median(w),st.mean(w),min(w),max(w),st.stdev(w)))
print('reintentos por corto en publicadas',sum(r['retries'] for r in pub))
bymonth=collections.defaultdict(collections.Counter)
for r in cron: bymonth[r['start'].strftime('%Y-%m')][r['out']]+=1
for k in sorted(bymonth): print(k,dict(bymonth[k]))
# first and last fail dates
for o in ('redacción insuficiente','login/red'):
    xs=[r['start'] for r in cron if r['out']==o]; 
    if xs: print(o,xs[0],xs[-1])
print('primer',runs[0]['start'],'ultimo',runs[-1]['start'])
print('--- duraciones reales')
runs2=[];cur=None
for line in open(sys.argv[1],errors='replace'):
    m=re.match(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',line)
    ts=datetime.strptime(m.group(1),'%Y-%m-%d %H:%M:%S') if m else None
    if 'SALON DE TEC' in line: cur={'s':ts,'p2':None,'p3':None,'p4':None,'pub':None};runs2.append(cur);continue
    if not cur or not ts: continue
    for k,pat in (('p2','Paso 2'),('p3','Paso 3'),('p4','Paso 4'),('pub','Artículo publicado')):
        if pat in line and cur[k] is None: cur[k]=ts
ok=[r for r in runs2 if r['pub'] and r['p2'] and r['p3'] and r['p4']]
def q(xs):
    xs=sorted(xs); return 'n=%d mediana %.1f media %.1f p90 %.1f max %.1f'%(len(xs),st.median(xs),st.mean(xs),xs[int(.9*len(xs))],xs[-1])
print('total (min)',q([(r['pub']-r['s']).total_seconds()/60 for r in ok]))
print('refresh engagement (min)',q([(r['p2']-r['s']).total_seconds()/60 for r in ok]))
print('redaccion (s)',q([(r['p4']-r['p3']).total_seconds() for r in ok]))
print('publicacion (s)',q([(r['pub']-r['p4']).total_seconds() for r in ok]))
# slots
from datetime import timedelta
t=datetime(2026,8,20,18);slots=[]
while t<=datetime(2026,10,13,6): slots.append(t); t+=timedelta(hours=6)
have=set(r['start'].replace(minute=0,second=0) for r in cron)
miss=[s for s in slots if s not in have]
print('slots esperados',len(slots),'faltantes',len(miss)); print([s.strftime('%m-%d %H') for s in miss])
post=[r for r in cron if r['start']>=datetime(2026,8,26,12)]
print('desde 26-ago 12h', collections.Counter(r['out'] for r in post))
pre=[r for r in cron if r['start']<datetime(2026,8,26,12)]
print('antes 26-ago 12h',len(pre),collections.Counter(r['out'] for r in pre))
w2=[r['words'] for r in pub if r['words'] and r['words']<800]; print('publicadas <800 palabras',len(w2))
