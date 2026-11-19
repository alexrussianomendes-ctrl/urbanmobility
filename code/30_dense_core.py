"""Third geography: the dense core of each city, as asked by the user ("regions with at least 50% of the density
of the densest place").
Definition (stated in the report):
  1. Density of each 250 m cell = Kontur population / 0.0625 km2.
  2. Smoothed density = mean density of all grid cells whose centre lies within 1,500 m of the cell centre (a window
     of about 3 km), so that a small isolated cluster does not set the threshold. With a 1 km window (radius 500 m)
     the peak fell on a single Kontur hexagon in several cities (Shenzhen, Shanghai, Lisbon, Chicago, Rome, Moscow)
     and the core shrank to 1-6 km2 around one tower cluster or dormitory block; from a radius of 1,500 m on, every core
     is at least 20 km2. Radii 1,000 and 2,000 m are run as sensitivity (argument: radius in metres).
  3. Peak = the cell with the highest smoothed density in the study area of the city.
  4. Core = the cells with smoothed density >= 50% of the peak that are connected to the peak cell through such
     cells (8-neighbour contiguity on the 250 m grid). Isolated dense patches elsewhere are left out.
Scores: population-weighted means of the cell scores already computed (results/cells/<city>_cells.parquet), with
the same 95% half-widths as the main results (Walk, Bike, Transit by variant; hybrids mixed by the OSM share of
the transit sum inside the core). Rank ranges as in 17_city_results.py.
Outputs: results/dense_core_scores.csv, results/dense_core_rankings.csv, results/dense_core_cells.parquet
(cell_id, city, in_core, dens_smooth), results/ranking_comparison.csv (rank by geography and Spearman)."""
import json, sys, numpy as np, pandas as pd, importlib.util
from scipy.spatial import cKDTree
from scipy.ndimage import label
from scipy.stats import spearmanr
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work')
RAD=float(sys.argv[1]) if sys.argv[1:] else 1500.0; SUF='' if RAD==1500 else f'_r{int(RAD)}'
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P=json.load(open(f'{B}/code/params_calibrated.json'))
CS=pd.read_csv(f'{B}/results/city_scores.csv'); CITIES=list(dict.fromkeys(CS.city))
HWG=float(CS[CS.transit_variant=='gtfs'].transit_hw95.iloc[0]); HWO=float(CS[CS.transit_variant=='osm_published_headways'].transit_hw95.iloc[0])
HWW=float(CS.walk_hw95.iloc[0]); HWB=float(CS.bike_hw95.iloc[0])
def wq(v,w,q): o=np.argsort(v); v=v[o]; w=w[o]; c=np.cumsum(w)/w.sum(); return float(np.interp(q,c,v))
rows=[]; cells=[]
for c in CITIES:
    G=pd.read_parquet(f'{W}/grid/{c}_grid.parquet',columns=['x','y','cell_id'])
    C=pd.read_parquet(f'{B}/results/cells/{c}_cells.parquet').drop(columns='geometry').merge(G,on='cell_id')
    dens=C['pop'].values/0.0625; xy=C[['x','y']].values
    nb=cKDTree(xy).query_ball_point(xy,r=RAD+0.01)
    ds=np.array([dens[i].mean() for i in nb]); C['dens_smooth']=ds
    pk=int(np.argmax(ds)); thr=0.5*ds[pk]
    ix=((C.x-C.x.min())/250).round().astype(int).values; iy=((C.y-C.y.min())/250).round().astype(int).values
    M=np.zeros((iy.max()+1,ix.max()+1),bool); M[iy,ix]=ds>=thr
    L,_=label(M,structure=np.ones((3,3))); C['in_core']=L[iy,ix]==L[iy[pk],ix[pk]]
    s=C[C.in_core]; w=s['pop'].values
    r={'city':c,'geography':'dense_core','population':float(w.sum()),'cells':int(len(s)),'area_km2':len(s)*0.0625,
       'peak_density_smoothed':float(ds[pk]),'threshold_density':float(thr),'peak_lon':float(C.lon.iloc[pk]),'peak_lat':float(C.lat.iloc[pk]),
       'share_in_municipality':float(s.in_muni.mean()),'transit_variant':s.transit_variant.iloc[0]}
    for k,col in (('walk','walk'),('transit','transit_main'),('bike','bike')):
        v=s[col].values.astype(float); m=np.isfinite(v)
        r[f'{k}_mean']=float((v[m]*w[m]).sum()/w[m].sum()); r[f'{k}_median']=wq(v[m],w[m],.5)
    r['walk_hw95']=HWW; r['bike_hw95']=HWB
    if r['transit_variant']=='hybrid_gtfs_osm':
        CR=pd.read_parquet(f'{W}/transit/{c}_cell_route_hybrid.parquet'); Rh=pd.read_parquet(f'{W}/transit/{c}_routes_hybrid.parquet')
        tot=sc.transit_raw(CR,Rh,P); hs=pd.read_parquet(f'{W}/transit/{c}_route_stops_hybrid.parquet',columns=['route_uid','freq_source']).drop_duplicates('route_uid')
        timed=set(hs.route_uid[hs.freq_source=='datamos_via_osm_ref'])
        part=sc.transit_raw(CR,Rh[Rh.route_uid.astype(str).str.startswith('osm:')&~Rh.route_uid.isin(timed)],P)
        sh=s.cell_id.map((part/tot).fillna(0)).fillna(0).values; sh=float((sh*w).sum()/w.sum()); r['transit_osm_share']=sh
        r['transit_hw95']=float(np.sqrt((1-sh)*HWG**2+sh*HWO**2))
    else: r['transit_hw95']=HWG if r['transit_variant']=='gtfs' else HWO
    rows.append(r); cells.append(C[['cell_id','in_core','dens_smooth']].assign(city=c))
    print(c,round(r['area_km2'],1),'km2',round(r['population']/1e6,2),'M',{k:round(r[f'{k}_mean'],1) for k in ('walk','transit','bike')},flush=True)
