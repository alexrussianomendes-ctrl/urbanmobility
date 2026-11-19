"""Compute Walk Score, Bike Score and Transit Score estimates for every cell from the stored components,
given a parameter file (params.json). Library + CLI.
Usage: python 11_scores.py <city> [params.json]  -> $MS_WORK/scores/<city>_cells.parquet"""
import sys, os, json, numpy as np, pandas as pd
W=__import__('os').environ.get('MS_WORK','work')
K={'grocery':1,'restaurants':10,'shopping':5,'coffee':2,'banks':1,'parks':1,'schools':1,'books':1,'entertainment':1}
def decay(d,p):
    """distance decay in metres. p['decay']: {'type':'table','table':[[m,f],...]} or {'type':'exp','alpha','beta','d0','cut'}"""
    dd=p['decay']; d=np.asarray(d,float)
    if dd['type']=='table':
        t=np.array(dd['table']); f=np.interp(d,t[:,0],t[:,1],right=0.0)
    else:
        f=np.where(d<=dd['d0'],1.0,np.exp(-dd['alpha']*(np.maximum(d-dd['d0'],0)/1000.0)**dd['beta']))
        f=np.where(d>dd['cut'],0.0,f)
    return np.where(np.isfinite(d),f,0.0)
def pen(v,table):
    out=np.zeros(len(v))
    for lo,hi,p in table: out[(v>=lo)&(v<hi)]=p
    return out
def walk_score(D,p):
    """D: DataFrame from 07_walk_distances. returns raw (0-100 before penalties), penalties, score, per-category points"""
    tot=0; parts={}
    for c,ws in p['walk']['weights'].items():
        cols=[f'd_{c}_{i+1}' for i in range(len(ws))]
        f=decay(D[cols].values,p['walk'])
        parts[c]=(f*np.array(ws)[None,:]).sum(1); tot=tot+parts[c]
    raw=tot/p['walk']['total_weight']*100
    pi=pen(D.int_density_mi2.values,p['walk']['intersection_penalty'])
    pb=pen(D.block_len_m.fillna(1e9).values,p['walk']['block_penalty'])
    sc=np.clip(raw*(1-pi/100-pb/100)*p['walk'].get('scale',1.0),0,100)
    return raw,pi,pb,sc,parts
def transit_raw(CR,routes,p):
    """CR: cell_id, route_uid, d_m; routes: route_uid, mode_w, trips_week"""
    t=CR.merge(routes[['route_uid','mode_w','trips_week']],on='route_uid')
    mw=p['transit'].get('mode_weights',{'2.0':2.0,'1.5':1.5,'1.0':1.0})
    w=t.mode_w.astype(float).map(lambda v: mw.get(str(v),v)).values
    t['v']=t.trips_week.values*w*decay(t.d_m.values,p['transit'] if 'decay' in p['transit'] else p['walk'])
    return t.groupby('cell_id').v.sum()
def transit_score(raw,p):
    a,b=p['transit']['a'],p['transit']['b']
    r=np.asarray(raw,float)
    return np.clip(np.where(r>0,a+b*np.log(np.maximum(r,1e-9)),0.0),0,100)
def bike_lane_raw(BK,p):
    bp=p['bike']; ring_mid=np.arange(10)*100+50
    f=np.clip(1-ring_mid/bp.get('lane_cut',1000.0),0,1)**bp.get('lane_decay_pow',1.0)
    raw=0
    for cls,wt in bp['class_weights'].items():
        raw=raw+wt*(BK[[f'L_{cls}_{r}' for r in range(10)]].values*f[None,:]).sum(1)
    return raw
def bike_score(BK,ws,p):
    bp=p['bike']
    lane=np.clip(100*bike_lane_raw(BK,p)/bp['lane_ref'],0,100)
    g=BK[bp.get('grade_col','grade_max')].fillna(0).values*100
    hill=np.clip((bp['hill_zero']-g)/(bp['hill_zero']-bp['hill_full'])*100,0,100)
    w=bp['component_weights']
    sc=(w['lanes']*lane+w['hills']*hill+w['destinations']*ws)/(w['lanes']+w['hills']+w['destinations'])
    return lane,hill,np.clip(sc*bp.get('scale',1.0)+bp.get('shift',0.0),0,100)
def compute(city,p,write=True):
    g=pd.read_parquet(f'{W}/grid/{city}_grid.parquet')
    D=pd.read_parquet(f'{W}/ws/{city}_D.parquet'); g=g.merge(D,on='cell_id')
    raw,pi,pb,ws,parts=walk_score(g,p)
    g['walk_raw']=raw; g['pen_int']=pi; g['pen_block']=pb; g['walk']=ws
    for c,v in parts.items(): g[f'pts_{c}']=v
    if os.path.exists(f'{W}/bike/{city}_bike.parquet'):
        BK=pd.read_parquet(f'{W}/bike/{city}_bike.parquet'); g=g.merge(BK,on='cell_id',how='left')
        g['bike_lane'],g['bike_hill'],g['bike']=bike_score(g,g.walk.values,p)
    for tag in ('','_osm','_hybrid','_osm_ph'):
        f=f'{W}/transit/{city}_cell_route{tag}.parquet'
        if os.path.exists(f):
            CR=pd.read_parquet(f); R=pd.read_parquet(f'{W}/transit/{city}_routes{tag}.parquet')
            tr=transit_raw(CR,R,p); g[f'transit_raw{tag}']=g.cell_id.map(tr).fillna(0).values
            g[f'transit{tag}']=transit_score(g[f'transit_raw{tag}'].values,p)
    if write:
        os.makedirs(f'{W}/scores',exist_ok=True); g.to_parquet(f'{W}/scores/{city}_cells.parquet')
    return g
def popw(g,col,w='pop'):
    m=g[col].notna(); return float((g.loc[m,col]*g.loc[m,w]).sum()/g.loc[m,w].sum())
if __name__=='__main__':
    city=sys.argv[1]; pf=sys.argv[2] if len(sys.argv)>2 else __import__('os').environ.get('MS_BASE','.')+'/code/params_default.json'
    g=compute(city,json.load(open(pf)))
    print(city,{c:round(popw(g,c),1) for c in ('walk','bike','transit') if c in g})
