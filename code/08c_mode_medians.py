"""Median weekly trips (busiest direction) per OSM route mode, from the GTFS cities, used ONLY to impute a
frequency for OSM route relations that carry no interval tag (08b_osm_transit.py). Reported by region so the
sensitivity of the imputation to the donor region can be shown.
Output: $MS_BASE/data/transit_mode_medians.json"""
import glob, json, pandas as pd, numpy as np
W=__import__('os').environ.get('MS_WORK','work')
REG={'nyc':'na','chicago':'na','losangeles':'na','boston':'na','sanfrancisco':'na','seattle':'na','washington':'na',
     'portland':'na','philadelphia':'na','minneapolis':'na','toronto':'na','paris':'eu','munich':'eu','vienna':'eu',
     'lisbon':'eu','amsterdam':'eu','madrid':'eu','barcelona':'eu','milan':'eu','rome':'eu','tokyo':'asia','stpetersburg':'stale'}
# OSM route=* -> GTFS route_type groups
GRP={'subway':['1','400','401','402'],'light_rail':['0','900'],'tram':['0','900','901','902'],'train':['2','100','101','102','103','106','109'],
     'monorail':['12','405'],'trolleybus':['11','800'],'bus':['3','700','702','704','715'],'ferry':['4','1000','1200'],
     'funicular':['7','1400'],'aerialway':['6','1300']}
rows=[]
for f in glob.glob(f'{W}/transit/*_route_stops.parquet'):
    c=f.split('/')[-1].replace('_route_stops.parquet','')
    if c not in REG or REG[c]=='stale': continue
    r=pd.read_parquet(f,columns=['route_uid','route_type','trips_week']).drop_duplicates('route_uid'); r['city']=c; r['region']=REG[c]
    rows.append(r)
R=pd.concat(rows); R['route_type']=R.route_type.astype(str)
out={'_note':'median trips/week in busiest direction per route, GTFS cities, reference week near 2026-11-16','all':{},'na':{},'eu':{},'asia':{},'n':{}}
for mode,types in GRP.items():
    d=R[R.route_type.isin(types)]
    for reg in ('all','na','eu','asia'):
        dd=d if reg=='all' else d[d.region==reg]
        if len(dd)>=5: out[reg][mode]=float(dd.trips_week.median())
    out['n'][mode]=int(len(d))
json.dump(out,open(__import__('os').environ.get('MS_BASE','.')+'/data/transit_mode_medians.json','w'),indent=1); print(json.dumps(out,indent=1))
