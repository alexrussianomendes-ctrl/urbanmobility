"""Write section 8a of relatorio/02_resultados.md (municipality as the main ranking, and the dense core) from
results/city_scores.csv, rankings.csv, dense_core_scores*.csv, dense_core_rankings*.csv. Replaces an existing
section 8a. Then rebuilds relatorio/relatorio_metodologia_resultados.md (01 + 02)."""
import pandas as pd, numpy as np
from scipy.stats import spearmanr
B=__import__('os').environ.get('MS_BASE','.'); f=f'{B}/relatorio/02_resultados.md'
NAME={'london':'Londres','berlin':'Berlim','nyc':'Nova York','chicago':'Chicago','losangeles':'Los Angeles','paris':'Paris','munich':'Munique','vienna':'Viena','lisbon':'Lisboa',
      'amsterdam':'Amsterdã','madrid':'Madri','barcelona':'Barcelona','milan':'Milão','rome':'Roma','moscow':'Moscou','stpetersburg':'São Petersburgo',
      'tokyo':'Tóquio','osaka':'Osaka','shanghai':'Xangai','beijing':'Pequim','shenzhen':'Shenzhen'}
n=lambda x,d=0: f'{x:.{d}f}'.replace('.',',')
D=pd.read_csv(f'{B}/results/city_scores.csv'); R=pd.read_csv(f'{B}/results/rankings.csv')
K=pd.read_csv(f'{B}/results/dense_core_scores.csv'); KR=pd.read_csv(f'{B}/results/dense_core_rankings.csv')
rk=lambda T,geo,k,c: T[(T.geography==geo)&(T['index']==k)&(T.city==c)].iloc[0]
def sp(a,b,k):
    x=a[a['index']==k].set_index('city')['rank']; y=b[b['index']==k].set_index('city')['rank'].reindex(x.index); return spearmanr(x,y)[0]
UC,MU=R[R.geography=='urban_centre'],R[R.geography=='municipality']
o=['## 8a. Duas versões novas: município como ranking principal e núcleo denso','',
   'Pedidas depois da primeira entrega. As notas por célula são as mesmas; muda só a área sobre a qual a média é feita.','',
   '### Município como ranking principal','',
   'É o recorte do Walk Score oficial, que dá a nota da cidade dentro do limite municipal. Por isso Nova York fica em 78,7 no centro urbano harmonizado (que inclui subúrbios de Nova Jersey, Long Island e Westchester) e em 85,5 no município, a 2,5 pontos do oficial (88), dentro da margem de ±4,5. Londres entra como a Grande Londres (os 32 boroughs mais a City of London, 1.595 km²) e Berlim como o Land de Berlim (891 km²).','',
   '| Cidade | Walk (posição) | Transit (posição) | Bike (posição) |','|---|---|---|---|']
m=D[D.geography=='municipality'].sort_values('walk_mean',ascending=False)
for _,r in m.iterrows():
    c=r.city; cell=lambda k,col: f"{n(r[col])} ± {n(r[k+'_hw95'])} ({rk(R,'municipality',k,c)['rank']}º, {rk(R,'municipality',k,c).rank_best}–{rk(R,'municipality',k,c).rank_worst})"
    o.append(f"| {NAME[c]}{' (23 distritos)' if c=='tokyo' else ' (Grande Londres)' if c=='london' else ''} | {cell('walk','walk_mean')} | {cell('transit','transit_mean')} | {cell('bike','bike_mean')} |")
o+=['','A posição vem com a faixa de posições compatível com os intervalos de 95%. A cautela da seção 7 continua: os municípios têm tamanhos muito diferentes (Paris e Lisboa são só o núcleo; Xangai, Pequim e Shenzhen incluem áreas rurais), e isso pesa na nota.','',
    '### Núcleo denso (50% da densidade do lugar mais denso)','',
    '**Como foi recortado:**',
    '- **Densidade suavizada:** a densidade de cada célula de 250 m é a média das células num raio de 1,5 km (janela de cerca de 3 km), para que um conjunto isolado de prédios não defina o pico.',
    '- **Pico e limiar:** o pico é a célula de maior densidade suavizada na área de estudo; o núcleo são as células com pelo menos 50% dessa densidade.',
    '- **Contiguidade:** só entram as células ligadas ao pico por outras células acima do limiar. Bolsões densos separados ficam de fora.',
    '- **Por que não 1 km:** com janela de 1 km, o pico caiu sobre um único hexágono de população em Shenzhen, Xangai, Lisboa, Chicago, Roma e Moscou, e o núcleo encolheu para 1 a 6 km² em volta de um bloco de torres. Com raio de 1,5 km ou mais, todo núcleo tem pelo menos 20 km². Os raios de 1 e 2 km ficaram como teste.','',
    '**O pico é de moradia, não de centro histórico.** Em Lisboa ele fica no limite com a Amadora (só 15% do núcleo está dentro do município), em Moscou num bairro de prédios altos do sul, em São Petersburgo no distrito de Primorsky, em Nova York no Upper East Side, em Londres no leste, perto de Stratford, e em Berlim em Charlottenburg-Wilmersdorf. Em Paris, Madri, Milão e Barcelona o núcleo coincide com o centro.','',
    '| Cidade | Área (km²) | População (mi) | Walk | Transit | Bike |','|---|---|---|---|---|---|']
