"""Cut a national GTFS feed down to a city's bbox (+0.15 degrees) so 08_gtfs.py can read it in memory.
Used for London: the UK aggregate feed of the Bus Open Data Service (Mobility Database mirror,
gb-unknown-uk-aggregate-feed-gtfs-2014, 4.7 GB stop_times). Keeps stop_times rows whose stop lies in the box, the
trips that have such rows, their routes, agencies, calendars and frequencies, and the stops in the box. Trips are
not cut further: 08_gtfs.py takes each route's stops inside the box anyway.
Usage: python 08f_subset_gtfs.py <city> <feed> <out_feed>"""
import sys, json, zipfile, io, pandas as pd
city,feed,out=sys.argv[1:4]; W=__import__('os').environ.get('MS_WORK','work'); B=json.load(open(f'{W}/bboxes.json'))[city]; m=0.15
z=zipfile.ZipFile(f'{W}/gtfs/{feed}.zip')
rd=lambda n,**k: pd.read_csv(z.open(n),dtype=str,**k)
S=rd('stops.txt'); la=S.stop_lat.astype(float); lo=S.stop_lon.astype(float)
S=S[(lo>B[0]-m)&(lo<B[2]+m)&(la>B[1]-m)&(la<B[3]+m)]; keep=set(S.stop_id)
parts=[]
for ch in pd.read_csv(z.open('stop_times.txt'),dtype=str,usecols=['trip_id','stop_id','stop_sequence','arrival_time','departure_time'],chunksize=5_000_000):
    parts.append(ch[ch.stop_id.isin(keep)])
ST=pd.concat(parts); tids=set(ST.trip_id)
T=rd('trips.txt'); T=T[T.trip_id.isin(tids)]
R=rd('routes.txt'); R=R[R.route_id.isin(set(T.route_id))]
A=rd('agency.txt'); A=A[A.agency_id.isin(set(R.agency_id))] if 'agency_id' in R else A
o=zipfile.ZipFile(f'{W}/gtfs/{out}.zip','w',zipfile.ZIP_DEFLATED)
for nm,d in (('stops.txt',S),('stop_times.txt',ST),('trips.txt',T),('routes.txt',R),('agency.txt',A)):
    o.writestr(nm,d.to_csv(index=False))
sv=set(T.service_id)
for nm in ('calendar.txt','calendar_dates.txt'):
    if nm in z.namelist(): d=rd(nm); o.writestr(nm,d[d.service_id.isin(sv)].to_csv(index=False))
if 'frequencies.txt' in z.namelist():
    d=rd('frequencies.txt'); o.writestr('frequencies.txt',d[d.trip_id.isin(tids)].to_csv(index=False))
if 'feed_info.txt' in z.namelist(): o.writestr('feed_info.txt',z.read('feed_info.txt'))
o.close(); print(city,'stops',len(S),'stop_times',len(ST),'trips',len(T),'routes',len(R),'agencies',len(A))
