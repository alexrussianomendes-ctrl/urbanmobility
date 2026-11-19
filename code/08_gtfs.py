"""Transit supply from GTFS for the Transit Score.
For each feed: choose a reference week (Mon-Sun) inside the feed's validity, the one nearest to the common
reference week of 2026-11-16 among 'normal' weeks (weekly trips >= 90% of the median week, which excludes
holiday and disruption weeks). If the feed's service ended before the reference week, the last normal week
is used and the gap is reported.
Service level of a route = trips per week in its busiest direction (direction_id), counting every day of
the reference week. Route identity = feed + route_id (both directions are one route; the nearest stop of
the route is used later). Mode weight (Walk Score Transit Score methodology): heavy/light rail 2,
ferry/cable car/other 1.5, bus 1.
Output: $MS_WORK/transit/<city>_route_stops.parquet (route_uid, stop_lon, stop_lat, mode_w, trips_week,
route_type) and <city>_gtfs_audit.json.
Usage: python 08_gtfs.py <city>"""
import sys, os, io, json, zipfile, datetime as dt, numpy as np, pandas as pd
city=sys.argv[1]; W=__import__('os').environ.get('MS_WORK','work'); OUT=f'{W}/transit'; os.makedirs(OUT,exist_ok=True)
FEEDS=json.load(open(f'{W}/gtfs_feeds.json'))[city]
B=json.load(open(f'{W}/bboxes.json'))[city]
REF=dt.date(2026,11,16)
OVR=json.load(open(__import__('os').environ.get('MS_BASE','.')+'/code/gtfs_overrides.json'))
import re
def skey(lat,lon): return list(zip((lat/0.0015).round().astype(int),(lon/0.002).round().astype(int)))
def mode_w(rt):
    rt=int(rt)
    if rt in (0,1,2,5,12) or 100<=rt<200 or 400<=rt<500 or 900<=rt<1000: return 2.0
    if rt in (4,6,7) or 1000<=rt<1100 or 1200<=rt<1500: return 1.5
    return 1.0
def rd(z,name,**kw):
    nm=[n for n in z.namelist() if n.split('/')[-1]==name]
    if not nm: return None
    uc=kw.pop('usecols',None)
    try:
        with z.open(nm[0]) as f: d=pd.read_csv(io.TextIOWrapper(f,encoding='utf-8-sig'),dtype=str,skipinitialspace=True,**kw)
    except pd.errors.EmptyDataError: return None
    d.columns=[c.strip() for c in d.columns]
    for c in d.columns: d[c]=d[c].str.strip()
    if uc is not None:
        d=d[[c for c in d.columns if (uc(c) if callable(uc) else c in uc)]]
    return d
def active_days(cal,cd,week):
    """dict service_id -> number of active days in the 7-day week (list of dates)"""
    cnt={}
    days=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    if cal is not None and len(cal):
        cal=cal.copy(); cal['s']=pd.to_datetime(cal.start_date,format='%Y%m%d').dt.date; cal['e']=pd.to_datetime(cal.end_date,format='%Y%m%d').dt.date
        for d in week:
            col=days[d.weekday()]
            ok=cal[(cal.s<=d)&(cal.e>=d)&(cal[col]=='1')].service_id
            for s in ok: cnt[s]=cnt.get(s,0)+1
    if cd is not None and len(cd):
        cd=cd.copy(); cd['d']=pd.to_datetime(cd.date,format='%Y%m%d').dt.date
        cdw=cd[cd.d.isin(week)]
        for s,t in zip(cdw.service_id,cdw.exception_type):
            cnt[s]=cnt.get(s,0)+(1 if t=='1' else -1)
    return {k:max(0,min(7,v)) for k,v in cnt.items()}
