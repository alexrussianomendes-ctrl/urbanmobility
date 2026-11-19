"""Sensitivity: Moscow Walk/Bike with the data.mos.ru schools added (dataset of educational organisations, CC BY 4.0).
Each general-education organisation is a complex of several buildings given as polygons; the complexes also
contain preschool buildings that cannot be told apart, and the Walk Score school category means schools, not
kindergartens. So the main estimate leaves this dataset out, and this variant adds one point per building
(polygon centroid) of the 475 general-education organisations, dropping any within 25 m of an existing school point.
Runs 07_walk_distances.py on a temporary POI file, scores, appends rows 'datamos_schools' to results/sensitivity.csv,
then restores the main POI and distance files."""
import os, json, shutil, subprocess, numpy as np, pandas as pd, importlib.util
from shapely.geometry import shape
from scipy.spatial import cKDTree
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work'); X=f'{B}/data/moscow_datamos/ex2/escolas.csv'
def parts(g):
    out=[]
    for seg in g.split('Geometry[type=')[1:]:
        t=seg.split(',')[0].strip(); j=seg[seg.index('coordinates=')+12:]; dep=0
        for i,ch in enumerate(j):
            dep+=ch=='['; dep-=ch==']'
            if dep==0: j=j[:i+1]; break
        geo=shape({'type':t,'coordinates':json.loads(j)}); out+=list(getattr(geo,'geoms',[geo]))
    return out
E=pd.read_csv(X,sep=';',skiprows=[1],dtype=str); E=E[E['Educational organization type']=='общеобразовательная организация']
pts=[(p.centroid.x,p.centroid.y) for g in E.Geodata for p in parts(g)]
S=pd.DataFrame(pts,columns=['lon','lat'])
pf=f'{W}/poi/moscow_pois.parquet'; df=f'{W}/ws/moscow_D.parquet'
P=pd.read_parquet(pf); sch=P[P.cat=='schools']; kx=111320*np.cos(np.radians(55.75)); ky=110540
d=cKDTree(np.c_[sch.lon*kx,sch.lat*ky]).query(np.c_[S.lon*kx,S.lat*ky])[0]; S=S[d>25]
shutil.copy(pf,pf+'.main'); shutil.copy(df,df+'.main')
try:
    pd.concat([P,pd.DataFrame({'lon':S.lon,'lat':S.lat,'cat':'schools','src':'datamos_schools','name':''})],ignore_index=True).to_parquet(pf)
    subprocess.run(['python3',f'{B}/code/07_walk_distances.py','moscow'],check=True,capture_output=True)
    spec=importlib.util.spec_from_file_location('sc',f'{B}/code/11_scores.py'); sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
    Pp=json.load(open(f'{B}/code/params_calibrated.json')); g=sc.compute('moscow',Pp,write=False)
    shutil.copy(df,f'{W}/ws/moscow_D_schools.parquet')
finally:
    shutil.move(pf+'.main',pf); shutil.move(df+'.main',df)
M=pd.read_csv(f'{B}/results/city_scores.csv'); M=M[M.city=='moscow'].set_index('geography')
rows=[]
for geo,col in (('urban_centre','in_uc'),('municipality','in_muni')):
    s=g[g[col]]; w=s['pop'].values
    for k in ('walk','bike'):
        v=float((s[k].values*w).sum()/w.sum()); rows.append({'city':'moscow','geography':geo,'index':k,'variant':'datamos_schools','mean':v,'delta':v-M.loc[geo,f'{k}_mean']})
R=pd.read_csv(f'{B}/results/sensitivity.csv'); R=R[R.variant!='datamos_schools']
pd.concat([R,pd.DataFrame(rows)],ignore_index=True).to_csv(f'{B}/results/sensitivity.csv',index=False)
print('school buildings',len(pts),'added',len(S)); print(pd.DataFrame(rows).round(2).to_string())
