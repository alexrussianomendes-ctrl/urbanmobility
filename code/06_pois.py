"""Destinations for the Walk Score categories, merged from OpenStreetMap (extract of planet 2026-11-09) and
Overture Maps places (release 2026-10-21.0; Meta, Microsoft, Foursquare and other sources, confidence >= 0.5,
not marked permanently closed). Overture points within 25 m of an OSM point of the same category are treated
as duplicates and dropped. Parks: OSM leisure=park/garden(public)/playground/recreation_ground/dog_park/village_green
and Overture land use parks; each polygon is reachable from access points every 100 m along its edge.
Output: $MS_WORK/poi/<city>_pois.parquet (lon, lat, cat, src) and an audit json.
Usage: python 06_pois.py <city>"""
import sys, os, json, numpy as np, pandas as pd, geopandas as gpd, osmium, shapely.wkb as wkblib
from scipy.spatial import cKDTree
city=sys.argv[1]; W=__import__('os').environ.get('MS_WORK','work'); OUT=f'{W}/poi'; os.makedirs(OUT,exist_ok=True)
CATS=['grocery','restaurants','shopping','coffee','banks','parks','schools','books','entertainment']
# ---------------- OSM
SHOP_EXCL={'car','car_repair','car_parts','tyres','motorcycle','boat','truck','vacant','no','fuel','caravan','trailer','agrarian','wholesale','funeral_directors','storage_rental','money_lender','pawnbroker','e-cigarette'}
def osm_cat(t):
    a=t.get('amenity'); s=t.get('shop'); l=t.get('leisure'); tr=t.get('tourism')
    if s in ('supermarket','grocery','greengrocer','health_food','hypermarket','food') or a=='marketplace': return 'grocery'
    if a in ('cafe',) or s in ('coffee','tea'): return 'coffee'
    if a in ('restaurant','fast_food','bar','pub','food_court','biergarten','ice_cream'): return 'restaurants'
    if a=='bank': return 'banks'
    if a=='library' or s=='books': return 'books'
    if a=='school': return 'schools'
    if a in ('cinema','theatre','arts_centre','nightclub','music_venue','concert_hall','planetarium') or tr in ('museum','gallery') or l in ('bowling_alley','escape_game','amusement_arcade'): return 'entertainment'
    if s and s not in SHOP_EXCL: return 'shopping'
    return None
PARK_L={'park','garden','playground','recreation_ground','dog_park','village_green','common'}
fab=osmium.geom.WKBFactory()
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.p=[]; s.parks=[]
    def node(s,n):
        if not n.tags: return
        t={k:v for k,v in n.tags}; c=osm_cat(t)
        if c: s.p.append((n.location.lon,n.location.lat,c,'osm',t.get('name','')))
    def area(s,a):
        t={k:v for k,v in a.tags}
        try: g=wkblib.loads(fab.create_multipolygon(a),hex=True)
        except Exception: return
        if t.get('leisure') in PARK_L and t.get('access') not in ('private','no') and not (t.get('leisure')=='garden' and t.get('garden:type') in ('residential','private')):
            s.parks.append(g)
        c=osm_cat(t)
        if c:
            p=g.representative_point(); s.p.append((p.x,p.y,c,'osm',t.get('name','')))
