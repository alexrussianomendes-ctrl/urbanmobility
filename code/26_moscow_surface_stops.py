"""Stops of each Moscow surface-transport route (bus, tram, trolleybus) from data.mos.ru open data (CC BY 4.0):
the route registry ('registro_linhas': stop names along each direction and the route track) and the stop list
('paradas': stop code, name, transport type, point). The stop_times table would give the exact assignment but its
file is too large for the download route available here, so stops are assigned by name and position:
a stop belongs to a route when its normalised name is one of the route's listed stop names, its transport type
includes the route's mode, and it lies within 60 m of the route track. Routes are then linked to the timetable
route table ('linhas': route code) by route number + mode.
Output: $MS_WORK/transit/moscow_surface_stops.parquet (route_code, number, mode, stop_code, lon, lat)
and data/moscow_datamos/surface_stops_audit.json."""
import re, json, numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import MultiLineString
B=__import__('os').environ.get('MS_BASE','.'); D=f'{B}/data/moscow_datamos'; T=__import__('os').environ.get('MS_WORK','work')+'/transit'
rd=lambda f: pd.read_csv(f'{D}/{f}',sep=';',skiprows=[1],dtype=str)
def norm(s):
    s=str(s).lower().replace('ё','е'); s=re.sub(r'[«»"\'().,]',' ',s); return re.sub(r'\s+',' ',s).strip()
R=rd('registro_linhas.csv'); P=rd('paradas.csv'); L=rd('linhas.csv')
TM={'Автобус':'bus','Трамвай':'tram','Троллейбус':'trolleybus'}; LT={'3':'bus','0':'tram','5':'trolleybus'}
R['mode']=R['Type of transport'].map(TM)
def geom(s):
    j=s[s.index('coordinates=')+12:].rstrip(']'); j=j+']'*(j.count('[')-j.count(']'))
    return MultiLineString(json.loads(j))
R['geometry']=R.Geodata.map(geom); R=gpd.GeoDataFrame(R,crs=4326)
c=P.Centroid.fillna(P.Geodata).str.extract(r'(-?\d+\.\d+),\s*(-?\d+\.\d+)').astype(float)
P['lon']=c[0]; P['lat']=c[1]; P['nm']=P['Stop name'].map(norm)
P['modes']=P['Transport type'].fillna('').map(lambda t: {TM[k] for k in TM if k in t})
P=gpd.GeoDataFrame(P,geometry=gpd.points_from_xy(P.lon,P.lat),crs=4326)
crs=32637; Rm=R.to_crs(crs); Pm=P.to_crs(crs)
sidx=Pm.sindex; out=[]; aud={'routes':len(R),'no_stop':0}
for i,r in Rm.iterrows():
    names=set()
    for col in ('Trassa sledovaniya marshruta (pryamoe napravlenie)','Trassa sledovaniya marshruta (obratnoe napravlenie)'):
        names|={norm(x) for x in re.split(r'\s+-\s+(?=[^\s])',str(r[col])) if x.strip()}
    cand=Pm.iloc[sidx.query(r.geometry.buffer(60),predicate='intersects')]
    cand=cand[cand.nm.isin(names)&cand.modes.map(lambda m: r['mode'] in m)]
    if not len(cand): aud['no_stop']+=1; continue
    out.append(pd.DataFrame({'reg_code':r.Code,'number':r['Route number'].strip(),'mode':r['mode'],'stop_code':cand['Stop code'].values,
                             'lon':cand.lon.values,'lat':cand.lat.values,'n_names':len(names)}))
S=pd.concat(out,ignore_index=True)
L['mode']=L['Type of route'].map(LT); L['k']=L['Number of the route'].str.strip().str.lower()+'|'+L['mode']
S['k']=S.number.str.lower()+'|'+S['mode']
S=S.merge(L[['k','Route code']].rename(columns={'Route code':'route_code'}),on='k',how='left')
per=S.groupby('reg_code').agg(n=('stop_code','size'),names=('n_names','first'))
aud.update({'routes_with_stops':int(per.shape[0]),'median_stops_per_route':float(per.n.median()),
            'median_share_of_listed_names_found':float((per.n/per.names).median()),
            'routes_linked_to_timetable':int(S.dropna(subset=['route_code']).reg_code.nunique()),
            'timetable_routes':len(L),'timetable_routes_with_stops':int(L.k.isin(S.k).sum())})
S.drop(columns='k').to_parquet(f'{T}/moscow_surface_stops.parquet')
json.dump(aud,open(f'{D}/surface_stops_audit.json','w'),indent=1); print(aud)
