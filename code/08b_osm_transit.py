"""Transit supply from OpenStreetMap route relations, for cities or operators with no usable GTFS.
This measures PHYSICAL PRESENCE of routes and stops. OSM has no timetables, so frequency is handled explicitly:
  - freq_source='osm_interval': the relation's own interval / headway tag (minutes) -> trips/week over an
    assumed 18 h service day x 7 days (assumption is a parameter, reported);
  - freq_source='imputed_mode_median': otherwise, the median weekly trips of routes of the same mode in the GTFS
    reference cities (table passed in), flagged as imputed. Scores built on imputed frequency are labelled
    'partial (physical presence + imputed frequency)' and their error is measured by running this module on
    cities that also have GTFS.
Directions: PTv2 publishes one relation per direction; relations are grouped by route_master, else by
(mode, ref) with >=80% shared stops, and counted once.
Output: $MS_WORK/transit/<city>_route_stops_osm.parquet (same columns as 08_gtfs.py) + audit json.
Usage: python 08b_osm_transit.py <city> [mode_median_json] [--modes subway,train,...]"""
import sys, os, json, numpy as np, pandas as pd, osmium
city=sys.argv[1]; W=__import__('os').environ.get('MS_WORK','work'); OUT=f'{W}/transit'; os.makedirs(OUT,exist_ok=True)
MED=json.load(open(sys.argv[2])) if len(sys.argv)>2 and not sys.argv[2].startswith('--') else None
ONLY=None
for a in sys.argv:
    if a.startswith('--modes='): ONLY=set(a.split('=')[1].split(','))
B=json.load(open(f'{W}/bboxes.json'))[city]
PBF=f'{W}/osm/{city}.osm.pbf'
MODES={'subway':(1,2.0),'light_rail':(0,2.0),'tram':(0,2.0),'train':(2,2.0),'monorail':(12,2.0),
       'trolleybus':(11,1.0),'bus':(3,1.0),'share_taxi':(3,1.0),'ferry':(4,1.5),'funicular':(7,1.5),'aerialway':(6,1.5)}
