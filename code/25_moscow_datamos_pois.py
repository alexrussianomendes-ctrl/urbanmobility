"""Add Moscow open-data establishments (data.mos.ru, Moscow city government, licence CC BY 4.0,
https://data.mos.ru/, terms https://data.mos.ru/terms) to the Moscow destination set from 06_pois.py.
Datasets (snapshot dates in the file names, 12-18 Nov 2026):
  1903 food service (alimentacao)   -> restaurants / coffee / entertainment (night clubs)
  3304 retail (comercio)            -> grocery / shopping / books
  526  libraries (bibliotecas)      -> books
  495  cinemas, 531 theatres, 529 museums (city culture department venues only) -> entertainment
Not used: schools (dataset file over the size limit of the download route available here), the route registry.
Category rules follow the OSM rules of 06_pois.py:
  - 'кафе', 'кафетерий' -> coffee (OSM amenity=cafe); restaurants, bars, snack bars, fast food -> restaurants.
    Canteens ('столовая') and buffets ('буфет') are left out because many sit inside schools, offices and
    hospitals and are not open to the public; production kitchens and deli counters are left out too.
  - supermarkets, general food stores, greengrocers, discounters, convenience stores -> grocery; specialised food
    stores (meat, fish, bread, alcohol ...) -> shopping, as OSM shop=butcher etc. is shopping in 06_pois.py.
  - car dealers and wholesale outlets are dropped (as in 06_pois.py); book stores -> books.
Duplicates: a data.mos.ru point within 25 m of an existing OSM/Overture point of the same category is dropped,
the same rule used between Overture and OSM. Points inside one data.mos.ru dataset are kept (distinct entries).
Input: data/moscow_datamos/ex/*.csv. Output: $MS_WORK/poi/moscow_pois.parquet (original kept as
moscow_pois_osm_ov.parquet) and data/moscow_datamos/merge_audit.json."""
import os, re, json, shutil, numpy as np, pandas as pd
from scipy.spatial import cKDTree
B=__import__('os').environ.get('MS_BASE','.'); D=f'{B}/data/moscow_datamos'; X=f'{D}/ex'; W=__import__('os').path.join(__import__('os').environ.get('MS_WORK','work'),'poi')
orig=f'{W}/moscow_pois_osm_ov.parquet'
if not os.path.exists(orig): shutil.copy(f'{W}/moscow_pois.parquet',orig)
P0=pd.read_parquet(orig)
rd=lambda f: pd.read_csv(f'{X}/{f}',sep=';',skiprows=[1],dtype=str)   # row 2 holds Russian field descriptions
num=r'(-?\d+\.\d+),\s*(-?\d+\.\d+)'
def xy(df):
    s=df['Centroid'].fillna('')+' '+df['Geodata'].fillna('')
    m=s.str.extract(num); return pd.to_numeric(m[0],errors='coerce'),pd.to_numeric(m[1],errors='coerce')
rows=[]
A=rd('data-1903-17-11-2026.csv'); lo,la=xy(A)
AF={'кафе':'coffee','кафетерий':'coffee','ресторан':'restaurants','бар':'restaurants','закусочная':'restaurants',
    'предприятие быстрого обслуживания':'restaurants','ночной клуб (дискотека)':'entertainment'}
rows.append(pd.DataFrame({'lon':lo,'lat':la,'cat':A['Object type'].str.strip().map(AF),'name':A['Name'],'ds':'1903'}))
C=rd('data-3304-15-11-2026.csv'); lo,la=xy(C); ot=C['Object type'].fillna('').str.strip()
GRO={'Магазин «Продукты»','Универсам','Супермаркет','Минимаркет','Гипермаркет (продовольственный)','Гастроном',
     'Магазин «Дискаунтер»','Магазин «Овощи-фрукты»','Магазин товаров повседневного спроса'}
DROP={'Автосалон','Магазин-склад','Магазин-склад непродовольственный (опт)','Магазин «Кэш энд Кэрри»',
      'Центр оптовой и мелкооптовой непродовольственной торговли'}
cat=np.where(ot.isin(GRO),'grocery',np.where(ot=='Магазин «Книги»','books',np.where(ot.isin(DROP),None,'shopping')))
rows.append(pd.DataFrame({'lon':lo,'lat':la,'cat':cat,'name':C['Name'],'ds':'3304'}))
for f,c,ds in (('data-526-18-11-2026.csv','books','526'),('data-495-18-11-2026.csv','entertainment','495'),
               ('data-531-18-11-2026.csv','entertainment','531'),('data-529-18-11-2026.csv','entertainment','529')):
    d=rd(f); lo,la=xy(d); rows.append(pd.DataFrame({'lon':lo,'lat':la,'cat':c,'name':d['Common name'],'ds':ds}))
M=pd.concat(rows,ignore_index=True)
aud={'read':M.groupby('ds').size().to_dict(),'no_category':int(M.cat.isna().sum()),'no_coords':int(M.lon.isna().sum())}
M=M[M.cat.notna()&M.lon.between(35,39)&M.lat.between(54.5,56.5)].copy()
lat0=55.75; kx=111320*np.cos(np.radians(lat0)); ky=110540
keep=[]; dup={}
for c,b in M.groupby('cat'):
    a=P0[P0.cat==c]
    if len(a):
        d,_=cKDTree(np.c_[a.lon*kx,a.lat*ky]).query(np.c_[b.lon*kx,b.lat*ky],k=1); dup[c]=int((d<=25).sum()); b=b[d>25]
    keep.append(b)
N=pd.concat(keep,ignore_index=True)
add=pd.DataFrame({'lon':N.lon.values,'lat':N.lat.values,'cat':N.cat.values,'src':'datamos_'+N.ds.values,'name':N.name.fillna('').values})
P=pd.concat([P0,add],ignore_index=True); P.to_parquet(f'{W}/moscow_pois.parquet')
nopk=lambda p: p[p.src!='park_edge'].cat.value_counts().to_dict()
aud.update({'categorised_with_coords':M.cat.value_counts().to_dict(),'duplicates_25m':dup,'added':add.cat.value_counts().to_dict(),
            'before':nopk(P0),'after':nopk(P),'licence':'CC BY 4.0','source':'https://data.mos.ru/'})
json.dump(aud,open(f'{D}/merge_audit.json','w'),indent=1,ensure_ascii=False); print(json.dumps(aud,ensure_ascii=False,indent=1))
