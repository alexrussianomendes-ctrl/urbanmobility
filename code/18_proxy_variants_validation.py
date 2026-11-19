"""How much of the OSM-proxy Transit Score error goes away when rail frequencies are known (as with published
headways), measured on the validation cities, which have GTFS to act as truth.
Variants (stops/distances unchanged; only trips/week per route changes, so cell_route_osm is reused):
  osm_v1      : OSM proxy as built (imputed mode medians at build time)
  osm_v2      : OSM proxy with the updated mode medians (after the frequencies.txt fix)
  osm_railgtfs: osm_v2, but every OSM rail group (subway/light rail/tram/train/monorail) matched to a GTFS route
                (same mode weight, >=50% of its stop cells shared, 3x3 tolerance) takes that route's GTFS trips/week;
                buses stay imputed. This is the best case of the published-headway variant.
  osm_railpub : osm_railgtfs with the published-headway formula error added: each rail route's trips/week multiplied
                by a ratio drawn from the 61 formula-check ratios divided by their median (200 draws; mean and
                5-95% band of the error metrics reported).
Uses params_calibrated.json. Output: results/proxy_variants_validation.csv"""
import json, os, numpy as np, pandas as pd, importlib.util
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work'); T=f'{W}/transit'
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P=json.load(open(f'{B}/code/params_calibrated.json')); MED=json.load(open(f'{B}/data/transit_mode_medians.json'))['all']
OFF=pd.read_csv(f'{B}/data/validation/official_city_level.csv').set_index('city')
VP=pd.read_csv(f'{B}/results/validation_points.csv')
CK=pd.read_csv(f'{B}/results/headway_formula_check.csv'); RAT=(CK.ratio/CK.ratio.median()).values
CITIES=['boston','sanfrancisco','seattle','washington','portland','philadelphia','minneapolis','chicago','nyc','losangeles']
TEST=['chicago','nyc','losangeles']; VAL={'boston','sanfrancisco','seattle','chicago','nyc','losangeles'}
RAIL={'subway','light_rail','tram','train','monorail'}
FB={'trolleybus':'bus','share_taxi':'bus','coach':'bus','minibus':'bus','light_rail':'light_rail','monorail':'subway','funicular':'tram'}
NB=[(i,j) for i in (-1,0,1) for j in (-1,0,1)]
def keys(d): return set(zip((d.stop_lat/0.0015).round().astype(int),(d.stop_lon/0.002).round().astype(int)))
rng=np.random.default_rng(20261118)
res=[]; pts={}
for c in CITIES:
    o=pd.read_parquet(f'{T}/{c}_route_stops_osm.parquet'); g=pd.read_parquet(f'{T}/{c}_route_stops.parquet')
    info=o.drop_duplicates('route_uid').set_index('route_uid')
    R1=pd.read_parquet(f'{T}/{c}_routes_osm.parquet').set_index('route_uid')
    R2=R1.copy()
    imp=info.freq_source=='imputed_mode_median'
    for ru in info.index[imp]:
        if ru in R2.index:
            m=info.route[ru]; m=m if m in MED else FB.get(m,'bus'); R2.loc[ru,'trips_week']=MED.get(m,MED['bus'])
    # match rail groups to GTFS
    gk={};
    for ru,sub in g.groupby('route_uid'):
        ks=keys(sub); gk[ru]=(set((a+i,b+j) for a,b in ks for i,j in NB),float(sub.mode_w.iloc[0]),float(sub.trips_week.iloc[0]))
    R3=R2.copy(); matched=0; railn=0
    for ru,sub in o.groupby('route_uid'):
        if info.route[ru] not in RAIL or ru not in R3.index: continue
        railn+=1; ks=keys(sub); mw=float(sub.mode_w.iloc[0]); best=None
        for gru,(gks,gmw,gtw) in gk.items():
            if gmw!=mw: continue
            sh=len(ks&gks)/max(len(ks),1)
            if sh>=0.5 and (best is None or sh>best[0]): best=(sh,gtw)
        if best: R3.loc[ru,'trips_week']=best[1]; matched+=1
    railidx=[ru for ru in R3.index if ru in info.index and info.route[ru] in RAIL]
    def score_city(R,cc):
        CR=pd.read_parquet(f'{T}/{cc}_cell_route_osm.parquet'); gr=pd.read_parquet(f'{W}/grid/{cc}_grid.parquet')
        raw=gr.cell_id.map(sc.transit_raw(CR,R.reset_index(),P)).fillna(0).values; ts=sc.transit_score(raw,P)
        return gr,ts
    out={'city':c,'set':'test' if c in TEST else 'calibration','official':OFF.transit[c],'rail_groups':railn,'rail_matched_gtfs':matched}
    gr,_=score_city(R1,c); m=gr.in_muni.values; w=gr['pop'].values[m]
    for nm,R in (('osm_v1',R1),('osm_v2',R2),('osm_railgtfs',R3)):
        _,ts=score_city(R,c); out[nm]=float((ts[m]*w).sum()/w.sum())
        if c in VAL:
            gv,tv=score_city(R,c+'__val'); pts.setdefault(nm,[]).append(pd.DataFrame({'id':gv.cell_id.str.replace('val_','').astype(int),'est':tv}))
    sims=[]; simp=[]
    CR=pd.read_parquet(f'{T}/{c}_cell_route_osm.parquet')
    for k in range(200):
        R4=R3.copy(); R4.loc[railidx,'trips_week']=R4.loc[railidx,'trips_week'].values*rng.choice(RAT,len(railidx))
        raw=gr.cell_id.map(sc.transit_raw(CR,R4.reset_index(),P)).fillna(0).values; ts=sc.transit_score(raw,P)
        sims.append(float((ts[m]*w).sum()/w.sum()))
        if c in VAL and k<50:
            gv,tv=score_city(R4,c+'__val'); simp.append(tv)
    out['osm_railpub_mean']=float(np.mean(sims)); out['osm_railpub_p05']=float(np.percentile(sims,5)); out['osm_railpub_p95']=float(np.percentile(sims,95))
    if c in VAL: pts.setdefault('osm_railpub',[]).append(pd.DataFrame({'id':gv.cell_id.str.replace('val_','').astype(int),'est':np.mean(simp,axis=0),'sd':np.std(simp,axis=0)}))
    res.append(out); print(out,flush=True)
D=pd.DataFrame(res); D.to_csv(f'{B}/results/proxy_variants_validation.csv',index=False)
def met(e,o): e=np.asarray(e,float)-np.asarray(o,float); return {'n':len(e),'MAE':round(float(np.abs(e).mean()),2),'RMSE':round(float(np.sqrt((e**2).mean())),2),'bias':round(float(e.mean()),2)}
rows=[]
for nm in ('osm_v1','osm_v2','osm_railgtfs','osm_railpub_mean'):
    for s in ('calibration','test'):
        d=D[D.set==s]; rows.append({'variant':nm,'level':'city','set':s,**met(d[nm],d.official)})
    k=nm.replace('_mean','')
    if k in pts:
        P_=pd.concat(pts[k]).merge(VP[['id','set','transit_official']],on='id')
        for s in ('calibration','test'):
            d=P_[P_.set==s]; rows.append({'variant':k,'level':'point','set':s,**met(d.est,d.transit_official)})
G=VP.copy()
for s in ('calibration','test'):
    d=G[G.set==s]; rows.append({'variant':'gtfs (reference)','level':'point','set':s,**met(d.transit_est,d.transit_official)})
M=pd.DataFrame(rows); M.to_csv(f'{B}/results/proxy_variants_metrics.csv',index=False); print(M.to_string())