HOURS=18.0
class Rel(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.rel={}; s.master={}; s.nodes=set(); s.ways=set()
    def relation(s,r):
        t=r.tags
        if t.get('type')=='route_master':
            for m in r.members:
                if m.type=='r': s.master[m.ref]=r.id
            return
        if t.get('type')!='route' or t.get('route') not in MODES: return
        if ONLY and t.get('route') not in ONLY: return
        st=[]
        for m in r.members:
            role=m.role or ''
            if role.startswith('stop') or role.startswith('platform') or (role=='' and m.type=='n'):
                st.append((m.type,m.ref,role.startswith('stop')))
                (s.nodes if m.type=='n' else s.ways).add(m.ref)
        iv=t.get('interval') or t.get('headway')
        s.rel[r.id]={'route':t.get('route'),'ref':(t.get('ref') or t.get('name') or '').strip().upper(),
                     'interval':iv,'members':st,'operator':t.get('operator',''),'network':t.get('network','')}
class Loc(osmium.SimpleHandler):
    def __init__(s,nodes,ways): super().__init__(); s.N=nodes; s.Wy=ways; s.n={}; s.w={}; s.stoptag={}
    def node(s,n):
        if n.id in s.N and n.location.valid(): s.n[n.id]=(n.location.lon,n.location.lat)
    def way(s,w):
        if w.id in s.Wy:
            xs=[(nd.lon,nd.lat) for nd in w.nodes if nd.location.valid()]
            if xs: s.w[w.id]=(float(np.mean([x[0] for x in xs])),float(np.mean([x[1] for x in xs])))
def minutes(v):
    try:
        v=str(v).strip()
        if ':' in v: h,m=v.split(':')[:2]; return int(h)*60+int(m)
        x=float(v.split()[0]); return x if x>0 else None
    except Exception: return None
h=Rel(); h.apply_file(PBF)
L=Loc(h.nodes,h.ways); L.apply_file(PBF,locations=True)
rows=[]
for rid,r in h.rel.items():
    pts=[]
    stops=[m for m in r['members'] if m[2]] or r['members']   # prefer stop positions; else platforms
    for typ,ref,_ in stops:
        p=L.n.get(ref) if typ=='n' else L.w.get(ref)
        if p: pts.append(p)
    if len(pts)<2: continue
    for lon,lat in pts: rows.append((rid,lon,lat))
P=pd.DataFrame(rows,columns=['rid','stop_lon','stop_lat'])
m=0.1; P=P[(P.stop_lon>B[0]-m)&(P.stop_lon<B[2]+m)&(P.stop_lat>B[1]-m)&(P.stop_lat<B[3]+m)]
P['k']=list(zip((P.stop_lat/0.0015).round().astype(int),(P.stop_lon/0.002).round().astype(int)))
R=pd.DataFrame([{'rid':k,**{x:v[x] for x in ('route','ref','interval','operator','network')}} for k,v in h.rel.items() if k in set(P.rid)])
R['master']=R.rid.map(h.master)
R['ks']=R.rid.map(P.groupby('rid').k.apply(set))
# group directions: same route_master, else same (mode, ref) with >=80% of the smaller stop set shared
R['grp']=-1; g=0
for (mode,ref),sub in R.groupby(['route','ref']):
    sub=sub.sort_values('rid'); assigned={}
    for i,row in sub.iterrows():
        tgt=None
        for gid,(ks,ms) in assigned.items():
            if (pd.notna(row.master) and row.master in ms) or (ref and len(row.ks&ks)>=0.8*min(len(row.ks),len(ks))):
                tgt=gid; break
        if tgt is None: g+=1; tgt=g; assigned[tgt]=(set(row.ks),{row.master} if pd.notna(row.master) else set())
        else: assigned[tgt][0].update(row.ks); assigned[tgt][1].add(row.master) if pd.notna(row.master) else None
        R.loc[i,'grp']=tgt
R['iv_min']=R.interval.map(minutes)
G=R.groupby('grp').agg(route=('route','first'),ref=('ref','first'),iv_min=('iv_min','min'),operator=('operator','first'),
                       network=('network','first'),n_rel=('rid','size')).reset_index()
G['route_type']=G.route.map(lambda x:MODES[x][0]); G['mode_w']=G.route.map(lambda x:MODES[x][1])
G['trips_week']=np.where(G.iv_min.notna(),HOURS*60/G.iv_min.clip(lower=1)*7,np.nan)
G['freq_source']=np.where(G.iv_min.notna(),'osm_interval','none')
if MED is not None:
    miss=G.trips_week.isna()
    FB={'trolleybus':'bus','share_taxi':'bus','monorail':'subway','light_rail':'tram','funicular':'ferry','aerialway':'ferry'}
    REGION=next((a.split('=')[1] for a in sys.argv if a.startswith('--region=')),'all'); M=MED[REGION]
    G.loc[miss,'trips_week']=G.loc[miss,'route'].map(lambda x:M.get(x,M.get(FB.get(x,''),MED['all'].get(x,MED['all'].get(FB.get(x,''))))))
    G.loc[miss&G.trips_week.notna(),'freq_source']='imputed_mode_median'
P=P.merge(R[['rid','grp']],on='rid').drop_duplicates(['grp','k'])
out=P.merge(G,on='grp')
out['route_uid']='osm:'+out.grp.astype(str); out['stop_id']=out.k.astype(str); out['line']=out.ref
out['feed']='osm'; out['gap']=0
out=out[out.trips_week.notna()&(out.trips_week>0)]
out[['route_uid','stop_id','stop_lon','stop_lat','route_type','mode_w','trips_week','line','feed','gap','freq_source','route']].to_parquet(f'{OUT}/{city}_route_stops_osm.parquet')
aud={'city':city,'relations':len(h.rel),'route_groups':int(len(G)),'groups_by_mode':G.route.value_counts().to_dict(),
     'freq_source':G.freq_source.value_counts().to_dict(),'hours_per_day_assumed_for_interval':HOURS,
     'groups_with_interval_by_mode':G[G.iv_min.notna()].route.value_counts().to_dict()}
json.dump(aud,open(f'{OUT}/{city}_osm_transit_audit.json','w'),indent=1); print(json.dumps(aud))
