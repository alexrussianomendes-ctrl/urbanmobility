"""Bus frequency model for the OSM transit proxy (labelled estimate, used only where no timetable exists).
Why: on the validation cities the OSM proxy's Transit Score error comes almost entirely from buses (imputed with
one median frequency); knowing rail frequencies changes little (18_proxy_variants_validation.py).
Training data: every OSM bus/trolleybus route group in a city that also has GTFS, matched to a GTFS bus route
(>=50% of the OSM group's stop cells inside the GTFS route's stop cells dilated by one cell, best share wins);
target = GTFS trips/week in the busiest direction. Feeds more than 365 days from the reference week are excluded.
Features (all derivable from OSM + population grid, so available in every city):
  n_stops, extent_km (bbox diagonal of stops), pop_500 (mean population within 500 m of the stops), corridor (mean
  number of other bus groups at the same stop cells), dist_centre_rel (distance from the population-weighted centre
  divided by the square root of the municipality area), rail_near (share of stops within 500 m of a rail stop),
  trolleybus, night (ref starts with N/Н or contains 'night'), city bus groups per 100k municipal residents.
  (City population itself is not used: it would let the model extrapolate to megacities outside the training range.)
Model: gradient boosting on log(trips/week). Evaluated leaving whole cities out.
Outputs: results/bus_model_cv.csv (per city), results/bus_model_validation.csv (Transit Score with the model on the
validation cities, each predicted by a model trained without it), transit/<city>_bus_pred.parquet for the target
cities (final model on all training cities)."""
import json, os, re, numpy as np, pandas as pd, importlib.util
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingRegressor
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work'); T=f'{W}/transit'
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P=json.load(open(f'{B}/code/params_calibrated.json'))
TRAIN=['boston','sanfrancisco','seattle','washington','portland','philadelphia','minneapolis','chicago','nyc','losangeles','toronto',
       'paris','munich','vienna','lisbon','amsterdam','madrid','barcelona','milan','rome','tokyo']
TARGET=['moscow','stpetersburg','osaka','shanghai','beijing','shenzhen','tokyo','munich']
VALC=['boston','sanfrancisco','seattle','washington','portland','philadelphia','minneapolis','chicago','nyc','losangeles']
BUS={'bus','trolleybus','share_taxi','coach','minibus'}; RAIL={'subway','light_rail','tram','train','monorail'}
NB=[(i,j) for i in (-1,0,1) for j in (-1,0,1)]
def kxy(lat,lon): return list(zip((lat/0.0015).round().astype(int),(lon/0.002).round().astype(int)))
def proj(lon,lat,lat0): return np.c_[np.asarray(lon)*111.32*np.cos(np.radians(lat0)),np.asarray(lat)*110.54]
def features(c):
    o=pd.read_parquet(f'{T}/{c}_route_stops_osm.parquet'); g=pd.read_parquet(f'{W}/grid/{c}_grid.parquet')
    lat0=float(g.lat.mean()); G=proj(g.lon,g.lat,lat0); tr=cKDTree(G); pop=g['pop'].values
    uc=g[g.in_muni]; w=uc['pop'].values; cen=np.r_[(proj(uc.lon,uc.lat,lat0)*w[:,None]).sum(0)/w.sum()]; area=len(uc)*0.0625   # municipality: the one geography every grid has
    o['k']=kxy(o.stop_lat,o.stop_lon)
    bus=o[o.route.isin(BUS)]; rail=o[o.route.isin(RAIL)]
    kc={}
    for ru,kk in bus.groupby('route_uid').k:
        for k in set(kk):
            for di,dj in NB: kc[(k[0]+di,k[1]+dj)]=kc.get((k[0]+di,k[1]+dj),0)+1
    rt=cKDTree(proj(rail.stop_lon,rail.stop_lat,lat0)) if len(rail) else None
    rows=[]
    for ru,s in bus.groupby('route_uid'):
        s=s.drop_duplicates('k'); X=proj(s.stop_lon,s.stop_lat,lat0)
        near=tr.query_ball_point(X,0.5); p5=np.mean([pop[i].sum() for i in near]) if len(near) else 0
        ref=str(s.line.iloc[0])
        rows.append({'route_uid':ru,'n_stops':len(s),'extent_km':float(np.hypot(*(X.max(0)-X.min(0)))),'pop_500':p5,
                     'corridor':float(np.mean([kc.get(k,1)-1 for k in s.k])),
                     'dist_centre_rel':float(np.hypot(*(X.mean(0)-cen))/np.sqrt(area)),
                     'rail_near':float(np.mean(rt.query(X,distance_upper_bound=0.5)[0]<0.5)) if rt is not None else 0.0,
                     'trolleybus':int(s.route.iloc[0]=='trolleybus'),
                     'night':int(bool(re.match(r'^\s*[NНн]',ref)) or 'night' in ref.lower()),
                     'city_logpop':float(np.log(w.sum())),'osm_freq_source':s.freq_source.iloc[0],'osm_trips_week':float(s.trips_week.iloc[0])})
    F=pd.DataFrame(rows); F['city_bus_per100k']=len(F)/(w.sum()/1e5); F['city']=c
    return F,o
