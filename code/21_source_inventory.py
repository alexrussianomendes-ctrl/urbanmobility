"""Source inventory with licences and audit fields -> results/source_inventory.csv
One row per data source actually used (or tried and blocked). GTFS rows come from the per-city GTFS audits
(status, validity, reference week, distance in days from the reference week) joined with the Mobility Database
catalogue (provider, official flag, licence URL as the catalogue gives it). Published-headway rows come from
data/published_headways/round1.csv. The rest are written out by hand from what was used."""
import json, os, glob, pandas as pd
B=__import__('os').environ.get('MS_BASE','.'); W=__import__('os').environ.get('MS_WORK','work')
CAT=os.environ.get('MDB_SOURCES','sources.csv')
cat=pd.read_csv(CAT,dtype=str).set_index('mdb_source_id') if os.path.exists(CAT) else None
rows=[]
def add(**k): rows.append(k)
# ---- static sources
add(source='OpenStreetMap (planet 2026-11-09, AWS osm-pds)',owner='OpenStreetMap contributors',role='rede de ruas para caminhada; ciclovias/ciclofaixas; destinos (POIs); rotas de transporte sem GTFS (relations route=*)',
    cities='todas',url='https://registry.opendata.aws/osm/',license='ODbL 1.0',license_url='https://opendatacommons.org/licenses/odbl/1-0/',date='2026-11-09',coverage='global; completude varia (baixa em POIs na China)',access='ok',notes='atribuição obrigatória; derivados compartilhados sob ODbL')
add(source='Overture Maps Places (release 2026-10-21.0)',owner='Overture Maps Foundation',role='destinos (POIs) com confiança >= 0,5, mesclados com OSM',cities='todas',url='https://docs.overturemaps.org/',
    license='CDLA Permissive 2.0',license_url='https://cdla.dev/permissive-2-0/',date='2026-10-21',coverage='global; fraca na China',access='ok',notes='')
add(source='Overture Maps Divisions',owner='Overture Maps Foundation (dados de OSM e outros)',role='limites municipais',cities='todas',url='https://docs.overturemaps.org/',
    license='ODbL 1.0',license_url='https://opendatacommons.org/licenses/odbl/1-0/',date='2026-10-21',coverage='global',access='ok',notes='Tóquio = união dos 23 distritos; Moscou = cidade federal (inclui Nova Moscou); cidades chinesas = município inteiro')
add(source='Kontur Population (2023-11-01, H3 r8)',owner='Kontur',role='população para grade de 250 m, regra DEGURBA de centro urbano e ponderação',cities='todas',url='https://data.humdata.org/organization/kontur',
    license='CC BY 4.0',license_url='https://creativecommons.org/licenses/by/4.0/',date='2023-11-01',coverage='global',access='ok (espelho S3); HDX bloqueado',notes='GHSL/GHS-FUA não acessível deste ambiente -> centro urbano refeito pela regra DEGURBA na grade Kontur')
add(source='Copernicus DEM GLO-30',owner='ESA / Comissão Europeia (Airbus)',role='declividade para Bike Score (DSM com abertura morfológica 7x7 como aproximação do terreno)',cities='todas',url='https://registry.opendata.aws/copernicus-dem/',
    license='Licença Copernicus DEM GLO-30 (uso livre, com atribuição)',license_url='https://spacedata.copernicus.eu/documents/20123/121286/CSCDA_ESA_Mission-specific+Annex_31_Oct_22.pdf',date='2021 (versão pública)',coverage='global',access='ok',notes='é modelo de superfície (DSM): prédios elevam a declividade; mitigado pela abertura')
add(source='Mobility Database (catálogo e espelho de GTFS)',owner='MobilityData',role='lista de feeds GTFS e licenças declaradas',cities='todas com GTFS',url='https://mobilitydatabase.org/',
    license='catálogo: CC0 / feeds: licença de cada operador (coluna license_url)',license_url='https://github.com/MobilityData/mobility-database-catalogs',date='2026-11-18',coverage='sem China; Rússia só metrô de SPb (desatualizado); Japão só Toei em Tóquio',access='ok',notes='')
add(source='Walk Score: metodologia pública (methodology.shtml, transit-score-methodology, bike-score-methodology) e patente US 9677892',owner='Walk Score / Redfin',role='especificação documentada dos índices',cities='-',url='https://www.walkscore.com/methodology.shtml',
    license='leitura apenas',license_url='https://www.redfin.com/about/terms-of-use',date='lida 2026-11-18',coverage='-',access='ok (página)',notes='Termos Redfin §2.3.5 proíbem consulta automatizada: nenhuma coleta automática de notas. Uma página de cidade (Chicago) foi lida antes da leitura dos termos; registrado no relatório.')
add(source='Notas oficiais por cidade (citações de terceiros, fev/2026) e tabela de 129 cidades enviada pelo usuário',owner='Walk Score via radicalstorage.com, homes.com; tabela do usuário',role='validação em nível de cidade',cities='10 cidades dos EUA',url='data/validation/official_city_level.csv',
    license='citação para validação; não redistribuídas como base',license_url='',date='2026-02 / 2026-11',coverage='10 das 129 cidades entram (as que têm os insumos processados)',access='ok',notes='')
add(source='Notas oficiais por endereço coletadas manualmente pelo usuário (150 endereços)',owner='usuário (consulta manual em walkscore.com)',role='validação por ponto',cities='Boston, SF, Seattle, Chicago, NYC, LA',url='data/validation/manual_sample_filled.csv',
    license='coleta manual pelo usuário',license_url='',date='2026-11-18',coverage='120 de 150 usados (20 genéricos, 10 sem localização segura)',access='ok',notes='')
