"""250 m residential grid for a study area.
- Study area: urban centre polygon from 01_urban_centres.py (target cities) or a municipal polygon (validation cities).
- Cells: 250 m squares in the local UTM zone; a cell is kept if its centre lies in the study area and it has residents.
- Population: Kontur Population 2023-11-01 (H3 r8). Each hexagon's population is shared equally among the
  250 m cells whose centres fall in it (areal disaggregation; documented limitation).
Target cities: the grid covers the union of the urban centre and the municipality, with flags in_uc / in_muni so
both geographies come from one computation. Shenzhen: its urban centre is the merged Pearl River Delta cluster,
so in_uc is clipped to the Shenzhen municipality (documented). Validation cities: municipality only.
Usage: python 05_grid.py <city> [study_area.gpkg]"""
import sys, os, json, numpy as np, pandas as pd, geopandas as gpd, h3, pyogrio
from shapely.geometry import box
city=sys.argv[1]
SA=sys.argv[2] if len(sys.argv)>2 else __import__('os').environ.get('MS_BASE','.')+f'/data/study_areas/{city}_urban_centre.gpkg'
W=__import__('os').environ.get('MS_WORK','work'); OUT=f'{W}/grid'; os.makedirs(OUT,exist_ok=True)

CTRY=json.load(open(f'{W}/ctry.json'))
D=__import__('os').environ.get('MS_BASE','.')+'/data/study_areas'
MU=f'{D}/{city}_municipal.gpkg'
parts={}
if os.path.exists(SA): parts['uc']=gpd.read_file(SA).to_crs(4326).union_all()
if os.path.exists(MU): parts['muni']=gpd.read_file(MU).to_crs(4326).union_all()
if city=='shenzhen': parts['uc']=parts['uc'].intersection(parts['muni'])
sa=gpd.GeoDataFrame(geometry=[gpd.GeoSeries(list(parts.values())).union_all()],crs=4326)
utm=sa.estimate_utm_crs(); sau=sa.to_crs(utm)
x0,y0,x1,y1=sau.total_bounds; S=250.0
xs=np.arange(np.floor(x0/S)*S+S/2,x1+S,S); ys=np.arange(np.floor(y0/S)*S+S/2,y1+S,S)
X,Y=np.meshgrid(xs,ys); X=X.ravel(); Y=Y.ravel()
pts=gpd.GeoSeries(gpd.points_from_xy(X,Y),crs=utm)
inside=pts.within(sau.union_all()).values
ll=pts.to_crs(4326)
lon=ll.x.values; lat=ll.y.values
hx=np.array([h3.latlng_to_cell(a,b,8) for a,b in zip(lat,lon)])
# Kontur population of the hexagons touched
bb=gpd.GeoSeries([box(*sa.total_bounds).buffer(0.02)],crs=4326).to_crs(3857).total_bounds
kp=pyogrio.read_dataframe(f'{W}/pop/kontur_{CTRY[city]}.gpkg',bbox=tuple(bb),read_geometry=False)
popmap=dict(zip(kp.h3,kp.population))
n_in_hex=pd.Series(hx).value_counts()   # all cells of the bounding grid -> full hexagon coverage except at the edge
g=pd.DataFrame({'x':X,'y':Y,'lon':lon,'lat':lat,'h3':hx,'inside':inside})
for k,geom in parts.items():
    pu=gpd.GeoSeries([geom],crs=4326).to_crs(utm).iloc[0]
    g['in_'+k]=False; g.loc[inside,'in_'+k]=pts[inside].within(pu).values
g['pop']=[popmap.get(h,0.0)/n_in_hex[h] for h in hx]
g=g[g.inside&(g['pop']>0)].drop(columns='inside').reset_index(drop=True)
g['cell_id']=[f'{city}_{int(a)}_{int(b)}' for a,b in zip(g.x,g.y)]
# validation addresses (manual look-up sample): extra zero-population points so the model is evaluated at the
# exact address; flagged is_val and excluded from every population-weighted aggregate (in_uc/in_muni False)
g['is_val']=False
VS=__import__('os').environ.get('MS_BASE','.')+'/data/validation/manual_sample.csv'
NM={'Boston':'boston','San Francisco':'sanfrancisco','Seattle':'seattle','Chicago':'chicago','New York':'nyc','Los Angeles':'losangeles'}
if os.path.exists(VS):
    v=pd.read_csv(VS); v=v[v.cidade.map(NM)==city]
    if len(v):
        vx=gpd.GeoSeries(gpd.points_from_xy(v.lon,v.lat),crs=4326).to_crs(utm)
        vv=pd.DataFrame({'x':vx.x.values,'y':vx.y.values,'lon':v.lon.values,'lat':v.lat.values,'h3':'','pop':0.0,
                         'cell_id':[f'val_{i}' for i in v.id],'is_val':True})
        for k in parts: vv['in_'+k]=False
        g=pd.concat([g,vv],ignore_index=True)
g.attrs['crs']=utm.to_string()
g.to_parquet(f'{OUT}/{city}_grid.parquet')
json.dump({'city':city,'crs':utm.to_string(),'cells':len(g),'pop':float(g['pop'].sum()),
           **{f'pop_{k}':float(g.loc[g['in_'+k],'pop'].sum()) for k in parts},**{f'cells_{k}':int(g['in_'+k].sum()) for k in parts}},open(f'{OUT}/{city}_grid.json','w'))
print(city,utm.to_string(),len(g),'cells',round(g['pop'].sum()),'pop',flush=True)
