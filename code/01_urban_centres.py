"""Harmonised study areas: Degree of Urbanisation 'urban centre' rule (UN Statistical Commission 2020)
applied to Kontur Population 2023-11-01 (H3 resolution 8, ~0.74 km2 cells) instead of 1 km2 squares.
Rule: cells with density >= 1500 inh/km2, contiguous (H3 edge neighbours), cluster population >= 50,000;
smoothing (add a cell if >= 4 of its 6 neighbours are in the cluster, iterate) and gap filling (holes < 15 km2).
The study area of a city is the urban centre that contains its reference point.
Usage: python 01_urban_centres.py [city ...]"""
import sys, json, numpy as np, pandas as pd, geopandas as gpd, h3, pyogrio
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
W=__import__('os').environ.get('MS_WORK','work'); OUT=__import__('os').environ.get('MS_BASE','.')+'/data/study_areas'
import os; os.makedirs(OUT,exist_ok=True)
B=json.load(open(f'{W}/bboxes.json'))
CTRY={'london':'GB','berlin':'DE','moscow':'RU','stpetersburg':'RU','paris':'FR','munich':'DE','vienna':'AT','lisbon':'PT','tokyo':'JP','osaka':'JP','amsterdam':'NL','madrid':'ES','barcelona':'ES','milan':'IT','rome':'IT','nyc':'US','chicago':'US','losangeles':'US','shanghai':'CN','beijing':'CN','shenzhen':'CN',
      'boston':'US','sanfrancisco':'US','seattle':'US','washington':'US','portland':'US','philadelphia':'US','minneapolis':'US','toronto':'CA'}
# reference point = conventional city centre (city hall / km zero), WGS84 lon,lat
REF={'london':(-0.1276,51.5072),'berlin':(13.4050,52.5200),'moscow':(37.6176,55.7558),'stpetersburg':(30.3141,59.9386),'paris':(2.3522,48.8566),'munich':(11.5755,48.1374),'vienna':(16.3731,48.2083),'lisbon':(-9.1393,38.7223),'tokyo':(139.6917,35.6895),'osaka':(135.5023,34.6937),'amsterdam':(4.8952,52.3702),'madrid':(-3.7038,40.4168),'barcelona':(2.1734,41.3851),'milan':(9.1900,45.4642),'rome':(12.4964,41.9028),'nyc':(-74.0060,40.7128),'chicago':(-87.6298,41.8781),'losangeles':(-118.2437,34.0522),'shanghai':(121.4737,31.2304),'beijing':(116.4074,39.9042),'shenzhen':(114.0579,22.5431),
     'boston':(-71.0589,42.3601),'sanfrancisco':(-122.4194,37.7749),'seattle':(-122.3321,47.6062),'washington':(-77.0369,38.9072),'portland':(-122.6765,45.5152),'philadelphia':(-75.1652,39.9526),'minneapolis':(-93.2650,44.9778),'toronto':(-79.3832,43.6532)}
def run(city):
    x0,y0,x1,y1=B[city]
    # read a margin beyond the bbox so clusters touching the bbox are detected
    m=0.6
    bb=gpd.GeoSeries([box(x0-m,y0-m,x1+m,y1+m)],crs=4326).to_crs(3857).total_bounds
    df=pyogrio.read_dataframe(f'{W}/pop/kontur_{CTRY[city]}.gpkg',bbox=tuple(bb),read_geometry=False)
    df=df[df.population>0]
    df['area']=[h3.cell_area(h,'km^2') for h in df.h3]
    df['dens']=df.population/df.area
    pop=dict(zip(df.h3,df.population)); area=dict(zip(df.h3,df.area))
    dense=set(df.h3[df.dens>=1500])
    # connected components
    comp={}; cid=0
    for h in dense:
        if h in comp: continue
        stack=[h]; comp[h]=cid
        while stack:
            c=stack.pop()
            for n in h3.grid_disk(c,1):
                if n in dense and n not in comp: comp[n]=cid; stack.append(n)
        cid+=1
    cdf=pd.DataFrame({'h3':list(comp),'c':list(comp.values())}); cdf['pop']=cdf.h3.map(pop)
    cp=cdf.groupby('c')['pop'].sum(); keep=set(cp[cp>=50000].index)
    uc={h for h,c in comp.items() if c in keep}
    # which cluster holds the reference point (or the nearest UC cell within 3 km)
    ref=h3.latlng_to_cell(REF[city][1],REF[city][0],8)
    cand=[ref]+list(h3.grid_disk(ref,4))
    target=next((comp[h] for h in cand if h in comp and comp[h] in keep),None)
    if target is None: raise SystemExit(f'{city}: no urban centre near reference point')
    cells={h for h,c in comp.items() if c==target}
    # smoothing: add cells with >=4 of 6 neighbours in the cluster (iterate until stable)
    for _ in range(10):
        add=set()
        for c in cells:
            for n in h3.grid_ring(c,1):
                if n in cells or n in add: continue
                k=sum(1 for q in h3.grid_ring(n,1) if q in cells)
                if k>=4: add.add(n)
        if not add: break
        cells|=add
    polys=[Polygon([(lng,lat) for lat,lng in h3.cell_to_boundary(h)]) for h in cells]
    g=gpd.GeoSeries([unary_union(polys)],crs=4326)
    utm=g.estimate_utm_crs(); gu=g.to_crs(utm).buffer(1).buffer(-1)
    # gap filling: holes < 15 km2
    def fill(geom):
        from shapely.geometry import MultiPolygon
        parts=geom.geoms if geom.geom_type=='MultiPolygon' else [geom]
        out=[Polygon(p.exterior,[r for r in p.interiors if Polygon(r).area>=15e6]) for p in parts]
        return unary_union(out)
    gu=gpd.GeoSeries([fill(gu.iloc[0])],crs=utm)
    poly4326=gu.to_crs(4326).iloc[0]
    # population inside (cells whose centre falls inside)
    df['inside']=[poly4326.contains(Point(h3.cell_to_latlng(h)[::-1])) for h in df.h3]
    P=df[df.inside].population.sum(); A=gu.area.iloc[0]/1e6
    touches=not box(x0,y0,x1,y1).contains(poly4326)
    res={'city':city,'country':CTRY[city],'uc_pop_kontur2023':round(float(P)),'uc_area_km2':round(A,1),'n_h3':len(cells),'utm':utm.to_string(),'exceeds_bbox':bool(touches),'bounds':[round(v,3) for v in poly4326.bounds],'n_urban_centres_in_window':len(keep)}
    gpd.GeoDataFrame([res],geometry=[poly4326],crs=4326).to_file(f'{OUT}/{city}_urban_centre.gpkg',driver='GPKG')
    print(json.dumps(res),flush=True)
    return res
if __name__=='__main__':
    cities=sys.argv[1:] or list(CTRY)
    rows=[run(c) for c in cities]
    pd.DataFrame(rows).to_csv(f'{OUT}/urban_centres_summary_{"all" if not sys.argv[1:] else "_".join(sys.argv[1:])}.csv',index=False)
