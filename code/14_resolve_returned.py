"""Locate the address that walkscore.com actually scored (written by the user in 'observacao') using Overture
addresses, so the model is evaluated at the scored location.
Rules: generic places (neighbourhood, ZIP, city) are excluded from point validation. A returned street address is
matched on normalised street name + postcode (else street only, within 3 km of the requested point), choosing the
candidate whose house number is closest; ranges use their first number. Unresolved rows, and neighbour-number matches more than 300 m from the requested point, are excluded and counted.
Queens-style numbers (84-09) are compared without the hyphen.
Output: data/validation/manual_sample_resolved.csv"""
import re, numpy as np, pandas as pd, geopandas as gpd
V=__import__('os').environ.get('MS_BASE','.')+'/data/validation'; W=__import__('os').environ.get('MS_WORK','work')
F=pd.read_csv(f'{V}/manual_sample_filled.csv')
NM={'Boston':'boston','San Francisco':'sanfrancisco','Seattle':'seattle','Chicago':'chicago','New York':'nyc','Los Angeles':'losangeles'}
SUF={'STREET':'ST','AVENUE':'AVE','AV':'AVE','ROAD':'RD','BOULEVARD':'BLVD','DRIVE':'DR','PLACE':'PL','COURT':'CT','LANE':'LN',
     'TERRACE':'TER','HIGHWAY':'HWY','PARKWAY':'PKWY','SQUARE':'SQ','CIRCLE':'CIR','WAY':'WAY','PLAZA':'PLZ','ALLEY':'ALY'}
DIR={'NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W','NORTHEAST':'NE','NORTHWEST':'NW','SOUTHEAST':'SE','SOUTHWEST':'SW'}
def norm(s):
    s=re.sub(r'[^A-Z0-9 ]',' ',str(s).upper()); w=s.split()
    w=[DIR.get(x,x) for x in w]; w=[SUF.get(x,x) for x in w]
    w=[re.sub(r'^(\d+)(ST|ND|RD|TH)$',r'\1',x) for x in w]
    return ' '.join(w)
def parse(o):
    o=str(o)
    if 'genéric' in o or not o.startswith('Walk Score retornou:'): return None
    m=re.match(r'Walk Score retornou:\s*(.+?)\s*\((.*)\)\s*$',o)
    if not m: return None
    street_part,paren=m.group(1),m.group(2)
    pc=re.findall(r'\b(\d{5})\b',paren); pc=pc[-1] if pc else None
    mm=re.match(r'^(\d+)[A-Z]?(?:-\d+[A-Z]?)?\s+(.+)$',street_part.strip(),re.I)
    if not mm: return {'num':None,'street':norm(street_part),'pc':pc,'raw':street_part}
    return {'num':int(mm.group(1)),'street':norm(mm.group(2)),'pc':pc,'raw':street_part}
rows=[]; cache={}
for _,r in F.iterrows():
    out={'id':r.id,'status':'','r_lat':np.nan,'r_lon':np.nan,'shift_m':np.nan,'returned':''}
    p=parse(r.observacao)
    if pd.isna(r.walk_score): out['status']='sem notas'
    elif p is None: out['status']='local genérico (excluído)'
    elif p['num'] is None: out['status']='sem número (excluído)'; out['returned']=p['raw']
    else:
        c=NM[r.cidade]
        if c not in cache:
            a=pd.read_parquet(f'{W}/ov/addresses_{c}.parquet',columns=['number','street','postcode','geometry'])
            a=a[a.number.notna()&a.street.notna()]
            g=gpd.GeoSeries.from_wkb(a.geometry,crs=4326); a=a.assign(lon=g.x.values,lat=g.y.values)
            a['n']=pd.to_numeric(a.number.astype(str).str.replace('-','',regex=False).str.extract(r'^(\d+)')[0],errors='coerce'); a['s']=a.street.map(norm)   # Queens '84-09' -> 8409
            cache[c]=a
        a=cache[c]; cand=a[a.s==p['street']]
        if p['pc'] is not None and (cand.postcode==p['pc']).any(): cand=cand[cand.postcode==p['pc']]
        kx=111320*np.cos(np.radians(r.lat)); d0=np.hypot((cand.lon-r.lon)*kx,(cand.lat-r.lat)*110540)
        cand=cand[d0<3000]
        if not len(cand): out['status']='não localizado (excluído)'; out['returned']=p['raw']
        else:
            j=(cand.n-p['num']).abs().idxmin(); b=cand.loc[j]
            sh=float(np.hypot((b.lon-r.lon)*kx,(b.lat-r.lat)*110540))
            if b.n!=p['num'] and sh>300: out['status']='incerto: número vizinho a mais de 300 m (excluído)'; out['returned']=p['raw']; rows.append(out); continue
            out.update(status='localizado' if b.n==p['num'] else 'localizado (número vizinho)',r_lat=b.lat,r_lon=b.lon,returned=p['raw'],
                       shift_m=float(np.hypot((b.lon-r.lon)*kx,(b.lat-r.lat)*110540)))
    rows.append(out)
R=F.merge(pd.DataFrame(rows),on='id')
R.to_csv(f'{V}/manual_sample_resolved.csv',index=False)
print(R.status.value_counts().to_string()); print(R.groupby('cidade').status.apply(lambda s:(s.str.startswith('localizado')).sum()).to_string())
print('shift m median',R.shift_m.median().round(0),'p90',R.shift_m.quantile(0.9).round(0),'max',R.shift_m.max().round(0))
print(R[R.status.str.contains('não localizado|sem número')][['id','cidade','returned']].to_string())
