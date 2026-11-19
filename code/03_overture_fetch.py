"""Download Overture Maps (release 2026-10-21.0) places, land use (parks) and division areas for each bbox.
Usage: python 03_overture_fetch.py places|landuse|divisions [city ...]"""
import sys, json, time, pyarrow.parquet as pq, pyarrow.fs as pfs, pyarrow.dataset as ds, os
P=os.environ.get('HTTPS_PROXY','')
fs=pfs.S3FileSystem(anonymous=True, region='us-west-2', proxy_options=P, tls_ca_file_path=os.environ.get('CA_BUNDLE') or None)
R='overturemaps-us-west-2/release/2026-10-21.0'
def dset(theme,typ): return ds.dataset(f'{R}/theme={theme}/type={typ}/', filesystem=fs, format='parquet')
def bf(x0,y0,x1,y1):
    f=lambda k: ds.field(('bbox',k)); return (f('xmin')<=x1)&(f('xmax')>=x0)&(f('ymin')<=y1)&(f('ymax')>=y0)
jobs={'places':('places','place',['id','names','categories','basic_category','taxonomy','confidence','operating_status','sources','geometry']),
 'landuse':('base','land_use',['id','subtype','class','names','geometry']),
 'addresses':('addresses','address',['id','number','street','unit','postcode','postal_city','address_levels','country','geometry']),
 'divisions':('divisions','division_area',['id','subtype','class','names','country','region','admin_level','division_id','geometry'])}
which=sys.argv[1]; theme,typ,cols=jobs[which]; d=dset(theme,typ); cols=[c for c in cols if c in d.schema.names]
B=json.load(open(__import__('os').environ.get('MS_WORK','work')+'/bboxes.json'))
for c in (sys.argv[2:] or list(B)):
    out=__import__('os').environ.get('MS_WORK','work')+f'/ov/{which}_{c}.parquet'
    if os.path.exists(out): continue
    x0,y0,x1,y1=B[c]; m=0.03; t=time.time()
    tb=d.to_table(columns=cols,filter=bf(x0-m,y0-m,x1+m,y1+m)); pq.write_table(tb,out)
    print(which,c,tb.num_rows,round(time.time()-t),'s',flush=True)