D=pd.DataFrame(rows); D.to_csv(f'{B}/results/dense_core_scores{SUF}.csv',index=False)
pd.concat(cells).to_parquet(f'{B}/results/dense_core_cells{SUF}.parquet')
R=[]
for k in ('walk','transit','bike'):
    x=D[['city',f'{k}_mean',f'{k}_hw95']].sort_values(f'{k}_mean',ascending=False).reset_index(drop=True); x['rank']=np.arange(1,len(x)+1)
    lo=x[f'{k}_mean']-x[f'{k}_hw95']; hi=x[f'{k}_mean']+x[f'{k}_hw95']
    x['rank_best']=[int((lo>hi[i]).sum()+1) for i in range(len(x))]; x['rank_worst']=[int(len(x)-(hi<lo[i]).sum()) for i in range(len(x))]
    x['index']=k; x['geography']='dense_core'; R.append(x.rename(columns={f'{k}_mean':'score',f'{k}_hw95':'hw95'}))
RC=pd.concat(R); RC.to_csv(f'{B}/results/dense_core_rankings{SUF}.csv',index=False)
RA=pd.concat([pd.read_csv(f'{B}/results/rankings.csv'),RC]); r['radius_m']=RAD; out=[]
piv=RA.pivot_table(index=['index','city'],columns='geography',values='rank').reset_index()
for k,d in piv.groupby('index'):
    for a,b in (('municipality','urban_centre'),('dense_core','municipality'),('dense_core','urban_centre')):
        out.append({'index':k,'a':a,'b':b,'spearman':float(spearmanr(d[a],d[b])[0]),'max_rank_shift':int((d[a]-d[b]).abs().max()),
                    'city_max_shift':d.city[(d[a]-d[b]).abs().idxmax()]})
piv.to_csv(f'{B}/results/ranking_comparison{SUF}.csv',index=False)
print(pd.DataFrame(out).round(2).to_string())
