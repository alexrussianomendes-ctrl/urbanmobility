"""Hybrid transit supply for cities whose GTFS covers only part of the network (e.g. Tokyo: Toei only; Munich:
no S-Bahn trips; Osaka/Moscow/China: none). Keeps every GTFS route (timetable frequency) and adds the OSM route
groups that are NOT already in the GTFS (same mode weight and >=60% of the OSM route's stop cells shared with one
GTFS route = duplicate). Added OSM routes carry their own frequency source (osm_interval or imputed_mode_median).
Output: $MS_WORK/transit/<city>_route_stops_hybrid.parquet + audit json.
Usage: python 08d_hybrid.py <city> [osm_suffix]"""
import sys, os, json, numpy as np, pandas as pd
city=sys.argv[1]; T=__import__('os').environ.get('MS_WORK','work')+'/transit'; osuf=sys.argv[2] if len(sys.argv)>2 else '_osm'   # e.g. _osm_ph
o=pd.read_parquet(f'{T}/{city}_route_stops{osuf}.parquet')
gf=f'{T}/{city}_route_stops.parquet'
g=pd.read_parquet(gf) if os.path.exists(gf) else o.iloc[0:0]
g=g.assign(freq_source='gtfs')
def keys(d): return d.assign(k=list(zip((d.stop_lat/0.0015).round().astype(int),(d.stop_lon/0.002).round().astype(int))))
g=keys(g); o=keys(o)
# tolerant matching: GTFS stop cells are dilated by one cell (about 150-170 m) because OSM stop positions and
# GTFS platform coordinates of the same station differ
NB=[(i,j) for i in (-1,0,1) for j in (-1,0,1)]
inv={}; gk={}
for ru,kk,mw in zip(g.route_uid,g.k,g.mode_w):
    for di,dj in NB:
        k2=(kk[0]+di,kk[1]+dj); inv.setdefault((k2,mw),set()).add(ru); gk.setdefault(ru,set()).add(k2)
dup=[]
for ru,sub in o.groupby('route_uid'):
    ks=set(sub.k); mw=sub.mode_w.iloc[0]
    cand=set().union(*[inv.get((k,mw),set()) for k in ks]) if ks else set()
    if any(len(ks&gk[c])>=0.6*len(ks) for c in cand): dup.append(ru)
add=o[~o.route_uid.isin(dup)]
cols=['route_uid','stop_id','stop_lon','stop_lat','route_type','mode_w','trips_week','freq_source']
H=pd.concat([g[cols],add[cols]],ignore_index=True); H['route_type']=H.route_type.astype(str); H['stop_id']=H.stop_id.astype(str)
H.to_parquet(f'{T}/{city}_route_stops_hybrid.parquet')   # same name whichever OSM input; audit records it
a={'city':city,'osm_input':osuf,'gtfs_routes':int(g.route_uid.nunique()),'osm_groups':int(o.route_uid.nunique()),'osm_duplicates_of_gtfs':len(dup),
   'osm_added':int(add.route_uid.nunique()),'added_by_mode':add.drop_duplicates('route_uid').route_type.astype(str).value_counts().to_dict(),
   'added_freq_source':add.drop_duplicates('route_uid').freq_source.value_counts().to_dict()}
json.dump(a,open(f'{T}/{city}_hybrid_audit.json','w'),indent=1); print(json.dumps(a))
