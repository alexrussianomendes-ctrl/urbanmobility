"""City results for the 19 study cities with the calibrated parameters.
Geographies: urban centre (DEGURBA on Kontur H3, cells in_uc) and municipality (in_muni). Destinations and
transit beyond the boundary count (distances were computed on the full study area).
Per city x geography x index: population-weighted mean (the official Walk Score city convention), weighted median,
p10/p25/p75/p90, population shares >=70, 50-69, 25-49, <25, and a 95% uncertainty half-width from validation.
Transit variant per city: GTFS where a usable feed exists; hybrid (GTFS + OSM routes missing from it) where the
feed covers only part of the network; OSM routes with published rail headways (_osm_ph) where there is no GTFS.
Outputs: results/city_scores.csv, results/rankings.csv, results/cells/<city>_cells.parquet (GeoParquet, EPSG:4326,
250 m cell polygons) and results/cells_all.gpkg (one layer per city)."""
import json, os, sys, numpy as np, pandas as pd, geopandas as gpd, importlib.util
from shapely.geometry import box
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work')
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P=json.load(open(f'{B}/code/params_calibrated.json'))
CITIES=['nyc','chicago','losangeles','paris','munich','vienna','lisbon','amsterdam','madrid','barcelona','milan','rome','london','berlin',
        'moscow','stpetersburg','tokyo','osaka','shanghai','beijing','shenzhen']
MAIN={'london':'_hybrid','munich':'_hybrid','tokyo':'_hybrid','stpetersburg':'_hybrid','osaka':'_osm_ph','moscow':'_hybrid','shanghai':'_osm_ph','beijing':'_osm_ph','shenzhen':'_osm_ph'}
VNAME={'':'gtfs','_hybrid':'hybrid_gtfs_osm','_osm_ph':'osm_published_headways','_osm':'osm_imputed'}
# validation-based 95% half-widths (city level, pooled calibration+test cities)
VM=pd.read_csv(f'{B}/results/validation_metrics.csv'); VC=pd.read_csv(f'{B}/results/validation_city_level.csv')
def rmse(e): e=np.asarray(e,float); e=e[np.isfinite(e)]; return float(np.sqrt((e**2).mean()))
HW={'walk':1.96*rmse(VC.walk_est-VC.walk_official),'bike':1.96*rmse(VC.bike_est-VC.bike_official),
    'transit_gtfs':1.96*rmse(VC.transit_est-VC.transit_official),'transit_osm_imputed':1.96*rmse(VC.transit_osm_proxy_est-VC.transit_official)}
if os.path.exists(f'{B}/results/proxy_variants_validation.csv'):
    PV=pd.read_csv(f'{B}/results/proxy_variants_validation.csv')
    HW['transit_osm_imputed']=1.96*rmse(PV.osm_v2-PV.official)
    # published-headway variant: error of the rail-known case plus the spread from the formula error
    HW['transit_osm_published_headways']=1.96*np.sqrt(rmse(PV.osm_railpub_mean-PV.official)**2+((PV.osm_railpub_p95-PV.osm_railpub_p05)/3.29).pow(2).mean())
else: HW['transit_osm_published_headways']=HW['transit_osm_imputed']
HW['transit_hybrid_gtfs_osm']=max(HW['transit_gtfs'],HW['transit_osm_published_headways'])
def wq(v,w,q):
    o=np.argsort(v); v=v[o]; w=w[o]; c=np.cumsum(w)/w.sum(); return float(np.interp(q,c,v))
def stats(v,w,pre):
    m=np.isfinite(v); v=v[m]; w=w[m]
    if not len(v) or w.sum()==0: return {}
    d={f'{pre}_mean':float((v*w).sum()/w.sum()),f'{pre}_median':wq(v,w,.5)}
    for q in (10,25,75,90): d[f'{pre}_p{q}']=wq(v,w,q/100)
    for lo,hi,nm in ((70,101,'ge70'),(50,70,'50_69'),(25,50,'25_49'),(0,25,'lt25')): d[f'{pre}_share_{nm}']=float(w[(v>=lo)&(v<hi)].sum()/w.sum())
    return d
