"""Moscow surface transport (bus, tram, trolleybus) as a GTFS-equivalent route table, from data.mos.ru open data
(Moscow city government, CC BY 4.0, https://data.mos.ru/): routes ('linhas', snapshot 12 Nov 2026), trips
('viagens', current version), service calendars ('calendario'), plus the stops per route from 26_moscow_surface_stops.py.
- Trips: the current trips table covers every current route (all 964 route codes of 'linhas'); the historical
  version (11 Aug 2026) is only needed to match the stop_times table, which is not used here, so it is ignored.
- Service level = trips per week in the busiest direction ('Direction of trip'), counting each day of the
  reference week Mon 16 - Sun 22 Nov 2026 (same week as every GTFS city) on which the trip's calendar runs
  (weekday flag set and start date <= day <= end date).
- Mode weights as in 08_gtfs.py: tram 2, bus and trolleybus 1 (data.mos.ru type 5 = trolleybus, GTFS type 11).
- Routes without registry stops (about 16%): their trip counts are carried to OSM route groups of the same mode
  and number whose stops lie mostly (>= 60%) within 60 m of a data.mos.ru stop, so the OSM copy of the route is
  timed instead of getting the imputed median; OSM variants of one number are merged into one route. Written as <city>_route_stops_osm_dm.parquet for 08d_hybrid.py.
Outputs: $MS_WORK/transit/moscow_route_stops.parquet, moscow_route_stops_osm_dm.parquet,
data/moscow_datamos/surface_gtfs_audit.json"""
import json, datetime as dt, numpy as np, pandas as pd
from scipy.spatial import cKDTree
B=__import__('os').environ.get('MS_BASE','.'); D=f'{B}/data/moscow_datamos'; T=__import__('os').environ.get('MS_WORK','work')+'/transit'
rd=lambda f: pd.read_csv(f,sep=';',skiprows=[1],dtype=str)
L=rd(f'{D}/linhas.csv'); V=rd(f'{D}/ex2/transporte_viagens_GTFS.csv'); C=rd(f'{D}/calendario.csv')
REF=dt.date(2026,11,16); DAYS=[REF+dt.timedelta(days=i) for i in range(7)]
WD=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
C=C.drop_duplicates('Code list of dates'); s=pd.to_datetime(C['Start date of trip']).dt.date; e=pd.to_datetime(C['End date of trip']).dt.date
C['days']=sum(((C[WD[i]]=='1')&(s<=d)&(e>=d)).astype(int) for i,d in enumerate(DAYS))
V['days']=V['Code list of dates'].map(C.set_index('Code list of dates').days).fillna(0)
rdir=V.groupby(['Route code','Direction of trip']).days.sum()
tw=rdir.groupby(level=0).max()
TYP={'3':(3,1.0,'bus'),'0':(0,2.0,'tram'),'5':(11,1.0,'trolleybus')}
L['route_type']=L['Type of route'].map(lambda t:TYP[t][0]); L['mode_w']=L['Type of route'].map(lambda t:TYP[t][1]); L['mode']=L['Type of route'].map(lambda t:TYP[t][2])
L['trips_week']=L['Route code'].map(tw).fillna(0); L['line']=L['Number of the route'].str.strip()
S=pd.read_parquet(f'{T}/moscow_surface_stops.parquet').dropna(subset=['route_code'])
rs=S.merge(L[['Route code','route_type','mode_w','trips_week','line']],left_on='route_code',right_on='Route code')
rs=rs[rs.trips_week>0].drop_duplicates(['route_code','stop_code'])
out=pd.DataFrame({'route_uid':'datamos:'+rs.route_code,'stop_id':rs.stop_code.astype(str),'stop_lon':rs.lon,'stop_lat':rs.lat,
                  'route_type':rs.route_type.astype(str),'mode_w':rs.mode_w,'trips_week':rs.trips_week,'line':rs.line,'feed':'datamos','gap':0})
out.to_parquet(f'{T}/moscow_route_stops.parquet')
# routes without registry stops -> time the OSM copy of the route (same mode and number, stops on data.mos.ru stops)
nost=L[(L.trips_week>0)&~L['Route code'].isin(rs.route_code)]
P=rd(f'{D}/paradas.csv'); c=P.Centroid.str.extract(r'(-?\d+\.\d+),\s*(-?\d+\.\d+)').astype(float)
kx=111320*np.cos(np.radians(55.75)); ky=110540; tr=cKDTree(np.c_[c[0]*kx,c[1]*ky])
o=pd.read_parquet(f'{T}/moscow_route_stops_osm_ph.parquet')
o['near']=tr.query(np.c_[o.stop_lon*kx,o.stop_lat*ky],k=1)[0]<=60
key=dict(zip(nost['mode']+'|'+nost.line.str.lower(),nost.trips_week))
og=o.groupby('route_uid').agg(route=('route','first'),line=('line','first'),near=('near','mean'),fs=('freq_source','first'))
og['k']=og.route+'|'+og.line.fillna('').str.strip().str.lower()
hit=og[og.k.isin(key)&(og.near>=0.6)&og.route.isin(['bus','tram','trolleybus'])]
first={}
for ru,k in hit.k.items():   # variants of one route number become one route (union of their stops)
    m=o.route_uid==ru; first.setdefault(k,ru); o.loc[m,'trips_week']=key[k]; o.loc[m,'freq_source']='datamos_via_osm_ref'; o.loc[m,'route_uid']=first[k]
o=o.drop_duplicates(['route_uid','stop_id'])
o.drop(columns='near').to_parquet(f'{T}/moscow_route_stops_osm_dm.parquet')
a={'ref_week':[str(DAYS[0]),str(DAYS[-1])],'trips_rows':len(V),'routes_in_linhas':len(L),'routes_with_trips_in_ref_week':int((L.trips_week>0).sum()),
   'routes_with_stops_and_trips':int(out.route_uid.nunique()),'by_mode':rs.drop_duplicates('route_code').route_type.astype(str).value_counts().to_dict(),
   'median_trips_week_busiest_dir':{m:float(L[(L['mode']==m)&(L.trips_week>0)].trips_week.median()) for m in ('bus','tram','trolleybus')},
   'routes_without_registry_stops':int(len(nost)),'timed_via_osm_copy':int(hit.k.nunique()),'osm_groups_timed':int(len(hit)),
   'osm_groups_replaced_from':hit.fs.value_counts().to_dict()}
json.dump(a,open(f'{D}/surface_gtfs_audit.json','w'),indent=1); print(json.dumps(a,indent=1))
