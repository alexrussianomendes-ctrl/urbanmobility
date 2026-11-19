"""Walking network distance from every 250 m cell to the nearest stop of every transit route within 2,414 m
(1.5 mi, the Walk Score cut-off that the Transit Score methodology reuses).
Stops of all routes are snapped to the walking graph; distance = cell snap + network path + stop snap.
Output: $MS_WORK/transit/<city>_cell_route.parquet (cell_id, route_uid, d_m) and the route table
(route_uid, mode_w, trips_week, route_type).
Usage: python 09_transit_distances.py <city> [route_stops_parquet]"""
import sys, os, json, numpy as np, pandas as pd, geopandas as gpd, pandana as pdna
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
city=sys.argv[1]; W=__import__('os').environ.get('MS_WORK','work')
RS=sys.argv[2] if len(sys.argv)>2 else f'{W}/transit/{city}_route_stops.parquet'
tag='' if len(sys.argv)<=2 else '_'+os.path.basename(RS).replace('.parquet','').replace(f'{city}_route_stops','').strip('_')
CUT=2414.0
grid=pd.read_parquet(f'{W}/grid/{city}_grid.parquet'); crs=json.load(open(f'{W}/grid/{city}_grid.json'))['crs']
n=pd.read_parquet(f'{W}/net/{city}_nodes.parquet'); e=pd.read_parquet(f'{W}/net/{city}_edges.parquet')
xy=gpd.GeoSeries(gpd.points_from_xy(n.lon,n.lat),crs=4326).to_crs(crs); n['x']=xy.x.values; n['y']=xy.y.values
we=e[e.walk]; N=len(n)
A=coo_matrix((np.ones(len(we)),(we.u.values,we.v.values)),shape=(N,N)); _,lab=connected_components(A,directed=False)
sizes=np.bincount(lab); okn=sizes[lab]>=200
we=we[okn[we.u.values]&okn[we.v.values]]
used=np.unique(np.r_[we.u.values,we.v.values]); nn=n.iloc[used]
we=we.reset_index(drop=True)
net=pdna.Network(pd.Series(nn.x.values,index=used),pd.Series(nn.y.values,index=used),we.u,we.v,we[['length_m']].astype(float),twoway=True)   # node ids = row positions in nodes table
rs=pd.read_parquet(RS)
sxy=gpd.GeoSeries(gpd.points_from_xy(rs.stop_lon,rs.stop_lat),crs=4326).to_crs(crs)
rs['x']=np.round(sxy.x.values,1); rs['y']=np.round(sxy.y.values,1)
S=rs[['x','y']].drop_duplicates().reset_index(drop=True); S['sid']=np.arange(len(S))
rs=rs.merge(S,on=['x','y'])
S['node']=net.get_node_ids(S.x.values,S.y.values).values
S['snap']=np.hypot(S.x.values-n.x.values[S.node.values],S.y.values-n.y.values[S.node.values])
routes=rs.drop_duplicates('route_uid')[['route_uid','mode_w','trips_week','route_type']].reset_index(drop=True)
routes['rix']=np.arange(len(routes)); rs=rs.merge(routes[['route_uid','rix']],on='route_uid')
sr=rs[['sid','rix']].drop_duplicates()
g_node=net.get_node_ids(grid.x.values,grid.y.values).values
g_snap=np.hypot(grid.x.values-n.x.values[g_node],grid.y.values-n.y.values[g_node])
tr=cKDTree(S[['x','y']].values); G=grid[['x','y']].values
out=[]; CH=1500
for i0 in range(0,len(grid),CH):
    idx=np.arange(i0,min(i0+CH,len(grid)))
    nb=tr.query_ball_point(G[idx],CUT)
    ci=np.repeat(idx,[len(x) for x in nb]); si=np.concatenate([np.array(x,dtype=np.int64) for x in nb]) if len(ci) else np.array([],dtype=np.int64)
    if len(ci)==0: continue
    d=net.shortest_path_lengths(g_node[ci],S.node.values[si])
    d=np.asarray(d,dtype=float)+g_snap[ci]+S.snap.values[si]
    ok=d<=CUT; ci,si,d=ci[ok],si[ok],d[ok]
    pr=pd.DataFrame({'ci':ci,'sid':si,'d':d}).merge(sr,on='sid')
    pr=pr.groupby(['ci','rix'],sort=False).d.min().reset_index()
    out.append(pr)
    print(city,i0,len(pr),flush=True) if (i0//CH)%10==0 else None
O=pd.concat(out,ignore_index=True)
O['cell_id']=grid.cell_id.values[O.ci.values]
O=O.merge(routes[['rix','route_uid']],on='rix')[['cell_id','route_uid','d']].rename(columns={'d':'d_m'})
O.to_parquet(f'{W}/transit/{city}_cell_route{tag}.parquet'); routes.drop(columns='rix').to_parquet(f'{W}/transit/{city}_routes{tag}.parquet')
print(city,'pairs',len(O),'routes',len(routes),'stops',len(S),'cells with any route',O.cell_id.nunique(),'/',len(grid),flush=True)
