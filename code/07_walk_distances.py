"""Network distances from every 250 m cell to the k nearest destinations of each Walk Score category,
plus the street-network metrics used by the pedestrian-friendliness penalties.
Walking graph: OSM ways usable on foot (02_osm_network.py), components with < 200 nodes dropped.
Distances: pandana contraction hierarchies on edge length; the cell->node snap distance is added.
Output: $MS_WORK/ws/<city>_D.parquet (cell_id, d_<cat>_<k> in metres, inf if none within 2.5 km,
int_density_mi2, block_len_m).
Usage: python 07_walk_distances.py <city>"""
import sys, os, json, numpy as np, pandas as pd, geopandas as gpd, pandana as pdna
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
city=sys.argv[1]; W=__import__('os').environ.get('MS_WORK','work'); OUT=f'{W}/ws'; os.makedirs(OUT,exist_ok=True)
K={'grocery':1,'restaurants':10,'shopping':5,'coffee':2,'banks':1,'parks':1,'schools':1,'books':1,'entertainment':1}
MAXD=2600.0; MI=1609.344
grid=pd.read_parquet(f'{W}/grid/{city}_grid.parquet'); crs=json.load(open(f'{W}/grid/{city}_grid.json'))['crs']
n=pd.read_parquet(f'{W}/net/{city}_nodes.parquet'); e=pd.read_parquet(f'{W}/net/{city}_edges.parquet')
xy=gpd.GeoSeries(gpd.points_from_xy(n.lon,n.lat),crs=4326).to_crs(crs); n['x']=xy.x.values; n['y']=xy.y.values
we=e[e.walk]
N=len(n); A=coo_matrix((np.ones(len(we)),(we.u.values,we.v.values)),shape=(N,N))
nc,lab=connected_components(A,directed=False); sizes=np.bincount(lab)
okn=sizes[lab]>=200
we=we[okn[we.u.values]&okn[we.v.values]]
used=np.unique(np.r_[we.u.values,we.v.values]); nn=n.iloc[used]
we=we.reset_index(drop=True)
net=pdna.Network(pd.Series(nn.x.values,index=used),pd.Series(nn.y.values,index=used),we.u,we.v,we[['length_m']].astype(float),twoway=True)   # node ids = row positions in nodes table
gid=net.get_node_ids(grid.x.values,grid.y.values)
snap=np.hypot(grid.x.values-n.x.values[gid.values],grid.y.values-n.y.values[gid.values])
out=pd.DataFrame({'cell_id':grid.cell_id.values,'snap_m':snap})
P=pd.read_parquet(f'{W}/poi/{city}_pois.parquet')
pxy=gpd.GeoSeries(gpd.points_from_xy(P.lon,P.lat),crs=4326).to_crs(crs); P['x']=pxy.x.values; P['y']=pxy.y.values
for c,k in K.items():
    sub=P[P.cat==c]
    if len(sub)==0:
        for i in range(k): out[f'd_{c}_{i+1}']=np.inf
        continue
    net.set_pois(c,MAXD,k,sub.x.values,sub.y.values)
    D=net.nearest_pois(MAXD,c,num_pois=k,max_distance=np.inf).loc[gid.values].values.astype(float)
    D=np.where(np.isfinite(D)&(D<MAXD),D+snap[:,None],np.inf)
    for i in range(k): out[f'd_{c}_{i+1}']=D[:,i]
# ---------- street metrics (street network only: roads open to general traffic incl. pedestrian streets)
st=e[e.street]
deg=pd.concat([st[['u','v']].rename(columns={'u':'a','v':'b'}),st[['v','u']].rename(columns={'v':'a','u':'b'})]).drop_duplicates().groupby('a').size()
nd=n.loc[deg.index].copy(); nd['deg']=deg.values
inter=nd[nd.deg>=3]; ixy=inter[['x','y']].values
tr=cKDTree(ixy); pairs=np.array(list(tr.query_pairs(15.0)))
parent=np.arange(len(ixy))
def f_(i):
    while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
    return i
for a,b in pairs:
    ra,rb=f_(a),f_(b)
    if ra!=rb: parent[ra]=rb
roots=np.array([f_(i) for i in range(len(ixy))])
cl=pd.DataFrame(ixy,columns=['x','y']).groupby(roots).mean().values
ends=nd[nd.deg!=2]
mid=np.c_[(n.x.values[st.u.values]+n.x.values[st.v.values])/2,(n.y.values[st.u.values]+n.y.values[st.v.values])/2]
B=800.0; Ami=np.pi*B*B/(MI*MI); G=grid[['x','y']].values
out['int_density_mi2']=np.array([len(x) for x in cKDTree(cl).query_ball_point(G,B)])/Ami
mt=cKDTree(mid); L=st.length_m.values
Lsum=np.array([L[ix].sum() for ix in mt.query_ball_point(G,B)])
et=cKDTree(ends[['x','y']].values); dg=ends.deg.values
dsum=np.array([dg[ix].sum() for ix in et.query_ball_point(G,B)])
out['block_len_m']=np.where(dsum>0,Lsum/np.maximum(dsum/2,1),np.nan)
out.to_parquet(f'{OUT}/{city}_D.parquet')
print(city,'cells',len(out),'walk nodes',len(nn),'median snap',round(float(np.median(snap)),1),'components dropped',int((sizes<200).sum()),flush=True)
