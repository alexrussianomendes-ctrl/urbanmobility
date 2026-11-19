"""Check of the published-headway formula (08e) on cities WITH timetables.
For each metro route (route_type 1/40x) of the GTFS feeds below, the timetable of the feed's reference week gives
  - actual trips/week in the busiest direction (sum of departures from the first stop over 7 days)
  - the 'published-style' summary a timetable would give: peak headway (busiest weekday hour in 07-10/16-19),
    off-peak headway (median weekday hour 10-16), weekend headway (median Saturday hour 10-19), service span
    (first to last weekday departure)
The 08e formula is applied to that summary and compared with the actual count. The error measures the formula
only (not the quality of published figures).
Output: results/headway_formula_check.csv"""
import zipfile, json, datetime as dt, numpy as np, pandas as pd
W=__import__('os').environ.get('MS_WORK','work'); B=__import__('os').environ.get('MS_BASE','.')
CASES={'paris':'fr-paris-ile-de-france-mobilite-gtfs-1026','vienna':'at-wien-wiener-lokalbahnen-wlb-gtfs-648',
       'barcelona':'es-barcelona-transports-metropolitans-de-barcelona-tmb-gtfs-2359','tokyo':'jp-tokyo-toei-train-gtfs-3176',
       'nyc':'us-new-york-mta-new-york-city-transit-mta-gtfs-511','chicago':'us-illinois-chicago-transit-authority-cta-gtfs-389',
       'washington':'us-district-of-columbia-washington-wmata-gtfs-1847','munich':'de-bavaria-munchner-verkehrsgesellschaft-mvg-gtfs-2333',
       'milan':'it-lombardia-milan-atm-gtfs-2666','rome':'it-lazio-roma-servizi-per-la-mobilita-gtfs-1294'}
def rd(z,n,**kw):
    if n not in z.namelist(): return None
    d=pd.read_csv(z.open(n),dtype=str,**kw); d.columns=d.columns.str.strip()
    return d.apply(lambda s:s.str.strip())
def active(cal,cd,day):
    s=set()
    if cal is not None:
        wd=['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][day.weekday()]; ds=day.strftime('%Y%m%d')
        s|=set(cal[(cal[wd]=='1')&(cal.start_date<=ds)&(cal.end_date>=ds)].service_id)
    if cd is not None:
        ds=day.strftime('%Y%m%d'); x=cd[cd.date==ds]
        s|=set(x[x.exception_type=='1'].service_id); s-=set(x[x.exception_type=='2'].service_id)
    return s
def hr(t): h,m,_=map(int,t.split(':')); return h+m/60
out=[]
for city,feed in CASES.items():
    au=json.load(open(f'{W}/transit/{city}_gtfs_audit.json')); fa=[a for a in (au if isinstance(au,list) else au.get('feeds',[])) if a.get('feed')==feed]
    if not fa or 'ref_week_monday' not in fa[0]: print(city,'no audit'); continue
    mon=dt.date.fromisoformat(fa[0]['ref_week_monday'])
    z=zipfile.ZipFile(f'{W}/gtfs/{feed}.zip')
    R=rd(z,'routes.txt'); R=R[R.route_type.isin(['1','400','401','402'])]
    keep=set(pd.read_parquet(f'{W}/transit/{city}_route_stops.parquet').query('feed==@feed').route_uid.str.split(':').str[-1])
    R=R[R.route_id.isin(keep)|(len(keep)==0)]
    T=rd(z,'trips.txt'); T=T[T.route_id.isin(R.route_id)]
    if 'direction_id' not in T: T['direction_id']='0'
    T['direction_id']=T.direction_id.fillna('0')
    cal=rd(z,'calendar.txt'); cd=rd(z,'calendar_dates.txt')
    ids=set(T.trip_id); first={}
    for ch in pd.read_csv(z.open('stop_times.txt'),dtype=str,usecols=lambda c:c.strip() in('trip_id','stop_sequence','departure_time'),chunksize=2_000_000):
        ch.columns=ch.columns.str.strip(); ch=ch[ch.trip_id.str.strip().isin(ids)].copy()
        ch['seq']=ch.stop_sequence.astype(int); ch=ch.sort_values('seq').drop_duplicates('trip_id')
        for t,s,d in zip(ch.trip_id.str.strip(),ch.seq,ch.departure_time.str.strip()):
            if t not in first or s<first[t][0]: first[t]=(s,d)
    T['dep']=T.trip_id.map(lambda t:hr(first[t][1]) if t in first and isinstance(first[t][1],str) and first[t][1] else np.nan)
    days={i:active(cal,cd,mon+dt.timedelta(days=i)) for i in range(7)}
    for (rid,di),g in T.groupby(['route_id','direction_id']):
        n=sum(g.service_id.isin(days[i]).sum() for i in range(7))
        wd=g[g.service_id.isin(days[2])].dep.dropna(); sa=g[g.service_id.isin(days[5])].dep.dropna()
        if len(wd)<20: continue
        c=np.bincount(np.floor(wd).astype(int),minlength=30)
        pk=max(c[7:10].max(),c[16:19].max()); op=np.median(c[10:16]); span=wd.max()-wd.min()
        cs=np.bincount(np.floor(sa).astype(int),minlength=30) if len(sa) else None; wk=np.median(cs[10:19]) if cs is not None else op
        if pk<=0 or op<=0 or wk<=0: continue
        hp,ho,hw=60/pk,60/op,60/wk
        f=5*(4*60/hp+max(span-4,0)*60/ho)+2*(span*60/hw)
        out.append({'city':city,'route':R.set_index('route_id').route_short_name.get(rid,rid) if 'route_short_name' in R else rid,'direction':di,
                    'actual_trips_week':int(n),'formula_trips_week':round(f,1),'peak_hw':round(hp,2),'offpeak_hw':round(ho,2),'weekend_hw':round(hw,2),'span_h':round(span,2)})
    print(city,'done',flush=True)
D=pd.DataFrame(out); D=D.sort_values('actual_trips_week',ascending=False).drop_duplicates(['city','route'])   # busiest direction
D['ratio']=D.formula_trips_week/D.actual_trips_week
D.to_csv(f'{B}/results/headway_formula_check.csv',index=False)
print(D.groupby('city').ratio.describe()[['count','mean','50%','min','max']].round(2).to_string())
r=D.ratio; print('all routes n',len(r),'median ratio',round(r.median(),3),'MAPE',round((r-1).abs().mean(),3),'p10-p90',r.quantile([.1,.9]).round(2).tolist())
# effect on Transit Score: TS = a + b ln(raw); a ratio k on one route's trips scales its contribution, so for a cell
# served mostly by metro dTS ~= b ln(k)
P=json.load(open(f'{B}/code/params_calibrated.json')); b=P['transit']['b']
print('TS shift if every metro route were off by the median ratio:',round(b*np.log(r.median()),2),' p10/p90:',[round(b*np.log(x),2) for x in r.quantile([.1,.9])])
