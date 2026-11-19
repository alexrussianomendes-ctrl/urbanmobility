"""Package cell-level results for GIS users.
results/cells_all.gpkg: one layer per city, populated 250 m cells of the urban centre or the municipality,
  with walk, transit (main variant), bike, components and flags. EPSG:4326.
results/cells_all.csv.gz: same rows without geometry (cell centre lon/lat).
The full per-city GeoParquet files (all cells, all transit variants) stay in results/cells/."""
import os, glob, pandas as pd, geopandas as gpd
B=__import__('os').environ.get('MS_BASE','.'); out=f'{B}/results/cells_all.gpkg'
if os.path.exists(out): os.remove(out)
KEEP=['cell_id','lon','lat','pop','in_uc','in_muni','walk','transit_main','bike','bike_lane','bike_hill','transit_variant']
rows=[]
for f in sorted(glob.glob(f'{B}/results/cells/*_cells.parquet')):
    c=os.path.basename(f).replace('_cells.parquet','')
    G=gpd.read_parquet(f); G=G[(G['pop']>0)&(G.in_uc|G.in_muni)][KEEP+['geometry']].copy()
    for k in ('walk','transit_main','bike','bike_lane','bike_hill','pop'): G[k]=G[k].astype('float32').round(2)
    G.insert(0,'city',c); G.to_file(out,layer=c,driver='GPKG'); rows.append(pd.DataFrame(G.drop(columns='geometry')))
    print(c,len(G),flush=True)
pd.concat(rows).to_csv(f'{B}/results/cells_all.csv.gz',index=False,compression='gzip')
print(os.path.getsize(out)/1e6,'MB')
