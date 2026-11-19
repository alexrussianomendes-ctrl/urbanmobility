"""Transit variant 'local_tagged_median' for the cities that rely on OSM routes (OSM-only and hybrid).
Why: the imputed frequency of an untimed OSM route is the median of that mode in the GTFS cities (mostly US and
Europe). In Japan this is far off for 'train' (commuter and private railways): the OSM groups of the same city that
carry an interval tag have a median of about 756 trips/week against the imputed 164. Where a city has at least
10 OSM groups of a mode with an interval tag, this variant imputes that city's own tagged median for the untimed
groups of that mode instead of the global median. Tagged routes may be busier than untagged ones, so this is an
upper-leaning alternative, reported as sensitivity, not as the main estimate.
Appends rows to results/sensitivity.csv (variant local_tagged_median) and writes results/local_tagged_medians.csv."""
import json, os, numpy as np, pandas as pd, importlib.util
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work'); T=f'{W}/transit'
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P=json.load(open(f'{B}/code/params_calibrated.json')); MED=json.load(open(f'{B}/data/transit_mode_medians.json'))['all']
MAIN={'london':'_hybrid','munich':'_hybrid','tokyo':'_hybrid','stpetersburg':'_hybrid','osaka':'_osm_ph','moscow':'_hybrid','shanghai':'_osm_ph','beijing':'_osm_ph','shenzhen':'_osm_ph'}
rows=[]; meds=[]
for c,tv in MAIN.items():
    src=next(f'{T}/{c}_route_stops{s}.parquet' for s in ('_osm_dm','_osm_ph','_osm') if os.path.exists(f'{T}/{c}_route_stops{s}.parquet'))   # _osm_dm: Moscow, OSM copies timed from data.mos.ru
    o=pd.read_parquet(src).drop_duplicates('route_uid').set_index('route_uid')
    loc={}
    for m,d in o.groupby('route'):
        t=d[d.freq_source=='osm_interval'].trips_week
        if len(t)>=10: loc[m]=float(t.median())
        meds.append({'city':c,'mode':m,'groups':len(d),'tagged':int(len(t)),'tagged_median':float(t.median()) if len(t) else np.nan,
                     'imputed_global':MED.get(m,np.nan),'used':m in loc and len(t)>=10})
    g=sc.compute(c,P,write=False)
    CR=pd.read_parquet(f'{T}/{c}_cell_route{tv}.parquet'); R=pd.read_parquet(f'{T}/{c}_routes{tv}.parquet').set_index('route_uid')
    R2=R.copy(); n=0
    for u in R2.index:
        if u in o.index and o.freq_source[u]=='imputed_mode_median' and o.route[u] in loc: R2.loc[u,'trips_week']=loc[o.route[u]]; n+=1
    base=sc.transit_score(g.cell_id.map(sc.transit_raw(CR,R.reset_index(),P)).fillna(0).values,P)
    alt=sc.transit_score(g.cell_id.map(sc.transit_raw(CR,R2.reset_index(),P)).fillna(0).values,P)
    for geo,col in (('urban_centre','in_uc'),('municipality','in_muni')):
        m=g[col].values; w=g['pop'].values[m]; b=float((base[m]*w).sum()/w.sum()); a=float((alt[m]*w).sum()/w.sum())
        rows.append({'city':c,'geography':geo,'index':'transit','variant':'local_tagged_median','mean':a,'delta':a-b})
    print(c,'replaced',n,{k:round(v) for k,v in loc.items()},rows[-1]['delta'],flush=True)
S=pd.read_csv(f'{B}/results/sensitivity.csv'); S=S[S.variant!='local_tagged_median']
pd.concat([S,pd.DataFrame(rows)],ignore_index=True).to_csv(f'{B}/results/sensitivity.csv',index=False)
pd.DataFrame(meds).to_csv(f'{B}/results/local_tagged_medians.csv',index=False)