add(source='Literatura: Kim et al. 2019; Statistics Canada 2015; Winters et al. 2016 (IJBNPA 13:18)',owner='autores',role='pesos das categorias do Walk Score (Street Smart) e versão de 3 componentes do Bike Score',cities='-',url='https://doi.org/10.1186/s12966-016-0339-0',
    license='artigos (citação)',license_url='',date='2015-2019',coverage='-',access='ok',notes='')
add(source='Portal de dados abertos de Moscou (data.mos.ru): conjuntos 60664 linhas, viagens, calendário, 60662 paradas, registro de linhas; 1903 alimentação; 3304 comércio; 526 bibliotecas; 495 cinemas; 531 teatros; 529 museus; escolas',
    owner='Governo da cidade de Moscou',role='Moscou: horários do transporte de superfície (ônibus, bonde, trólebus) e destinos adicionais para Walk/Bike',cities='Moscou',url='https://data.mos.ru/',
    license='CC BY 4.0',license_url='https://data.mos.ru/terms',date='instantâneos de 12 a 18/11/2026 (viagens atuais; histórico de 11/08/2026 não usado)',
    coverage='só cidade de Moscou; transporte só de superfície (sem metrô, MCD, MCC e trens)',access='portal bloqueado neste ambiente; arquivos baixados pelo usuário e lidos do Google Drive dele',
    notes='stop_times não usado (arquivo grande demais); paradas por linha pelo registro (nome + 60 m do traçado). Escolas só no teste de sensibilidade (complexos incluem prédios de educação infantil). Cantinas e bufês fora.')
add(source='Bus Open Data Service: feed agregado do Reino Unido (espelho Mobility Database gb-unknown-uk-aggregate-feed-gtfs-2014), recortado para Londres (08f_subset_gtfs.py -> gb-bods-london-subset)',
    owner='Department for Transport (Reino Unido)',role='Londres: horários de ônibus, metrô (Underground), DLR e Tramlink; Overground, Elizabeth line e trens nacionais não estão no feed e vêm do OSM',cities='Londres',
    url='https://www.bus-data.dft.gov.uk/',license='Open Government Licence v3.0',license_url='https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/',date='versão 20260603',coverage='Inglaterra, Escócia e País de Gales; ônibus e parte do trilho urbano',access='ok',notes='recorte pela caixa de Londres + 0,15 grau')
for h in ['gtfs-data.jp','api-public.odpt.org / odpt.org','data.mos.ru / apidata.mos.ru','transit.land','transitfeeds.com','transport.orgp.spb.ru','osakametro.co.jp','shmetro.com','bjsubway.com','szmc.net','tokyometro.jp','transport.mos.ru','GHSL/JRC','Geofabrik','Overpass API','WorldPop','HDX','Zenodo']:
    add(source=h,owner='',role='tentado (horários/frequências ou dados de base)',cities='',url=h,license='',license_url='',date='',coverage='',access='bloqueado pela política de rede deste ambiente (403); não contornado',notes='ODPT exigiria cadastro de desenvolvedor: não feito sem autorização' if 'odpt' in h else '')
# ---- GTFS feeds actually used
for f in sorted(glob.glob(f'{W}/transit/*_gtfs_audit.json')):
    city=os.path.basename(f).replace('_gtfs_audit.json','')
    if '__val' in city: continue
    A=json.load(open(f)); A=A if isinstance(A,list) else A.get('feeds',[])
    for a in A:
        if not a.get('feed'): continue
        fid=a.get('feed',''); mid=fid.rsplit('-',1)[-1]
        c=cat.loc[mid] if cat is not None and mid in cat.index else None
        g=lambda k: (str(c[k]) if c is not None and k in c and pd.notna(c[k]) else '')
        add(source=f'GTFS {fid}',owner=g('provider'),role='horários de transporte (Transit Score)',cities=city,url=g('urls.latest') or g('urls.direct_download'),
            license=('ver URL de licença do catálogo' if g('urls.license') else 'não declarada no catálogo Mobility Database (dados abertos do operador; verificar termos antes de redistribuir)'),
            license_url=g('urls.license'),date=f"validade {a.get('valid','')}; semana de referência {a.get('ref_week_monday','')}",
            coverage=f"oficial={g('is_official')}",access=a.get('status',''),notes=f"distância à semana de referência: {a.get('gap_days_to_ref','')} dias" + ('; frequencies.txt' if a.get('frequencies_rows') else ''))
# ---- published headways
H=pd.read_csv(f'{B}/data/published_headways/round1.csv'); H['source']=H.source.where(~H.source.isin(['same'])).ffill()
for (city,src),d in H.groupby(['city','source'],sort=False):
    if src=='same': continue
    add(source=f'Intervalo publicado: {src}',owner='operador / governo / imprensa / enciclopédia / guia (ver nota)',role='frequência de trilho sem GTFS',cities=city,url='',
        license='fato publicado (intervalo, horário); só os números foram usados',license_url='',date=str(d.source_date.iloc[0]),coverage=f"{len(d)} linhas",access='ok (leitor de página)',notes='grau '+','.join(sorted(d.grade.dropna().unique())))
R=pd.DataFrame(rows); R.to_csv(f'{B}/results/source_inventory.csv',index=False); print(len(R),'rows')
