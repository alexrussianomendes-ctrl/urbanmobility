"""Calibration and validation against official scores.
Reference data
  - city level: official municipal scores copied by the user from walkscore.com city pages
    (data/validation/official_city_level.csv, subset of official_city_level_129.csv). The official city score is
    the population-weighted mean over the municipality, so estimates are aggregated the same way (in_muni cells).
  - point level: 150 addresses looked up by hand on walkscore.com by the user; the model is evaluated at the
    address the site actually scored (14_resolve_returned.py, 15_val_points.py); generic/unlocated rows excluded.
Split (whole cities held out)
  - calibration: Boston, San Francisco, Seattle (points + city), Washington, Portland, Philadelphia, Minneapolis (city)
  - test: Chicago, New York, Los Angeles (points + city), never used in fitting.
Fitted parameters (everything else fixed at documented / literature values)
  - Walk: decay f(d)=1 up to 0.25 mi, exp(-alpha*((d-402)/1000)^beta), 0 beyond 1.5 mi -> alpha, beta
  - Transit: TS = a + b*ln(raw) -> a, b   (decay = the Walk decay, as documented)
  - Bike: lane_ref (normalisation of the infrastructure component)
Objective: robust least squares (soft L1) where the point group and the city group carry equal total weight
(residuals divided by sqrt(group size)).
Outputs: results/validation_city_level.csv, results/validation_points.csv, results/validation_metrics.csv,
code/params_calibrated.json"""
import json, os, copy, numpy as np, pandas as pd, importlib.util
from scipy.optimize import least_squares
from scipy.stats import spearmanr
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work')
spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
P0=json.load(open(f'{B}/code/params_default.json'))
OFF=pd.read_csv(f'{B}/data/validation/official_city_level.csv').set_index('city')
PT=pd.read_csv(f'{B}/data/validation/manual_sample_resolved.csv'); PT=PT[PT.status.str.startswith('localizado')].copy()
PT['cell_id']='val_'+PT.id.astype(str)
NM={'Boston':'boston','San Francisco':'sanfrancisco','Seattle':'seattle','Chicago':'chicago','New York':'nyc','Los Angeles':'losangeles'}
PT['city']=PT.cidade.map(NM)
CAL=['boston','sanfrancisco','seattle','washington','portland','philadelphia','minneapolis']
TEST=['chicago','nyc','losangeles']
avail=[c for c in CAL+TEST if os.path.exists(f'{W}/ws/{c}_D.parquet')]
vavail=[c for c in avail if os.path.exists(f'{W}/ws/{c}__val_D.parquet')]
print('cities',avail,'point cities',vavail,flush=True)
# cache the heavy per-city tables once; walk/transit/bike are recomputed from them for each parameter set
RAW={}
for c in avail+[v+'__val' for v in vavail]:
    g=pd.read_parquet(f'{W}/grid/{c}_grid.parquet').merge(pd.read_parquet(f'{W}/ws/{c}_D.parquet'),on='cell_id')
    if not c.endswith('__val'): g=g[g.in_muni]
    else: g=g.merge(PT[['cell_id','walk_score','transit_score','bike_score']],on='cell_id')
    bk=f'{W}/bike/{c}_bike.parquet'
    if os.path.exists(bk): g=g.merge(pd.read_parquet(bk),on='cell_id',how='left')
    CR={}
    for tag in ('','_osm'):
        f=f'{W}/transit/{c}_cell_route{tag}.parquet'
        if os.path.exists(f):
            cr=pd.read_parquet(f); cr=cr[cr.cell_id.isin(g.cell_id)]
            CR[tag]=(cr,pd.read_parquet(f'{W}/transit/{c}_routes{tag}.parquet'))
    RAW[c]=(g.reset_index(drop=True),CR)
print('loaded',flush=True)
def build(c,p,need_transit=True):
    g,CR=RAW[c]; g=g.copy(); g['walk']=sc.walk_score(g,p)[3]
    if need_transit:
        for tag,(cr,R) in CR.items():
            tr=sc.transit_raw(cr,R,p); g['transit_raw'+tag]=g.cell_id.map(tr).fillna(0).values
    return g
def pw(g,v): w=g['pop'].values; return float((v*w).sum()/w.sum())
def grp(rc,rp):
    out=[np.asarray(x,float)/np.sqrt(len(x)) for x in (rc,rp) if len(x)]
    return np.concatenate(out)
def set_decay(p,x): p['walk']['decay']={'type':'exp','alpha':float(x[0]),'beta':float(x[1]),'d0':402.3,'cut':2414.0}; return p
# ---------------- Walk
def r_w(x):
    p=set_decay(copy.deepcopy(P0),x)
    rc=[pw(g,g.walk.values)-OFF.walk[c] for c in CAL if c in RAW and pd.notna(OFF.walk.get(c)) for g in [build(c,p,False)]]
    rp=np.concatenate([g.walk.values-g.walk_score.values for c in vavail if c in CAL for g in [build(c+'__val',p,False)]])
    return grp(rc,rp)