h=H(); h.apply_file(f'{W}/osm/{city}.osm.pbf',locations=True,idx='flex_mem')
osm=pd.DataFrame(h.p,columns=['lon','lat','cat','src','name'])
# ---------------- Overture
pl=gpd.read_parquet(f'{W}/ov/places_{city}.parquet',columns=['names','taxonomy','confidence','operating_status','geometry'])
pl=pl[(pl.confidence>=0.5)&(pl.operating_status.fillna('open')!='permanently_closed')].copy()
pl['tp']=pl.taxonomy.apply(lambda t: t['primary'] if t is not None else '').fillna('')
pl['h']=pl.taxonomy.apply(lambda t: list(t['hierarchy']) if t is not None and t['hierarchy'] is not None else [])
def ov_cat(tp,h):
    hs=set(h); h0=h[0] if h else ''
    if ('grocery' in tp or 'supermarket' in tp or tp in ('hypermarket','farmers_market','public_market','fruits_and_vegetables','greengrocer','produce_market')) and 'wholesale' not in tp: return 'grocery'
    if tp in ('coffee_shop','cafe','coffee_roastery','tea_room','bubble_tea','tea_house','internet_cafe'): return 'coffee'
    if tp in ('bookstore','library','books_music_and_video_store','comic_books_store','used_bookstore','public_library'): return 'books'
    if tp in ('bank','bank_or_credit_union','credit_union','banks'): return 'banks'
    if tp in ('school','elementary_school','middle_school','high_school','public_school','private_school','charter_school','religious_school','primary_school','secondary_school'): return 'schools'
    if tp in ('park','dog_park','playground','public_plaza','botanical_garden','skate_park','city_park','urban_park'): return 'parks'
    if tp in ('movie_theater','theatre_venue','music_venue','museum','art_museum','history_museum','science_museum','art_gallery','bowling_alley','comedy_club','opera_and_ballet','performing_arts_venue','concert_hall','cinema','jazz_and_blues','theater','theatre'): return 'entertainment'
    if h0=='food_and_drink' and (('restaurant' in hs) or ('bar' in hs) or 'restaurant' in tp or tp.endswith('_bar') or tp in ('bar','pub','gastropub','bistro','diner','pizzeria','deli','delicatessen','casual_eatery','fast_food_restaurant','izakaya','noodles','ramen','sushi_restaurant','food_court')): return 'restaurants'
    if h0=='shopping' and not any(x in tp for x in ('auto','car_','vehicle','motorcycle','boat','wholesale','real_estate','tire','rv_','manufactured_home','trailer','gas_station')): return 'shopping'
    return None
pl['cat']=[ov_cat(a,b) for a,b in zip(pl.tp,pl.h)]
pl=pl[pl.cat.notna()]
ov=pd.DataFrame({'lon':pl.geometry.x,'lat':pl.geometry.y,'cat':pl.cat,'src':'overture','name':pl.names.apply(lambda n: (n or {}).get('primary') or '')})
# ---------------- merge with dedupe (local metric approx)
lat0=float(osm.lat.median() if len(osm) else ov.lat.median()); kx=111320*np.cos(np.radians(lat0)); ky=110540
keep=[]
for c in CATS:
    a=osm[osm.cat==c]; b=ov[ov.cat==c]
    if len(a) and len(b):
        tr=cKDTree(np.c_[a.lon*kx,a.lat*ky]); d,_=tr.query(np.c_[b.lon*kx,b.lat*ky],k=1)
        b=b[d>25]
    keep+= [a,b]
P=pd.concat(keep,ignore_index=True)
# park access points from polygons (OSM + Overture land use), every 100 m along the edge
lu=gpd.read_parquet(f'{W}/ov/landuse_{city}.parquet',columns=['class','geometry'])
lu=lu[lu['class'].isin(['park','garden','playground','dog_park','recreation_ground','village_green'])&lu.geometry.geom_type.isin(['Polygon','MultiPolygon'])]
parks=gpd.GeoSeries(list(h.parks)+list(lu.geometry),crs=4326)
utm=parks.estimate_utm_crs() if len(parks) else 'EPSG:3857'
pk=parks.to_crs(utm); pk=pk[pk.area>=2000]
pts=[]
for g in pk.geometry:
    for part in (g.geoms if g.geom_type=='MultiPolygon' else [g]):
        b=part.exterior; L=b.length
        for d in np.arange(0,L,100): p=b.interpolate(d); pts.append((p.x,p.y))
if pts:
    pp=gpd.GeoSeries(gpd.points_from_xy(*zip(*pts)),crs=utm).to_crs(4326)
    P=pd.concat([P,pd.DataFrame({'lon':pp.x,'lat':pp.y,'cat':'parks','src':'park_edge','name':''})],ignore_index=True)
P.to_parquet(f'{OUT}/{city}_pois.parquet')
aud={'city':city,'osm':osm.cat.value_counts().to_dict(),'overture_conf05':pl.cat.value_counts().to_dict(),'merged':P[P.src!='park_edge'].cat.value_counts().to_dict(),'park_polygons':int(len(pk)),'park_access_points':len(pts)}
json.dump(aud,open(f'{OUT}/{city}_poi_audit.json','w'),indent=1); print(json.dumps(aud))
