"""Sensitivity of the city results to the choices that are inferred rather than documented.
Each variant changes one thing; everything else stays at the main specification (params_calibrated.json and the
main transit variant per city from 17_city_results.py). Population-weighted means per city x geography.
Walk:    decay_table (documented 0.25 mi plateau / 1.5 mi cut, uncalibrated table shape), no_penalties
         (intersection and block-length penalties off).
Bike:    grade_p90 (90th-percentile slope instead of the maximum), classes_soft (path 1, lane 0.75, shared 0.5),
         classes_strict (path 1, lane 0.33, shared 0), no_hills (hill component dropped, weights renormalised),
         lane_ref_x0.75 / lane_ref_x1.25 (lane saturation point), decay_table (destinations with the table decay).
Transit: osm_imputed (OSM routes with one median frequency per mode, no timetables), bus_model (OSM-imputed buses
         replaced by the bus-frequency model, 19_bus_model.py), headways_AB_only (published headways of grade C/D
         replaced by the mode median), formula_p10 / formula_p90 (published-headway trips scaled by the 10th / 90th
         percentile of the formula check, i.e. the formula's own error), and for GTFS cities the share of the transit
         sum that comes from feeds more than 365 days from the reference week (stale feeds).
Also: POI density (merged destinations per 1000 residents of the municipality), a completeness indicator for the
Walk Score inputs (low values in Chinese cities point to missing POIs, so Walk Score there is a lower bound).
Outputs: results/sensitivity.csv (long), results/poi_density.csv"""
import json, os, sys, copy, numpy as np, pandas as pd, importlib.util
from scipy.spatial import cKDTree
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work'); T=f'{W}/transit'
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P=json.load(open(f'{B}/code/params_calibrated.json')); P0=json.load(open(f'{B}/code/params_default.json'))
MED=json.load(open(f'{B}/data/transit_mode_medians.json'))['all']
CK=pd.read_csv(f'{B}/results/headway_formula_check.csv'); RAT=(CK.ratio/CK.ratio.median())
Q10,Q90=float(RAT.quantile(.1)),float(RAT.quantile(.9))
CITIES=['nyc','chicago','losangeles','paris','munich','vienna','lisbon','amsterdam','madrid','barcelona','milan','rome','london','berlin',
        'moscow','stpetersburg','tokyo','osaka','shanghai','beijing','shenzhen']
