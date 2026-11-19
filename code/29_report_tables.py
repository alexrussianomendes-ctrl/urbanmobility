"""Rebuild the score tables (section 7) and ranking lists (section 8) of relatorio/02_resultados.md from
results/city_scores.csv and results/rankings.csv. Replaces the text between the section 7 table heading and the
'**Leitura:**' line of section 8."""
import pandas as pd
B=__import__('os').environ.get('MS_BASE','.'); f=f'{B}/relatorio/02_resultados.md'
NAME={'london':'Londres','berlin':'Berlim','nyc':'Nova York','chicago':'Chicago','losangeles':'Los Angeles','paris':'Paris','munich':'Munique','vienna':'Viena','lisbon':'Lisboa',
      'amsterdam':'Amsterdã','madrid':'Madri','barcelona':'Barcelona','milan':'Milão','rome':'Roma','moscow':'Moscou','stpetersburg':'São Petersburgo',
      'tokyo':'Tóquio','osaka':'Osaka','shanghai':'Xangai','beijing':'Pequim','shenzhen':'Shenzhen'}
VL={'gtfs':'GTFS','hybrid_gtfs_osm':'híbrida','osm_published_headways':'OSM + intervalos','osm_imputed':'OSM'}
CN={'shanghai','beijing','shenzhen'}
D=pd.read_csv(f'{B}/results/city_scores.csv'); R=pd.read_csv(f'{B}/results/rankings.csv')
n=lambda x,d=0: f'{x:.{d}f}'.replace('.',',')
out=[]
for geo,title in (('urban_centre','### Centro urbano harmonizado (geografia comparável)'),('municipality','### Município')):
    d=D[D.geography==geo].sort_values('walk_mean',ascending=False)
    out+=[title,'','| Cidade | População (mi) | Walk | Transit | Bike | Variante Transit |','|---|---|---|---|---|---|']
    for _,r in d.iterrows():
        nm=NAME[r.city]+(' (23 distritos)' if r.city=='tokyo' and geo=='municipality' else '')
        out.append(f"| {nm} | {n(r.population/1e6,1)} | {n(r.walk_mean)} ± {n(r.walk_hw95)} | {n(r.transit_mean)} ± {n(r.transit_hw95)} | {n(r.bike_mean)} ± {n(r.bike_hw95)} | {VL[r.transit_variant]} |")
    out.append('')
    if geo=='urban_centre': out+=['MARK_MUNI']
sec8=['## 8. Rankings separados','','Cada índice tem seu próprio ranking, com a faixa de posições possíveis entre parênteses. A faixa vai da melhor à pior posição compatível com os intervalos de 95%. Detalhe em `results/rankings.csv`.','']
for geo,gl in (('urban_centre','**Centro urbano harmonizado**'),('municipality','**Município**')):
    sec8.append(gl)
    for k in ('walk','transit','bike'):
        sec8.append(f'- **{k.capitalize()}:**')
        x=R[(R.geography==geo)&(R['index']==k)].sort_values('rank')
        for _,r in x.iterrows(): sec8.append(f"  {r['rank']}. {NAME[r.city]} ({r.rank_best}–{r.rank_worst}){'*' if k=='walk' and r.city in CN else ''}")
        if k=='walk': sec8+=['','  \\* limite inferior.']
    sec8.append('')
txt=open(f).read(); a=txt.index('### Centro urbano harmonizado (geografia comparável)'); b=txt.index('**Leitura:**')
mid='\n'.join(out); mid=mid.replace('MARK_MUNI\n','')
open(f,'w').write(txt[:a]+mid+'\n'+'\n'.join(sec8)+'\n'+txt[b:])