fw=least_squares(r_w,[2.5,2.0],bounds=([0.05,0.5],[30,6]),loss='soft_l1',f_scale=10,diff_step=0.05)
P=set_decay(copy.deepcopy(P0),fw.x); P['_fit']={'walk_alpha_beta':list(map(float,fw.x))}
print('walk alpha,beta',fw.x,flush=True)
G={c:build(c,P) for c in RAW}
def tsc(g,p,col='transit_raw'): return sc.transit_score(g[col].values,p) if col in g else np.full(len(g),np.nan)
def r_t(x):
    p=copy.deepcopy(P); p['transit']['a'],p['transit']['b']=x
    rc=[pw(G[c],tsc(G[c],p))-OFF.transit[c] for c in CAL if c in G and 'transit_raw' in G[c] and pd.notna(OFF.transit.get(c))]
    rp=np.concatenate([tsc(G[c+'__val'],p)-G[c+'__val'].transit_score.values for c in vavail if c in CAL])
    return grp(rc,rp)
ft=least_squares(r_t,[-50,15],bounds=([-300,0.5],[100,60]),loss='soft_l1',f_scale=10)
P['transit']['a'],P['transit']['b']=map(float,ft.x); P['_fit']['transit_a_b']=list(map(float,ft.x)); print('transit a,b',ft.x,flush=True)
def bsc(g,p): return sc.bike_score(g,g.walk.values,p)[2]
def r_b(x):
    p=copy.deepcopy(P); p['bike']['lane_ref']=float(x[0])
    rc=[pw(G[c],bsc(G[c],p))-OFF.bike[c] for c in CAL if c in G and 'L_path_0' in G[c] and pd.notna(OFF.bike.get(c))]
    rp=np.concatenate([bsc(G[c+'__val'],p)-G[c+'__val'].bike_score.values for c in vavail if c in CAL])
    return grp(rc,rp)
fb=least_squares(r_b,[2000],bounds=([100],[1e6]),loss='soft_l1',f_scale=10)
P['bike']['lane_ref']=float(fb.x[0]); P['_fit']['bike_lane_ref']=float(fb.x[0]); print('bike lane_ref',fb.x,flush=True)
json.dump(P,open(f'{B}/code/params_calibrated.json','w'),indent=1)
# ---------------- evaluation
rows=[]
for c in avail:
    g=G[c]; e={'city':c,'set':'calibration' if c in CAL else 'test','walk_est':pw(g,g.walk.values)}
    if 'transit_raw' in g: e['transit_est']=pw(g,tsc(g,P))
    if 'transit_raw_osm' in g: e['transit_osm_proxy_est']=pw(g,tsc(g,P,'transit_raw_osm'))
    if 'L_path_0' in g: e['bike_est']=pw(g,bsc(g,P))
    for k in ('walk','transit','bike'): e[k+'_official']=OFF[k].get(c,np.nan)
    rows.append(e)
VC=pd.DataFrame(rows); os.makedirs(f'{B}/results',exist_ok=True); VC.to_csv(f'{B}/results/validation_city_level.csv',index=False)
pts=[]
for c in vavail:
    v=G[c+'__val']
    pts.append(pd.DataFrame({'id':v.cell_id.str.replace('val_','').astype(int),'city':c,'set':'calibration' if c in CAL else 'test',
       'walk_est':v.walk.values,'walk_official':v.walk_score.values,
       'transit_est':tsc(v,P),'transit_osm_proxy_est':tsc(v,P,'transit_raw_osm') if 'transit_raw_osm' in v else np.nan,
       'transit_official':v.transit_score.values,'bike_est':bsc(v,P),'bike_official':v.bike_score.values}))
VP=pd.concat(pts,ignore_index=True); VP.to_csv(f'{B}/results/validation_points.csv',index=False)
BANDS=[(0,25,'0-24'),(25,50,'25-49'),(50,70,'50-69'),(70,90,'70-89'),(90,101,'90-100')]
def met(est,off):
    m=np.isfinite(est)&np.isfinite(off); e=est[m]-off[m]
    if m.sum()==0: return {}
    return {'n':int(m.sum()),'MAE':float(np.abs(e).mean()),'RMSE':float(np.sqrt((e**2).mean())),'bias':float(e.mean()),
            'spearman':float(spearmanr(est[m],off[m]).statistic) if m.sum()>2 else np.nan,'within_10':float((np.abs(e)<=10).mean())}
M=[]
for k in ('walk','transit','bike','transit_osm_proxy'):
    off=k.replace('_osm_proxy','')+'_official'
    for lvl,D in (('city',VC),('point',VP)):
        if k+'_est' not in D: continue
        for s in ('calibration','test'):
            d=D[D.set==s]; r=met(d[k+'_est'].values.astype(float),d[off].values.astype(float))
            if r: M.append({'index':k,'level':lvl,'set':s,'group':'all',**r})
            if lvl=='point':
                for c in d.city.unique():
                    dc=d[d.city==c]; r=met(dc[k+'_est'].values.astype(float),dc[off].values.astype(float))
                    if r: M.append({'index':k,'level':lvl,'set':s,'group':'city:'+c,**r})
                for lo,hi,nm in BANDS:
                    db=d[(d[off]>=lo)&(d[off]<hi)]; r=met(db[k+'_est'].values.astype(float),db[off].values.astype(float))
                    if r: M.append({'index':k,'level':lvl,'set':s,'group':'band:'+nm,**r})
M=pd.DataFrame(M); M.to_csv(f'{B}/results/validation_metrics.csv',index=False)
pd.set_option('display.width',220)
print(VC.round(1).to_string()); print(M[M.group=='all'].round(2).to_string())
print(M[(M.set=='test')&(M.group!='all')].round(1).to_string())
