"""Municipal (legal city) boundaries from Overture Maps divisions (release 2026-10-21.0), land class.
Each rule names the division explicitly so the choice is auditable. Writes data/study_areas/<city>_municipal.gpkg
and data/study_areas/municipal_summary.csv. Usage: python 04_municipal.py [city ...]"""
import sys, os, geopandas as gpd, pandas as pd
W=__import__('os').environ.get('MS_WORK','work'); OUT=__import__('os').environ.get('MS_BASE','.')+'/data/study_areas'; os.makedirs(OUT,exist_ok=True)
W23=['千代田区','中央区','港区','新宿区','文京区','台東区','墨田区','江東区','品川区','目黒区','大田区','世田谷区','渋谷区',
     '中野区','杉並区','豊島区','北区','荒川区','板橋区','練馬区','足立区','葛飾区','江戸川区']
LONB=['Barking and Dagenham','Barnet','Bexley','Brent','Bromley','Camden','Croydon','Ealing','Enfield','Hackney','Hammersmith and Fulham',
      'Haringey','Harrow','Havering','Hillingdon','Hounslow','Islington','Lambeth','Lewisham','Merton','Newham','Redbridge',
      'Richmond upon Thames','Southwark','Sutton','Tower Hamlets','Waltham Forest','Wandsworth']
LON=['London Borough of '+b for b in LONB]+['City of Westminster','Royal Borough of Kensington and Chelsea',
     'Royal Borough of Kingston upon Thames','Royal Borough of Greenwich','City of London']
# city: (subtype, [primary names], region or country filter, meaning)
R={'nyc':('locality',['New York','City of New York','New York City'],'US-NY','City of New York (5 boroughs)'),
 'chicago':('locality',['Chicago'],'US-IL','City of Chicago'),
 'losangeles':('locality',['Los Angeles'],'US-CA','City of Los Angeles'),
 'boston':('locality',['Boston'],'US-MA','City of Boston'),
 'sanfrancisco':('county',['San Francisco'],'US-CA','City and County of San Francisco'),
 'seattle':('locality',['Seattle'],'US-WA','City of Seattle'),
 'washington':('locality',['Washington'],'US-DC','District of Columbia'),
 'portland':('locality',['Portland'],'US-OR','City of Portland'),
 'philadelphia':('locality',['Philadelphia'],'US-PA','City of Philadelphia'),
 'minneapolis':('locality',['Minneapolis'],'US-MN','City of Minneapolis'),
 'toronto':('county',['Toronto'],'CA-ON','City of Toronto'),
 'paris':('locality',['Paris'],'FR-IDF','Commune de Paris (20 arrondissements)'),
 'munich':('county',['München','Munich'],'DE-BY','Landeshauptstadt München'),
 'vienna':('region',['Wien','Vienna'],'AT-9','Wien (Land and Gemeinde)'),
 'lisbon':('county',['Lisboa','Lisbon'],None,'Município de Lisboa'),
 'amsterdam':('locality',['Amsterdam'],None,'Gemeente Amsterdam'),
 'madrid':('locality',['Madrid'],None,'Municipio de Madrid'),
 'barcelona':('locality',['Barcelona'],None,'Municipi de Barcelona'),
 'milan':('locality',['Milano','Milan'],None,'Comune di Milano'),
 'rome':('locality',['Roma','Rome'],'IT-62','Roma Capitale (comune)'),
 'tokyo':('locality',W23,'JP-13','Tokyo 23 special wards (ku-bu); Tokyo Metropolis also reported'),
 'osaka':('county',['Osaka','大阪市'],'JP-27','Osaka-shi'),
 'moscow':('region',['Москва','Moscow'],'RU-MOW','City of federal significance incl. New Moscow'),
 'stpetersburg':('region',['Санкт-Петербург','Saint Petersburg'],None,'City of federal significance'),
 'shanghai':('region',['上海市','Shanghai'],None,'Shanghai municipality (incl. rural districts)'),
 'beijing':('region',['北京市','Beijing'],None,'Beijing municipality (incl. rural districts)'),
 'berlin':('region',['Berlin'],'DE-BE','Land Berlin (city-state)'),
 'london':('neighborhood',LON,'GB-ENG','Greater London: 32 London boroughs + City of London'),
 'shenzhen':('county',['深圳市','Shenzhen'],'CN-GD','Shenzhen-shi (prefecture-level city)')}
rows=[]
for c in (sys.argv[1:] or R):
    st,names,reg,meaning=R[c]
    d=gpd.read_parquet(f'{W}/ov/divisions_{c}.parquet'); d['nm']=d.names.map(lambda x:x['primary'] if x is not None else '')
    s=d[(d.subtype==st)&d.nm.isin(names)&(d['class']=='land')] if c!='london' else d[d.nm.isin(names)&(d['class']=='land')]   # boroughs come as neighborhood/macrohood, the City as county
    if reg: s=s[(s.region==reg)|(s.country==reg)]
    if c=='nyc' and not len(s): s=d[(d.subtype=='locality')&d.nm.str.contains('New York')&(d.region=='US-NY')&(d['class']=='land')]
    if not len(s): rows.append({'city':c,'status':'NOT FOUND'}); print(c,'NOT FOUND'); continue
    if c=='london': s=s.drop_duplicates('nm')
    if c not in ('tokyo','london') and len(s)>1: s=s.assign(a=s.area).sort_values('a',ascending=False).head(1)
    g=gpd.GeoDataFrame({'city':[c],'meaning':[meaning],'ids':[';'.join(s.id)]},geometry=[s.union_all()],crs=4326)
    km2=float(g.to_crs(g.estimate_utm_crs()).area.iloc[0]/1e6)
    g.to_file(f'{OUT}/{c}_municipal.gpkg',driver='GPKG')
    rows.append({'city':c,'status':'ok','meaning':meaning,'overture_subtype':st,'n_units':len(s),'km2':round(km2,1)})
    print(c,st,len(s),round(km2,1),flush=True)
S=pd.DataFrame(rows); fo=f'{OUT}/municipal_summary.csv'
if sys.argv[1:] and os.path.exists(fo): o=pd.read_csv(fo); S=pd.concat([o[~o.city.isin(S.city)],S],ignore_index=True)
S.to_csv(fo,index=False)