rows=[]; audit=[]
for f in FEEDS:
    p=f'{W}/gtfs/{f}.zip'
    if not os.path.exists(p): audit.append({'feed':f,'status':'missing file'}); continue
    try: z=zipfile.ZipFile(p)
    except Exception as ex: audit.append({'feed':f,'status':f'bad zip {ex}'}); continue
    stops=rd(z,'stops.txt',usecols=lambda c:c in('stop_id','stop_lat','stop_lon','location_type','parent_station'))
    routes=rd(z,'routes.txt',usecols=lambda c:c in('route_id','route_type','route_short_name','route_long_name','agency_id'))
    trips=rd(z,'trips.txt',usecols=lambda c:c in('trip_id','route_id','service_id','direction_id'))
    cal=rd(z,'calendar.txt'); cd=rd(z,'calendar_dates.txt')
    if stops is None or routes is None or trips is None: audit.append({'feed':f,'status':'missing core files'}); continue
    # validity range
    ds=[]
    if cal is not None and len(cal): ds+= [pd.to_datetime(cal.start_date,format='%Y%m%d').min().date(), pd.to_datetime(cal.end_date,format='%Y%m%d').max().date()]
    if cd is not None and len(cd): dd=pd.to_datetime(cd.date,format='%Y%m%d'); ds+=[dd.min().date(),dd.max().date()]
    if not ds: audit.append({'feed':f,'status':'no calendar'}); continue
    v0,v1=min(ds),max(ds)
    if 'direction_id' not in trips: trips['direction_id']='0'
    trips['direction_id']=trips.direction_id.fillna('0')
    # candidate weeks
    mon0=v0-dt.timedelta(days=v0.weekday()); weeks=[]
    m=mon0
    while m<=v1:
        weeks.append(m); m+=dt.timedelta(days=7)
    if len(weeks)>80:  # thin out very long feeds: keep the 80 weeks nearest the reference/end
        kk=min(REF,v1); weeks=sorted(weeks,key=lambda w:abs((w-kk).days))[:80]
    refm=REF-dt.timedelta(days=REF.weekday())
    # reference week chosen per agency: national feeds bundle agencies whose published periods differ
    if 'agency_id' not in routes or routes.agency_id.isna().all(): routes['agency_id']='_'
    routes['agency_id']=routes.agency_id.fillna('_')
    trips=trips.merge(routes[['route_id','agency_id']],on='route_id',how='left'); trips['agency_id']=trips.agency_id.fillna('_')
    # frequency-based trips (frequencies.txt): one trips.txt row stands for (end-start)/headway departures
    trips['mult']=1.0; fq=rd(z,'frequencies.txt')
    if fq is not None and len(fq):
        def sec(t): h,m,s_=map(int,str(t).split(':')); return h*3600+m*60+s_
        fq=fq.dropna(subset=['start_time','end_time','headway_secs'])
        fq['n']=[max(sec(b)-sec(a),0)/max(float(h),1) for a,b,h in zip(fq.start_time,fq.end_time,fq.headway_secs)]
        # some feeds (e.g. St Petersburg orgp) attach the same window to every scheduled trip as an annotation;
        # if most windows are shared by several trips of the same route/service/direction, the trips are real
        # departures and frequencies.txt is not expanded
        fx=fq.merge(trips[['trip_id','route_id','service_id','direction_id']],on='trip_id')
        shared=float((fx.groupby(['route_id','service_id','direction_id','start_time','end_time']).trip_id.transform('size')>1).mean()) if len(fx) else 0
        if shared>0.5:
            audit_fq={'frequency_trips':int(len(fx)),'frequencies_ignored_as_annotation':True,'share_windows_shared':shared}
        else:
            fm=fq.groupby('trip_id').n.sum(); m_=trips.trip_id.isin(fm.index)
            trips.loc[m_,'mult']=trips.loc[m_,'trip_id'].map(fm).clip(lower=1).values
            audit_fq={'frequency_trips':int(m_.sum()),'frequency_departures':float(fm.sum()),'share_windows_shared':shared}
    else: audit_fq={'frequency_trips':0}
    trips['days']=0.0; agw={}
    for ag,tg in trips.groupby('agency_id'):
        tps=tg.groupby('service_id').mult.sum(); tot={}
        for w0 in weeks:
            wk=[w0+dt.timedelta(days=i) for i in range(7)]
            ad=active_days(cal,cd,wk); tot[w0]=sum(tps.get(s_,0)*n for s_,n in ad.items())
        tser=pd.Series(tot); tser=tser[tser>0]
        if not len(tser): continue
        normal=tser[tser>=0.9*tser.median()]
        w=min(normal.index,key=lambda x:abs((x-refm).days)); agw[ag]=w
        ad=active_days(cal,cd,[w+dt.timedelta(days=i) for i in range(7)])
        trips.loc[tg.index,'days']=tg.service_id.map(ad).fillna(0).values
    if not agw: audit.append({'feed':f,'status':'no service in any week','valid':[str(v0),str(v1)]}); continue
    w=max(agw.values(),key=lambda x:abs((x-refm).days))   # reported: the agency week furthest from the reference
    trips['days']=trips.days*trips.mult
    rdir=trips.groupby(['route_id','direction_id']).days.sum().reset_index()
    rfreq=rdir.groupby('route_id').days.max()
    # route -> stops (union over all trips), via stop_times
    st=rd(z,'stop_times.txt',usecols=['trip_id','stop_id'])
    tr=trips[['trip_id','route_id']].drop_duplicates('trip_id')
    rs=st.merge(tr,on='trip_id')[['route_id','stop_id']].drop_duplicates()
    del st
    stops=stops.dropna(subset=['stop_lat','stop_lon'])
    stops['stop_lat']=stops.stop_lat.astype(float); stops['stop_lon']=stops.stop_lon.astype(float)
    rs=rs.merge(stops[['stop_id','stop_lat','stop_lon']],on='stop_id')
    m=0.1
    rs=rs[(rs.stop_lon>B[0]-m)&(rs.stop_lon<B[2]+m)&(rs.stop_lat>B[1]-m)&(rs.stop_lat<B[3]+m)]
    for c in ('route_short_name','route_long_name'):
        if c not in routes: routes[c]=''
    routes['line']=routes.route_short_name.fillna('').str.strip().str.upper()
    routes.loc[routes.line=='','line']=routes.route_long_name.fillna('').str.strip().str.upper()
    for o in OVR.get(f,[]):
        m_=routes.line.str.match(o['line_regex'])&routes.route_type.isin(o.get('from_types',routes.route_type.unique()))
        routes.loc[m_,'route_type']=str(o['route_type'])
    routes['mode_w']=routes.route_type.map(mode_w)
    rs=rs.merge(routes[['route_id','route_type','mode_w','line']],on='route_id')
    rs['trips_week']=rs.route_id.map(rfreq).fillna(0)
    rs=rs[rs.trips_week>0]
    rs['route_uid']=f+':'+rs.route_id
    # within-feed: route_ids of the same line whose stops are >=80% covered by a busier route_id of that line
    # are the same service split by direction or variant -> not counted again (no double counting of directions)
    rs["k"]=skey(rs.stop_lat.values,rs.stop_lon.values)
    keep=[]; dropped=0
    for (ln,rt),grp in rs.groupby(['line','route_type']):
        tw=grp.drop_duplicates('route_uid').set_index('route_uid').trips_week.sort_values(ascending=False)
        seen=set()
        for ru in tw.index:
            ks=set(grp.k[grp.route_uid==ru])
            if ln and seen and len(ks & seen)>=0.8*len(ks): dropped+=1; continue
            keep.append(ru); seen|=ks
    rs=rs[rs.route_uid.isin(keep)]
    rs['feed']=f; rs['gap']=rs.route_id.map(routes.set_index('route_id').agency_id).map(lambda a:abs((refm-agw.get(a,w)).days)).fillna(abs((refm-w).days))
    rows.append(rs[['route_uid','stop_id','stop_lon','stop_lat','route_type','mode_w','trips_week','line','k','feed','gap']])
    audit.append({'feed':f,'status':'ok','valid':[str(v0),str(v1)],'ref_week_monday':str(w),'gap_days_to_ref':(refm-w).days,**audit_fq,'ref_week_by_agency':{a:str(x) for a,x in list(agw.items())[:60]},
                  'routes_in_area':int(rs.route_uid.nunique()),'route_ids_merged_same_line':dropped,'stops_in_area':int(rs.stop_id.nunique()),
                  'trips_week_in_area':float(rs.drop_duplicates('route_uid').trips_week.sum()),
                  'routes_by_weight':rs.drop_duplicates('route_uid').mode_w.value_counts().to_dict()})
    print(json.dumps(audit[-1]),flush=True)
