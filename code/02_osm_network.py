"""Build walking/street/cycling network tables from an OpenStreetMap extract (planet 2026-11-09).
Edges are split at every node shared by two or more kept ways (true graph topology, incl. footways,
crossings, steps, bridges and tunnels: a destination across a motorway is only reachable via a crossing).
Output: $MS_WORK/net/<city>_nodes.parquet (nid, osmid, lon, lat) and <city>_edges.parquet
(u, v, length_m, highway, walk, street, bike_class, ...).
Usage: python 02_osm_network.py <city> [pbf_dir]"""
import sys, os, numpy as np, pandas as pd, osmium
city=sys.argv[1]; PBF=(sys.argv[2] if len(sys.argv)>2 else __import__('os').environ.get('MS_WORK','work')+'/osm')+f'/{city}.osm.pbf'
OUT=__import__('os').environ.get('MS_WORK','work')+'/net'; os.makedirs(OUT,exist_ok=True)
NO_WALK_HW={'motorway','motorway_link','construction','proposed','raceway','bus_guideway','abandoned','platform','rest_area','services','elevator_no'}
STREET_HW={'primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','residential','unclassified','living_street','trunk','trunk_link','pedestrian'}
CAR_HW={'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','residential','unclassified','living_street','service','road'}
def walkable(t):
    hw=t.get('highway')
    if hw is None or hw in NO_WALK_HW: return False
    if t.get('foot') in ('no','private','use_sidepath'): return False
    if t.get('access') in ('no','private') and t.get('foot') not in ('yes','designated','permissive'): return False
    if hw in ('trunk','trunk_link') and t.get('sidewalk') in ('no','none') and t.get('foot') not in ('yes','designated'): return False
    if t.get('area')=='yes' and hw not in ('pedestrian','footway'): return False
    return True
def bike_class(t):
    """Bike facility class following the Bike Score definition (path > lane > shared).
    path  = physically separated: highway=cycleway, cycleway*=track/opposite_track, bicycle=designated paths
    lane  = painted on-road lane: cycleway*=lane/opposite_lane/buffered_lane
    shared= sharrow/shared lane, bus+bike lane, bicycle_road/cyclestreet
    Returns ('path'|'lane'|'shared'|'', ridable_bool)"""
    hw=t.get('highway','')
    if hw in ('motorway','motorway_link'): return '',False
    ridable = hw!='' and t.get('bicycle') not in ('no','dismount','use_sidepath') and t.get('access') not in ('no','private')
    if hw in ('footway','pedestrian','steps','corridor') and t.get('bicycle') not in ('yes','designated','permissive'): ridable=False
    if hw=='cycleway' or (hw in ('path','footway','track','bridleway','pedestrian') and t.get('bicycle')=='designated'): return 'path',True
    vals=[t.get(k,'') for k in ('cycleway','cycleway:both','cycleway:left','cycleway:right')]
    if any(v in ('track','opposite_track','separate') for v in vals): return 'path',ridable
    if any(v in ('lane','opposite_lane','buffered_lane') for v in vals): return 'lane',ridable
    if any(v in ('shared_lane','share_busway','opposite_share_busway','shared') for v in vals) or t.get('bicycle_road')=='yes' or t.get('cyclestreet')=='yes': return 'shared',ridable
    return '',ridable
class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.ways=[]; s.cnt={}
    def way(s,w):
        t={k:v for k,v in w.tags}
        if 'highway' not in t: return
        wk=walkable(t); bc,rd=bike_class(t)
        st=t['highway'] in STREET_HW and t.get('area')!='yes'
        if not (wk or rd or bc): return
        try: coords=[(n.ref,n.lon,n.lat) for n in w.nodes]
        except osmium.InvalidLocationError: coords=[(n.ref,n.lon,n.lat) for n in w.nodes if n.location.valid()]
        if len(coords)<2: return
        for r,_,_ in coords: s.cnt[r]=s.cnt.get(r,0)+1
        s.ways.append((w.id,t['highway'],wk,st,bc,rd,t['highway'] in CAR_HW,t.get('oneway',''),t.get('bridge','') not in ('','no'),t.get('tunnel','') not in ('','no'),t.get('maxspeed',''),t.get('lanes',''),coords))
h=H(); h.apply_file(PBF,locations=True,idx='flex_mem')
R=6371008.8
def hav(lo1,la1,lo2,la2):
    p1,p2=np.radians(la1),np.radians(la2); dl=np.radians(lo2-lo1); dp=p2-p1
    a=np.sin(dp/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(a))
nodes={}; E=[]
for wid,hw,wk,st,bc,rd,car,ow,br,tu,ms,ln,coords in h.ways:
    seg_start=0; L=0.0
    for i in range(1,len(coords)):
        L+=hav(coords[i-1][1],coords[i-1][2],coords[i][1],coords[i][2])
        if i==len(coords)-1 or h.cnt[coords[i][0]]>1:
            a,b=coords[seg_start],coords[i]
            if a[0]!=b[0]:
                for r,lo,la in (a,b): nodes[r]=(lo,la)
                E.append((a[0],b[0],max(L,0.5),wid,hw,wk,st,bc,rd,car,ow,br,tu,ms,ln))
            seg_start=i; L=0.0
n=pd.DataFrame([(k,v[0],v[1]) for k,v in nodes.items()],columns=['osmid','lon','lat']); n['nid']=np.arange(len(n),dtype=np.int64)
idx=dict(zip(n.osmid,n.nid))
e=pd.DataFrame(E,columns=['u','v','length_m','way_id','highway','walk','street','bike_class','ride','car','oneway','bridge','tunnel','maxspeed','lanes'])
e['u']=e.u.map(idx).astype(np.int64); e['v']=e.v.map(idx).astype(np.int64)
n.to_parquet(f'{OUT}/{city}_nodes.parquet'); e.to_parquet(f'{OUT}/{city}_edges.parquet')
print(city,'nodes',len(n),'edges',len(e),'walk',int(e.walk.sum()),'street',int(e.street.sum()),'bike km',e[e.bike_class!=''].groupby('bike_class').length_m.sum().div(1000).round(0).to_dict(),flush=True)