for _,r in K.sort_values('walk_mean',ascending=False).iterrows():
    o.append(f"| {NAME[r.city]} | {n(r.area_km2)} | {n(r.population/1e6,1)} | {n(r.walk_mean)} ± {n(r.walk_hw95)} | {n(r.transit_mean)} ± {n(r.transit_hw95)} | {n(r.bike_mean)} ± {n(r.bike_hw95)} |")
o+=['','O tamanho do núcleo varia muito: de 20 km² (São Petersburgo) a 634 km² (Tóquio), e de 0,35 a 11,5 milhões de habitantes. Cidades com densidade alta e uniforme (Tóquio, Osaka, Xangai) têm núcleos enormes; cidades com um pico forte e queda rápida (São Petersburgo, Moscou, Los Angeles, Roma) têm núcleos pequenos.','','**Rankings do núcleo denso** (faixa de posições entre parênteses; detalhe em `results/dense_core_rankings.csv`):']
for k in ('walk','transit','bike'):
    x=KR[KR['index']==k].sort_values('rank')
    o.append(f"- **{k.capitalize()}:** "+'; '.join(f"{r['rank']}. {NAME[r.city]} ({r.rank_best}–{r.rank_worst})" for _,r in x.iterrows())+'.')
s=lambda k: (sp(KR,MU,k),sp(KR,UC,k),sp(MU,UC,k))
w,t,b=s('walk'),s('transit'),s('bike')
R1=pd.read_csv(f'{B}/results/dense_core_rankings_r1000.csv'); R2=pd.read_csv(f'{B}/results/dense_core_rankings_r2000.csv')
r12=[min(sp(KR,R1,k),sp(KR,R2,k)) for k in ('walk','transit','bike')]
o+=['','**O recorte mexe nos rankings?**',
    f"- **Walk: pouco.** Correlação de postos de {n(w[0],2)} com o município e {n(w[1],2)} com o centro urbano. Paris e Milão seguem no topo e as cidades chinesas no fim (ainda como limite inferior); o que muda é o meio, com Los Angeles subindo (seu núcleo é Koreatown e arredores, bem servido) e São Petersburgo caindo.",
    f"- **Transit: bastante.** Correlação de {n(t[0],2)} com o município e {n(t[1],2)} com o centro urbano. Lisboa cai para 20º porque o núcleo é suburbano; São Petersburgo e Nova York sobem; Osaka fica em último. Entre município e centro urbano a correlação já era baixa ({n(t[2],2)}), porque o Transit depende muito de onde se corta a cidade.",
    f"- **Bike: moderado.** Correlação de {n(b[0],2)} com o município e {n(b[1],2)} com o centro urbano. Munique e Amsterdã seguem no topo e Shenzhen no fim.",
    f"- **Raio da suavização:** trocar 1,5 km por 1 ou 2 km dá correlação de postos de {n(min(r12),2)} ou mais com a versão principal; a maior mudança é Lisboa no Transit com raio de 1 km.",
    '- **Margem de 95%:** a mesma da versão principal. No Transit híbrido ela é recalculada pela fração do OSM dentro do núcleo: Moscou fica em ±14, São Petersburgo em ±10 e Londres em ±8.','',
    'Arquivos: `results/dense_core_scores.csv` (área, população, densidade do pico e do limiar, notas), `results/dense_core_rankings.csv`, `results/dense_core_cells.parquet` (que células entram), `results/ranking_comparison.csv` e as versões com raio de 1 e 2 km (`_r1000`, `_r2000`). Código: `code/30_dense_core.py`.','']
txt=open(f).read()
if '## 8a.' in txt:
    a=txt.index('## 8a.'); bb=txt.index('## 9.'); txt=txt[:a]+txt[bb:]
a=txt.index('## 9.'); txt=txt[:a]+'\n'.join(o)+'\n'+txt[a:]
open(f,'w').write(txt)
m1=open(f'{B}/relatorio/01_metodologia.md').read()
open(f'{B}/relatorio/relatorio_metodologia_resultados.md','w').write(m1.rstrip()+'\n\n'+txt)
print('ok')