if rows:
    R=pd.concat(rows,ignore_index=True)
    # across feeds: the same service published by two agencies/feeds. Drop the staler copy when the same mode,
    # stops >=80% shared (>=90% if either line name is empty), same line name when both are named, trips within x2.
    info=R.drop_duplicates('route_uid').set_index('route_uid')[['feed','gap','trips_week','mode_w','line']]
    ks={ru:set(g) for ru,g in R.groupby('route_uid').k}
    inv={}
    for ru,kk in ks.items():
        for k_ in kk: inv.setdefault(k_,set()).add(ru)
    drop=set(); pairs=[]
    for ru in sorted(ks,key=lambda r:(info.gap[r],-info.trips_week[r])):
        if ru in drop: continue
        cand=set().union(*[inv[k_] for k_ in ks[ru]])-{ru}-drop
        for o in cand:
            if info.feed[o]==info.feed[ru] or info.mode_w[o]!=info.mode_w[ru]: continue
            a,b=info.line[ru],info.line[o]
            if a and b and a!=b: continue
            thr=0.8 if (a and b) else 0.9
            sh=len(ks[ru]&ks[o])
            if sh>=thr*min(len(ks[ru]),len(ks[o])) and 0.5<=info.trips_week[o]/max(info.trips_week[ru],1)<=2:
                drop.add(o); pairs.append([o,ru])
    R=R[~R.route_uid.isin(drop)].drop(columns='k')
    audit.append({'cross_feed_duplicates_dropped':len(drop),'examples':pairs[:20]})
    R.to_parquet(f'{OUT}/{city}_route_stops.parquet')
json.dump(audit,open(f'{OUT}/{city}_gtfs_audit.json','w'),indent=1)
