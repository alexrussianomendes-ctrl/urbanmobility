"""Point sample for manual look-up of official Walk/Transit/Bike Scores (collected by hand by the user on
walkscore.com; no automated querying, per Redfin's terms).
Design: 6 cities x 25 points. Calibration: Boston, San Francisco, Seattle. Test (held out): Chicago, New York,
Los Angeles. Within each municipality, 5 rings of distance to the centre, each holding 20% of residents;
5 points per ring drawn with probability proportional to cell population (seed fixed), at least 750 m apart.
Each point is the Overture address (with house number and street) nearest the 250 m cell centre, max 150 m.
The model is later evaluated at the address coordinates themselves.
Output: data/validation/manual_sample.csv and .xlsx"""
import json, numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
W=__import__('os').environ.get('MS_WORK','work'); OUT=__import__('os').environ.get('MS_BASE','.')+'/data/validation'
CITIES={'boston':('calibração',(-71.0589,42.3601),'Boston'),'sanfrancisco':('calibração',(-122.4194,37.7749),'San Francisco'),
        'seattle':('calibração',(-122.3321,47.6062),'Seattle'),'chicago':('teste',(-87.6298,41.8781),'Chicago'),
        'nyc':('teste',(-74.0060,40.7128),'New York'),'losangeles':('teste',(-118.2437,34.0522),'Los Angeles')}
BORO={'NEW YORK':'New York','BROOKLYN':'Brooklyn','BRONX':'Bronx','STATEN ISLAND':'Staten Island'}
rng=np.random.default_rng(20261118); rows=[]
for city,(st,ref,cname) in CITIES.items():
    g=pd.read_parquet(f'{W}/grid/{city}_grid.parquet'); crs=json.load(open(f'{W}/grid/{city}_grid.json'))['crs']
    g=g[g.in_muni].reset_index(drop=True)
    r=gpd.GeoSeries(gpd.points_from_xy([ref[0]],[ref[1]]),crs=4326).to_crs(crs).iloc[0]
    g['dist']=np.hypot(g.x-r.x,g.y-r.y); g=g.sort_values('dist').reset_index(drop=True)
    cp=g['pop'].cumsum()/g['pop'].sum(); g['ring']=np.minimum((cp*5).astype(int),4)+1
    a=pd.read_parquet(f'{W}/ov/addresses_{city}.parquet',columns=['number','street','unit','postcode','postal_city','address_levels','geometry'])
    a=a[a.number.notna()&a.street.notna()&a.unit.isna()]; a=a[a.number.astype(str).str.fullmatch(r'\d+(-\d+)?')]
    ga=gpd.GeoSeries.from_wkb(a.geometry,crs=4326); ax=ga.to_crs(crs); a=a.assign(lon=ga.x.values,lat=ga.y.values,x=ax.x.values,y=ax.y.values)
    tr=cKDTree(a[['x','y']].values); chosen=[]
    for ring in range(1,6):
        c=g[g.ring==ring]; p=(c['pop']/c['pop'].sum()).values; order=rng.choice(len(c),size=len(c),replace=False,p=p)
        k=0
        for i in order:
            cell=c.iloc[i]
            if any(np.hypot(cell.x-q[0],cell.y-q[1])<750 for q in chosen): continue
            d,j=tr.query([cell.x,cell.y])
            if d>150: continue
            ad=a.iloc[j]; lv=list(ad.address_levels) if ad.address_levels is not None else []
            state=lv[0]['value'] if lv else ''
            town=ad.postal_city if isinstance(ad.postal_city,str) else cname
            if city=='nyc' and town.upper() in BORO: town=BORO[town.upper()]
            addr=f"{ad.number} {ad.street}, {town}, {state} {ad.postcode or ''}".strip()
            rows.append({'cidade':cname,'conjunto':st,'anel':ring,'endereco':addr,'lat':round(ad.lat,6),'lon':round(ad.lon,6),
                         'cell_id':cell.cell_id,'walk_score':None,'transit_score':None,'bike_score':None,'observacao':None})
            chosen.append((cell.x,cell.y)); k+=1
            if k==5: break
S=pd.DataFrame(rows); S.insert(0,'id',np.arange(1,len(S)+1))
S.to_csv(f'{OUT}/manual_sample.csv',index=False)
INSTR=pd.DataFrame({'Como preencher':[
 'Para cada linha, abra walkscore.com no seu navegador, cole o endereço da coluna "endereco" na busca e abra a página do endereço.',
 'Copie as três notas da página: Walk Score, Transit Score e Bike Score (só o número de 0 a 100).',
 'Se o site não mostrar uma das notas, deixe a célula vazia e escreva o motivo em "observacao" (ex.: "sem Bike Score").',
 'Se o site achar outro endereço (outra rua ou cidade), não use: escreva "endereço diferente" em "observacao".',
 'Não mude as colunas id, lat, lon e cell_id: elas ligam a sua nota ao ponto do meu modelo.',
 'Quando terminar, salve o arquivo e me mande de volta nesta conversa.',
 'Amostra: 6 cidades x 25 pontos, sorteados por população em 5 anéis de distância do centro (semente fixa).']})
with pd.ExcelWriter(f'{OUT}/manual_sample.xlsx') as xw:
    INSTR.to_excel(xw,sheet_name='Instruções',index=False); S.to_excel(xw,sheet_name='Pontos',index=False)
print(S.groupby('cidade').size().to_dict()); print(S.head(8).to_string())