MAIN={'london':'_hybrid','munich':'_hybrid','tokyo':'_hybrid','stpetersburg':'_hybrid','osaka':'_osm_ph','moscow':'_hybrid','shanghai':'_osm_ph','beijing':'_osm_ph','shenzhen':'_osm_ph'}
FB={'trolleybus':'bus','share_taxi':'bus','coach':'bus','minibus':'bus','monorail':'subway','funicular':'tram'}
BUS={'bus','trolleybus','share_taxi','coach','minibus'}
def wmean(v,w): m=np.isfinite(v); return float((v[m]*w[m]).sum()/w[m].sum()) if w[m].sum()>0 else np.nan
def tscore(g,CR,R,p=P): return sc.transit_score(g.cell_id.map(sc.transit_raw(CR,R,p)).fillna(0).values,p)
rows=[]; dens=[]
only=sys.argv[1:] or CITIES
for c in only:
    if not os.path.exists(f'{W}/ws/{c}_D.parquet'): print(c,'not ready'); continue
    g=sc.compute(c,P,write=False); tv=MAIN.get(c,'')
    if not os.path.exists(f'{T}/{c}_cell_route{tv}.parquet'): print(c,'main transit missing'); tv=None
    V={}
    # walk
    V[('walk','main')]=g.walk.values
    Pt=copy.deepcopy(P); Pt['walk']['decay']=P0['walk']['decay']; _,_,_,wt,_=sc.walk_score(g,Pt); V[('walk','decay_table')]=wt
    Pn=copy.deepcopy(P); Pn['walk']['intersection_penalty']=[[0,1e12,0]]; Pn['walk']['block_penalty']=[[0,1e12,0]]
    V[('walk','no_penalties')]=sc.walk_score(g,Pn)[3]
    # bike
    if 'bike' in g:
        V[('bike','main')]=g.bike.values
        def bk(mod,ws=g.walk.values):
            q=copy.deepcopy(P); mod(q['bike']); return sc.bike_score(g,ws,q)[2]
        V[('bike','grade_p90')]=bk(lambda b:b.update(grade_col='grade_p90'))
        V[('bike','classes_soft')]=bk(lambda b:b.update(class_weights={'path':1.0,'lane':0.75,'shared':0.5}))
        V[('bike','classes_strict')]=bk(lambda b:b.update(class_weights={'path':1.0,'lane':0.3333,'shared':0.0}))
        V[('bike','no_hills')]=bk(lambda b:b.update(component_weights={'lanes':0.5,'hills':0.0,'destinations':0.25}))
        V[('bike','lane_ref_x0.75')]=bk(lambda b:b.update(lane_ref=b['lane_ref']*0.75))
        V[('bike','lane_ref_x1.25')]=bk(lambda b:b.update(lane_ref=b['lane_ref']*1.25))
        V[('bike','decay_table')]=bk(lambda b:None,wt)
    # transit
    stale=np.nan
    if tv is not None:
        CR=pd.read_parquet(f'{T}/{c}_cell_route{tv}.parquet'); R=pd.read_parquet(f'{T}/{c}_routes{tv}.parquet')
        V[('transit','main')]=tscore(g,CR,R)
        if os.path.exists(f'{T}/{c}_cell_route_osm.parquet') and tv!='_osm':
            V[('transit','osm_imputed')]=tscore(g,pd.read_parquet(f'{T}/{c}_cell_route_osm.parquet'),pd.read_parquet(f'{T}/{c}_routes_osm.parquet'))
        if tv in ('_osm_ph','_hybrid'):
            rs=pd.read_parquet(f'{T}/{c}_route_stops{tv}.parquet').drop_duplicates('route_uid')
            ph=pd.read_parquet(f'{T}/{c}_route_stops_osm_ph.parquet' if os.path.exists(f'{T}/{c}_route_stops_osm_ph.parquet') else f'{T}/{c}_route_stops_osm.parquet').drop_duplicates('route_uid').set_index('route_uid')
            info=ph[['route','freq_source']+(['ph_grade'] if 'ph_grade' in ph else [])]
            Ri=R.set_index('route_uid')
            pub=[u for u in Ri.index if u in info.index and str(info.freq_source.get(u,'')).startswith('published')]
            imp_bus=[u for u in Ri.index if u in info.index and info.freq_source[u]=='imputed_mode_median' and info.route[u] in BUS]
            bp=f'{T}/{c}_bus_pred.parquet'
            if os.path.exists(bp):
                pr=pd.read_parquet(bp).set_index('route_uid').trips_week_pred
                Rb=Ri.copy(); u=[x for x in imp_bus if x in pr.index]; Rb.loc[u,'trips_week']=pr[u].values
                V[('transit','bus_model')]=tscore(g,CR,Rb.reset_index())
            if 'ph_grade' in info:
                cd=[u for u in pub if info.ph_grade[u] in ('C','D')]
                if cd:
                    Ra=Ri.copy()
                    for u in cd: m=info.route[u]; m=m if m in MED else FB.get(m,'subway'); Ra.loc[u,'trips_week']=MED.get(m,MED['subway'])
                    V[('transit','headways_AB_only')]=tscore(g,CR,Ra.reset_index())
            if pub:
                for nm,k in (('formula_p10',Q10),('formula_p90',Q90)):
                    Rf=Ri.copy(); Rf.loc[pub,'trips_week']=Rf.loc[pub,'trips_week']*k; V[('transit',nm)]=tscore(g,CR,Rf.reset_index())
        if tv in ('','_hybrid') and os.path.exists(f'{T}/{c}_route_stops.parquet'):
            rs=pd.read_parquet(f'{T}/{c}_route_stops.parquet').drop_duplicates('route_uid')
            old=set(rs.route_uid[rs.gap.abs()>365])
            tot=sc.transit_raw(CR,R,P); part=sc.transit_raw(CR,R[R.route_uid.isin(old)],P)
            g['_stale']=g.cell_id.map((part/tot)).fillna(0).values; stale=g['_stale'].values
    # POI density (municipality)
    po=f'{W}/poi/{c}_pois.parquet'
    if os.path.exists(po):
        pois=pd.read_parquet(po,columns=['lon','lat','cat']); lat0=g.lat.mean(); f=np.cos(np.radians(lat0))
        tr=cKDTree(np.c_[g.lon*f,g.lat]); d,i=tr.query(np.c_[pois.lon*f,pois.lat],distance_upper_bound=0.003)
        ok=np.isfinite(d); inm=np.zeros(len(pois),bool); inm[ok]=g.in_muni.values[i[ok]]
        mp=g.loc[g.in_muni,'pop'].sum()
        r={'city':c,'muni_pop':float(mp),'pois_in_muni':int(inm.sum()),'pois_per_1000':float(inm.sum()/mp*1000)}
        for cat,n in pois[inm].cat.value_counts().items(): r[f'per1000_{cat}']=float(n/mp*1000)
        dens.append(r)
    for geo,col in (('urban_centre','in_uc'),('municipality','in_muni')):
        m=g[col].values; w=g['pop'].values[m]
        base={k[0]:wmean(v[m],w) for k,v in V.items() if k[1]=='main'}
        for (ix,var),v in V.items():
            mu=wmean(v[m],w); rows.append({'city':c,'geography':geo,'index':ix,'variant':var,'mean':mu,'delta':mu-base[ix]})
        if isinstance(stale,np.ndarray): rows.append({'city':c,'geography':geo,'index':'transit','variant':'stale_feed_share','mean':wmean(stale[m],w),'delta':np.nan})
    print(c,'ok',flush=True)
S=pd.DataFrame(rows); f=f'{B}/results/sensitivity.csv'
if os.path.exists(f) and sys.argv[1:]:
    old=pd.read_csv(f); S=pd.concat([old[~old.city.isin(S.city)],S],ignore_index=True)
S.to_csv(f,index=False)
Dn=pd.DataFrame(dens); f=f'{B}/results/poi_density.csv'
if os.path.exists(f) and sys.argv[1:]:
    old=pd.read_csv(f); Dn=pd.concat([old[~old.city.isin(Dn.city)],Dn],ignore_index=True)
Dn.to_csv(f,index=False)
print(S[S.geography=='municipality'].pivot_table(index=['index','variant'],columns='city',values='delta').round(1).to_string())
