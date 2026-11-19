"""Inputs for the Bike Score components at every 250 m cell.
1) Bike infrastructure: OSM facilities classed as path (separated), lane (painted) or shared (02_osm_network.py),
   sampled every 25 m; for each cell the facility length by class in 100 m Euclidean rings up to 1,000 m
   (columns L_<class>_<ring>), so the decay and class weights can be calibrated later.
2) Hills: elevation from Copernicus DEM GLO-30 (2021 release, COG on AWS) at both ends of each ridable street
   or path edge (bridges and tunnels excluded, edges >= 100 m only to limit DEM noise); grade = |dz|/length.
   Copernicus GLO-30 is a surface model (buildings, trees). Ground is approximated by a morphological opening
   (min then max filter, 7x7 pixels, about 200 m) before sampling, which removes buildings narrower than the
   window; documented limitation, sensitivity test without the filter (BIKE_DEM_RAW=1).
   Per cell: steepest grade (and 90th percentile) among edges whose midpoint lies within 200 m.
Output: $MS_WORK/bike/<city>_bike.parquet
Usage: python 10_bike_components.py <city>"""
import sys, os, json, math, numpy as np, pandas as pd, geopandas as gpd, rasterio
from scipy.ndimage import grey_opening
from rasterio.windows import from_bounds
from scipy.spatial import cKDTree
city=sys.argv[1]; W=__import__('os').environ.get('MS_WORK','work'); OUT=f'{W}/bike'; os.makedirs(OUT,exist_ok=True)
os.environ.setdefault('GDAL_HTTP_PROXY',os.environ.get('HTTPS_PROXY','')); (os.environ.setdefault('CURL_CA_BUNDLE',os.environ['CA_BUNDLE']) if os.environ.get('CA_BUNDLE') else None); os.environ['GDAL_DISABLE_READDIR_ON_OPEN']='EMPTY_DIR'
grid=pd.read_parquet(f'{W}/grid/{city}_grid.parquet'); crs=json.load(open(f'{W}/grid/{city}_grid.json'))['crs']
n=pd.read_parquet(f'{W}/net/{city}_nodes.parquet'); e=pd.read_parquet(f'{W}/net/{city}_edges.parquet')
xy=gpd.GeoSeries(gpd.points_from_xy(n.lon,n.lat),crs=4326).to_crs(crs); n['x']=xy.x.values; n['y']=xy.y.values
G=grid[['x','y']].values; out=pd.DataFrame({'cell_id':grid.cell_id.values})
# ---- 1) infrastructure rings
for cls in ('path','lane','shared'):
    b=e[e.bike_class==cls]
    if len(b)==0:
        for r in range(10): out[f'L_{cls}_{r}']=0.0
        continue
    x0,y0=n.x.values[b.u.values],n.y.values[b.u.values]; x1,y1=n.x.values[b.v.values],n.y.values[b.v.values]
    L=np.hypot(x1-x0,y1-y0); k=np.maximum(1,np.ceil(L/25).astype(int))
    rep=np.repeat(np.arange(len(b)),k); t=(np.concatenate([ (np.arange(m)+0.5)/m for m in k]))
    px=x0[rep]+(x1[rep]-x0[rep])*t; py=y0[rep]+(y1[rep]-y0[rep])*t
    seg=(b.length_m.values/k)[rep]   # network length represented by each sample
    tr=cKDTree(np.c_[px,py])
    acc=np.zeros((len(G),10))
    for i0 in range(0,len(G),5000):
        nb=tr.query_ball_point(G[i0:i0+5000],1000.0)
        for j,ix in enumerate(nb):
            if not ix: continue
            ix=np.array(ix); d=np.hypot(px[ix]-G[i0+j,0],py[ix]-G[i0+j,1])
            acc[i0+j]=np.bincount(np.minimum((d//100).astype(int),9),weights=seg[ix],minlength=10)
    for r in range(10): out[f'L_{cls}_{r}']=acc[:,r]
# ---- 2) hills
lon0,lat0,lon1,lat1=n.lon.min(),n.lat.min(),n.lon.max(),n.lat.max()
elev=np.full(len(n),np.nan)
for la in range(math.floor(lat0),math.floor(lat1)+1):
    for lo in range(math.floor(lon0),math.floor(lon1)+1):
        ns='N' if la>=0 else 'S'; ew='E' if lo>=0 else 'W'
        name=f'Copernicus_DSM_COG_10_{ns}{abs(la):02d}_00_{ew}{abs(lo):03d}_00_DEM'
        url=f'/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif'
        sel=(n.lon>=lo)&(n.lon<lo+1)&(n.lat>=la)&(n.lat<la+1)
        if not sel.any(): continue
        try:
            with rasterio.open(url) as src:
                bx=(max(lo,lon0)-0.01,max(la,lat0)-0.01,min(lo+1,lon1)+0.01,min(la+1,lat1)+0.01)
                win=from_bounds(*bx,src.transform).round_offsets().round_lengths()
                a=src.read(1,window=win).astype(float); T=src.window_transform(win)
                if os.environ.get('BIKE_DEM_RAW')!='1': a=grey_opening(a,size=(7,7))
        except Exception as ex:
            print('DEM tile missing',name,ex,flush=True); continue
        c=(n.lon.values[sel]-T.c)/T.a-0.5; r=(n.lat.values[sel]-T.f)/T.e-0.5
        c0=np.clip(np.floor(c).astype(int),0,a.shape[1]-2); r0=np.clip(np.floor(r).astype(int),0,a.shape[0]-2)
        fc=np.clip(c-c0,0,1); fr=np.clip(r-r0,0,1)
        v=(a[r0,c0]*(1-fc)*(1-fr)+a[r0,c0+1]*fc*(1-fr)+a[r0+1,c0]*(1-fc)*fr+a[r0+1,c0+1]*fc*fr)
        elev[sel.values]=v
h=e[(e.ride|(e.bike_class!=''))&(~e.bridge)&(~e.tunnel)&(e.length_m>=100)&(~e.highway.isin(['steps','motorway','motorway_link']))]
gr=np.abs(elev[h.u.values]-elev[h.v.values])/h.length_m.values
mx=(n.x.values[h.u.values]+n.x.values[h.v.values])/2; my=(n.y.values[h.u.values]+n.y.values[h.v.values])/2
ok=np.isfinite(gr); gr,mx,my=gr[ok],mx[ok],my[ok]
tr=cKDTree(np.c_[mx,my]); nb=tr.query_ball_point(G,200.0)
out['grade_max']=[float(gr[ix].max()) if ix else np.nan for ix in nb]
out['grade_p90']=[float(np.percentile(gr[ix],90)) if ix else np.nan for ix in nb]
out['elev_cell']=np.nan
out.to_parquet(f'{OUT}/{city}_bike.parquet')
print(city,'bike km',{c:round(float(e[e.bike_class==c].length_m.sum()/1000)) for c in ('path','lane','shared')},'median grade_max',round(float(np.nanmedian(out.grade_max)),4),'nan elev',int(np.isnan(elev).sum()),flush=True)
