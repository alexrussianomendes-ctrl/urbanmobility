"""Replace imputed frequencies of rail lines in the OSM transit proxy with frequencies derived from published
headways (data/published_headways/*.csv), for cities without a usable GTFS.
Trips per week per direction (busiest direction convention, as for GTFS):
  weekday: 4 peak hours at the peak headway + (service span - 4) hours at the off-peak headway
  weekend: whole span at the weekend off-peak headway (else the weekday off-peak headway)
  service span = last - first train (published); if not given, 18 h (same assumption as OSM interval tags).
If only one of peak/off-peak is published, the missing one is imputed with the median off-peak/peak ratio of the
lines of the same city that publish both (pooled over all cities' grade A/B lines when fewer than 3) (labelled freq_source=published_headway_partial).
Matching: OSM route group 'line' (ref) normalised (digits, letters, Chinese/Japanese line suffixes removed) against
the table's line field and aliases below; only rail modes (subway, light_rail, monorail, train, tram) are touched.
Usage: python 08e_published_headways.py <city> [in_suffix=_osm]  -> transit/<city>_route_stops<in_suffix>_ph.parquet"""
import sys, re, json, glob, numpy as np, pandas as pd
city=sys.argv[1]; suf=sys.argv[2] if len(sys.argv)>2 else '_osm'
T=__import__('os').environ.get('MS_WORK','work')+'/transit'; B=__import__('os').environ.get('MS_BASE','.')
H=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f'{B}/data/published_headways/round*.csv'))],ignore_index=True)
ALL=H.copy(); H=H[H.city==city].copy()
# formula correction: on 61 timetabled metro routes in 9 GTFS cities the formula overstates weekly trips by the
# median ratio below (evening/early service is sparser than off-peak); 16_headway_formula_check.py
CK=pd.read_csv(f'{B}/results/headway_formula_check.csv'); CORR=float(CK.ratio.median())
ALIAS={'tokyo':{'G':'Ginza','M':'Marunouchi','H':'Hibiya','T':'Tozai','C':'Chiyoda','Y':'Yurakucho','Z':'Hanzomon','N':'Namboku','F':'Fukutoshin','JY':'JR Yamanote'},
       'osaka':{'M':'Midosuji','T':'Tanimachi','Y':'Yotsubashi','C':'Chuo','S':'Sennichimae','K':'Sakaisuji','N':'Nagahori Tsurumi-ryokuchi','I':'Imazatosuji','P':'New Tram'},
       'moscow':{'МЦК':'14','D1':'D1','D2':'D2','D3':'D3','D4':'D4','8А':'8A','11А':'11A'}}
def norm(s):
    s=str(s).strip(); s=re.sub(r'(号线|線|号線|Line|line|линия)','',s).strip()
    return s.upper()
def tod(t,default):
    try: h,m=map(int,str(t).split(':')); return h+m/60
    except Exception: return default
both=H.dropna(subset=['peak_min','offpeak_min'])
if len(both)<3: both=ALL[ALL.grade.isin(['A','B'])].dropna(subset=['peak_min','offpeak_min'])   # pooled across cities
ratio=float((both.offpeak_min/both.peak_min).median()) if len(both) else np.nan
rows={}
for _,r in H.iterrows():
    pk,op=r.peak_min,r.offpeak_min; src='published_headway'
    if pd.isna(pk) and pd.isna(op): continue
    if pd.isna(pk): pk=op/ratio if np.isfinite(ratio) else op; src='published_headway_partial'
    if pd.isna(op): op=pk*ratio if np.isfinite(ratio) else pk; src='published_headway_partial'
    wk=r.weekend_offpeak_min if pd.notna(r.weekend_offpeak_min) else op
    f=tod(r['first'],5.5); l=tod(r['last'],23.5); l=l+24 if l<f else l; span=l-f if pd.notna(r['first']) and pd.notna(r['last']) else 18.0
    tw=(5*(4*60/pk+max(span-4,0)*60/op)+2*(span*60/wk))/CORR
    rows[norm(r.line)]={'trips_week':tw,'freq_source':src,'span_h':span,'grade':r.grade,'source_date':r.source_date}
o=pd.read_parquet(f'{T}/{city}_route_stops{suf}.parquet')
RAIL={'subway','light_rail','monorail','train','tram'}
al={norm(k):norm(v) for k,v in ALIAS.get(city,{}).items()}
hit={}
for ru,sub in o.groupby('route_uid'):
    if sub.route.iloc[0] not in RAIL: continue
    k=norm(sub.line.iloc[0]); k=al.get(k,k)
    if k in rows: hit[ru]=k
o['ph_grade']=None
for ru,k in hit.items():
    m=o.route_uid==ru; o.loc[m,'trips_week']=rows[k]['trips_week']; o.loc[m,'freq_source']=rows[k]['freq_source']; o.loc[m,'ph_grade']=rows[k]['grade']
o.to_parquet(f'{T}/{city}_route_stops{suf}_ph.parquet')
used=sorted(set(hit.values())); unmatched=sorted(set(rows)-set(used))
rail=o.drop_duplicates('route_uid'); rail=rail[rail.route.isin(RAIL)]
a={'city':city,'input':suf,'formula_correction':CORR,'table_lines':len(rows),'matched_lines':used,'unmatched_table_lines':unmatched,'ratio_offpeak_peak':ratio,
   'osm_rail_groups':int(len(rail)),'osm_rail_groups_published':int(len(hit)),'rail_freq_source':rail.freq_source.value_counts().to_dict(),
   'rail_refs_not_matched':sorted(set(rail[~rail.route_uid.isin(hit)].line.astype(str)))[:80]}
json.dump(a,open(f'{T}/{city}_published_headways_audit.json','w'),indent=1,ensure_ascii=False); print(json.dumps(a,ensure_ascii=False))