def target(c,o):
    g=pd.read_parquet(f'{T}/{c}_route_stops.parquet'); g=g[(g.mode_w==1.0)&(g.gap.abs()<=365)]
    inv={}; gks={}
    for ru,kk in zip(g.route_uid,kxy(g.stop_lat,g.stop_lon)):
        for di,dj in NB: inv.setdefault((kk[0]+di,kk[1]+dj),set()).add(ru); gks.setdefault(ru,set()).add((kk[0]+di,kk[1]+dj))
    tw=g.drop_duplicates('route_uid').set_index('route_uid').trips_week
    out={}
    for ru,s in o[o.route.isin(BUS)].groupby('route_uid'):
        ks=set(s.k); cand=set().union(*[inv.get(k,set()) for k in ks]) if ks else set()
        best=max(((len(ks&gks[x])/len(ks),x) for x in cand),default=(0,None))
        if best[0]>=0.5: out[ru]=float(tw[best[1]])
    return pd.Series(out)
FEAT=['n_stops','extent_km','pop_500','corridor','dist_centre_rel','rail_near','trolleybus','night','city_bus_per100k']
DATA={}; ALLO={}
for c in sorted(set(TRAIN+TARGET)):
    if not os.path.exists(f'{T}/{c}_route_stops_osm.parquet'): print(c,'no OSM routes yet'); continue
    F,o=features(c); ALLO[c]=o
    if c in TRAIN and os.path.exists(f'{T}/{c}_route_stops.parquet'):
        y=target(c,o); F['y']=F.route_uid.map(y)
    DATA[c]=F; print(c,len(F),'matched',int(F.get('y',pd.Series(dtype=float)).notna().sum()),flush=True)
TR=pd.concat([DATA[c] for c in TRAIN if c in DATA and 'y' in DATA[c]]); TR=TR[TR.y>0]
def fit(d): m=HistGradientBoostingRegressor(max_iter=400,learning_rate=0.05,max_leaf_nodes=31,min_samples_leaf=40,l2_regularization=1.0,random_state=0); return m.fit(d[FEAT],np.log(d.y))
MED=json.load(open(f'{B}/data/transit_mode_medians.json'))['all']
cv=[]; PRED={}
for c in TR.city.unique():
    m=fit(TR[TR.city!=c]); d=TR[TR.city==c]; pr=m.predict(d[FEAT]); PRED[c]=m
    e=pr-np.log(d.y); e0=np.log(MED['bus'])-np.log(d.y)
    cv.append({'city':c,'n':len(d),'model_mae_log':float(np.abs(e).mean()),'model_bias_log':float(e.mean()),'median_mae_log':float(np.abs(e0).mean()),'median_bias_log':float(e0.mean()),
               'spearman':float(pd.Series(pr).corr(pd.Series(np.log(d.y.values)),method='spearman'))})
CV=pd.DataFrame(cv); CV.to_csv(f'{B}/results/bus_model_cv.csv',index=False); print(CV.round(2).to_string())
print('mean |log err| model',round(CV.model_mae_log.mean(),3),'vs single median',round(CV.median_mae_log.mean(),3))
# downstream: Transit Score on validation cities with rail from GTFS (best case) or imputed, buses from the LOCO model
OFF=pd.read_csv(f'{B}/data/validation/official_city_level.csv').set_index('city'); VP=pd.read_csv(f'{B}/results/validation_points.csv')
PV=pd.read_csv(f'{B}/results/proxy_variants_validation.csv').set_index('city')
res=[]; pts=[]
for c in VALC:
    if c not in PRED: continue
    F=DATA[c]; pr=np.exp(PRED[c].predict(F[FEAT])); mp=dict(zip(F.route_uid,pr))
    R=pd.read_parquet(f'{T}/{c}_routes_osm.parquet')
    imp=set(F.route_uid[F.osm_freq_source=='imputed_mode_median'])
    R['trips_week']=[mp[r] if r in imp else t for r,t in zip(R.route_uid,R.trips_week)]
    out={'city':c,'official':OFF.transit[c],'osm_v2':PV.osm_v2[c]}
    for cc in (c,c+'__val'):
        f=f'{T}/{cc}_cell_route_osm.parquet'
        if not os.path.exists(f): continue
        CR=pd.read_parquet(f); gr=pd.read_parquet(f'{W}/grid/{cc}_grid.parquet')
        ts=sc.transit_score(gr.cell_id.map(sc.transit_raw(CR,R,P)).fillna(0).values,P)
        if cc==c: m=gr.in_muni.values; w=gr['pop'].values[m]; out['osm_busmodel']=float((ts[m]*w).sum()/w.sum())
        else: pts.append(pd.DataFrame({'id':gr.cell_id.str.replace('val_','').astype(int),'est':ts}))
    res.append(out)
V=pd.DataFrame(res); V.to_csv(f'{B}/results/bus_model_validation.csv',index=False); print(V.round(1).to_string())
def met(e): e=np.asarray(e,float); return f"MAE {np.abs(e).mean():.2f} RMSE {np.sqrt((e**2).mean()):.2f} bias {e.mean():.2f}"
print('city  osm_v2   :',met(V.osm_v2-V.official)); print('city  busmodel :',met(V.osm_busmodel-V.official))
if pts:
    Pp=pd.concat(pts).merge(VP[['id','set','transit_official','transit_osm_proxy_est']],on='id')
    for s in ('calibration','test'):
        d=Pp[Pp.set==s]; print('points',s,'osm:',met(d.transit_osm_proxy_est-d.transit_official),'| busmodel:',met(d.est-d.transit_official))
    Pp.to_csv(f'{B}/results/bus_model_validation_points.csv',index=False)
# final model -> predictions for target cities
M=fit(TR)
for c in TARGET:
    if c not in DATA: continue
    F=DATA[c]; F['trips_week_pred']=np.exp(M.predict(F[FEAT]))
    F[['route_uid','trips_week_pred','osm_freq_source']+FEAT].to_parquet(f'{T}/{c}_bus_pred.parquet')
    print(c,'pred median',round(float(F.trips_week_pred.median()),0),'n',len(F))
