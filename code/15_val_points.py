"""Model inputs at the locations walkscore.com actually scored (manual_sample_resolved.csv, status 'localizado*').
Builds a pseudo-city '<city>__val' whose grid holds only those points and whose network, POI and transit inputs are
links to the city's own files, then runs 07, 09 (GTFS and OSM proxy) and 10 on it.
Usage: python 15_val_points.py"""
import os, json, subprocess, pandas as pd, geopandas as gpd
W=__import__('os').environ.get('MS_WORK','work'); C=__import__('os').environ.get('MS_BASE','.')+'/code'
R=pd.read_csv(__import__('os').environ.get('MS_BASE','.')+'/data/validation/manual_sample_resolved.csv')
R=R[R.status.str.startswith('localizado')]
NM={'Boston':'boston','San Francisco':'sanfrancisco','Seattle':'seattle','Chicago':'chicago','New York':'nyc','Los Angeles':'losangeles'}
for cname,c in NM.items():
    v=R[R.cidade==cname]; vc=f'{c}__val'
    crs=json.load(open(f'{W}/grid/{c}_grid.json'))['crs']
    xy=gpd.GeoSeries(gpd.points_from_xy(v.r_lon,v.r_lat),crs=4326).to_crs(crs)
    g=pd.DataFrame({'x':xy.x.values,'y':xy.y.values,'lon':v.r_lon.values,'lat':v.r_lat.values,'h3':'','pop':1.0,
                    'cell_id':[f'val_{i}' for i in v.id],'is_val':True,'in_muni':False})
    g.to_parquet(f'{W}/grid/{vc}_grid.parquet'); json.dump({'city':vc,'crs':crs,'cells':len(g)},open(f'{W}/grid/{vc}_grid.json','w'))
    for d,suf in [('net','_nodes.parquet'),('net','_edges.parquet'),('poi','_pois.parquet'),('transit','_route_stops.parquet'),('transit','_route_stops_osm.parquet')]:
        src=f'{W}/{d}/{c}{suf}'; dst=f'{W}/{d}/{vc}{suf}'
        if os.path.exists(src) and not os.path.exists(dst): os.symlink(src,dst)
    if not os.path.exists(f'{W}/bboxes_val_done'):
        pass
    B=json.load(open(f'{W}/bboxes.json')); B[vc]=B[c]; json.dump(B,open(f'{W}/bboxes.json','w'))
    for args in ([f'{C}/07_walk_distances.py',vc],[f'{C}/10_bike_components.py',vc],[f'{C}/09_transit_distances.py',vc],
                 [f'{C}/09_transit_distances.py',vc,f'{W}/transit/{vc}_route_stops_osm.parquet']):
        r=subprocess.run(['python3',*args],capture_output=True,text=True)
        print(vc,os.path.basename(args[0]),'ok' if r.returncode==0 else 'FAIL '+r.stderr[-400:],flush=True)