os.makedirs(f'{B}/results/cells',exist_ok=True)
rows=[]; only=sys.argv[1:] or CITIES
for c in only:
    if not os.path.exists(f'{W}/ws/{c}_D.parquet'): print(c,'not ready'); continue
    g=sc.compute(c,P,write=False); tv=MAIN.get(c,'')
    if f'transit{tv}' not in g: print(c,'missing transit variant',tv); tv='_osm' if 'transit_osm' in g else None
    g['transit_main']=g[f'transit{tv}'] if tv is not None else np.nan
    crs=json.load(open(f'{W}/grid/{c}_grid.json'))['crs']
    keep=['cell_id','lon','lat','h3','in_uc','in_muni','pop','walk','bike','bike_lane','bike_hill','transit_main']+[k for k in g.columns if k.startswith('transit') and k not in ('transit_main',) and not k.startswith('transit_raw')]
    G=gpd.GeoDataFrame(g[keep].copy(),geometry=[box(x-125,y-125,x+125,y+125) for x,y in zip(g.x,g.y)],crs=crs).to_crs(4326)
    G['transit_variant']=VNAME.get(tv,'none'); G.to_parquet(f'{B}/results/cells/{c}_cells.parquet')
    osm_share=None
    if tv=='_hybrid':
        CR=pd.read_parquet(f'{W}/transit/{c}_cell_route_hybrid.parquet'); Rh=pd.read_parquet(f'{W}/transit/{c}_routes_hybrid.parquet')
        tot=sc.transit_raw(CR,Rh,P); hs=pd.read_parquet(f'{W}/transit/{c}_route_stops_hybrid.parquet',columns=['route_uid','freq_source']).drop_duplicates('route_uid')
        timed=set(hs.route_uid[hs.freq_source=='datamos_via_osm_ref'])   # OSM stops but official trip counts (Moscow)
        part=sc.transit_raw(CR,Rh[Rh.route_uid.astype(str).str.startswith('osm:')&~Rh.route_uid.isin(timed)],P)
        g['osm_share']=g.cell_id.map((part/tot).fillna(0)).fillna(0).values
    au=f'{W}/transit/{c}_gtfs_audit.json'; gap=None
    if os.path.exists(au):
        A=[a for a in json.load(open(au)) if a.get('status')=='ok']; gap=max([abs(a.get('gap_days_to_ref',0)) for a in A],default=None)
    for geo,col in (('urban_centre','in_uc'),('municipality','in_muni')):
        s=g[g[col]]; w=s['pop'].values
        r={'city':c,'geography':geo,'population':float(w.sum()),'cells':int(len(s)),'transit_variant':VNAME.get(tv,'none'),'max_feed_gap_days':gap}
        for k,col2 in (('walk','walk'),('transit','transit_main'),('bike','bike')): r.update(stats(s[col2].values.astype(float),w,k))
        if 'transit_osm' in s: r.update({'transit_osm_imputed_mean':float((s.transit_osm.values*w).sum()/w.sum())})
        r['walk_hw95']=HW['walk']; r['bike_hw95']=HW['bike']
        if 'osm_share' in s: r['transit_osm_share']=float((s.osm_share.values*w).sum()/w.sum())
        rows.append(r)
    print(c,{k:round(v,1) for k,v in rows[-1].items() if k.endswith('_mean')},flush=True)
D=pd.DataFrame(rows)
f=f'{B}/results/city_scores.csv'
if os.path.exists(f) and sys.argv[1:]:
    old=pd.read_csv(f); D=pd.concat([old[~old.city.isin(D.city)],D],ignore_index=True)
# Transit uncertainty for the OSM-based variants, from every city that has both GTFS and the OSM proxy:
# proxy minus GTFS-based score (municipality) in the 10 US validation cities and the GTFS study cities, combined
# with the GTFS-based model's own error against official scores. Published rail headways did not measurably reduce
# the proxy error on the validation cities (18_proxy_variants_validation.py), so they get the same width.
dm=D[(D.geography=='municipality')&(D.transit_variant=='gtfs')&(~D.city.isin(VC.city))].dropna(subset=['transit_osm_imputed_mean'])
dif=np.r_[(dm.transit_osm_imputed_mean-dm.transit_mean).values,(VC.transit_osm_proxy_est-VC.transit_est).values]
dif=dif[np.isfinite(dif)]
HW['proxy_minus_gtfs_rmse']=rmse(dif); HW['proxy_minus_gtfs_bias']=float(dif.mean()); HW['proxy_n_cities']=int(len(dif))
HW['transit_osm_imputed']=1.96*np.sqrt(HW['proxy_minus_gtfs_rmse']**2+(HW['transit_gtfs']/1.96)**2)
HW['transit_osm_published_headways']=HW['transit_osm_imputed']
def thw(r):
    v=r.transit_variant
    if v=='hybrid_gtfs_osm':
        sh=r.get('transit_osm_share',0.5); sh=0.5 if pd.isna(sh) else sh
        return float(np.sqrt((1-sh)*HW['transit_gtfs']**2+sh*HW['transit_osm_published_headways']**2))
    return HW.get('transit_'+v,np.nan)
D['transit_hw95']=D.apply(thw,axis=1)
D.to_csv(f,index=False)
R=[]
for geo in ('urban_centre','municipality'):
    d=D[D.geography==geo]
    for k in ('walk','transit','bike'):
        x=d[['city',f'{k}_mean',f'{k}_hw95']].dropna().sort_values(f'{k}_mean',ascending=False).reset_index(drop=True)
        x['rank']=np.arange(1,len(x)+1)
        # rank range: cities whose interval overlaps share a rank band
        lo=x[f'{k}_mean']-x[f'{k}_hw95']; hi=x[f'{k}_mean']+x[f'{k}_hw95']
        x['rank_best']=[int((lo>hi[i]).sum()+1) for i in range(len(x))]; x['rank_worst']=[int(len(x)-(hi<lo[i]).sum()) for i in range(len(x))]
        x['index']=k; x['geography']=geo; R.append(x.rename(columns={f'{k}_mean':'score',f'{k}_hw95':'hw95'}))
pd.concat(R).to_csv(f'{B}/results/rankings.csv',index=False)
print(json.dumps({k:round(v,2) for k,v in HW.items()}))
