# urbanmobility

Reconstrução aberta do Walk Score, do Transit Score e do Bike Score (0 a 100) para 21 cidades. O método segue a metodologia publicada desses índices, foi calibrado e validado contra notas oficiais nos EUA e é aplicado da mesma forma em todas as cidades, com intervalo de 95% em cada nota.

Cidades: Nova York, Chicago, Los Angeles, Paris, Londres, Berlim, Viena, Munique, Amsterdã, Lisboa, Madri, Barcelona, Milão, Roma, Moscou, São Petersburgo, Tóquio, Osaka, Xangai, Pequim e Shenzhen.

Este projeto não é afiliado ao Walk Score nem à Redfin. As notas aqui são estimativas próprias, calculadas com dados abertos. "Walk Score", "Transit Score" e "Bike Score" são marcas de seus donos.

## Resultados

- `results/city_scores.csv`: média ponderada por população, mediana, percentis e população por faixa de nota, por cidade e geografia, com o intervalo de 95%.
- `results/rankings.csv`: rankings por índice, com a faixa de posições compatível com os intervalos.
- `results/dense_core_scores.csv` e `results/dense_core_rankings.csv`: notas e rankings no núcleo denso (células contíguas ao pico de densidade com pelo menos 50% dele). As versões `_r1000` e `_r2000` são testes de sensibilidade do raio.
- `results/maps/` e `results/fig_*.png`: mapas por cidade e gráficos.
- `results/sensitivity.csv`, `results/validation_metrics*.csv` e demais tabelas: testes de sensibilidade e métricas de validação.
- `results/source_inventory.csv`: todas as fontes, com dono, licença, data e status de acesso.

Três geografias por cidade:
- **Centro urbano harmonizado:** regra DEGURBA (células contíguas com 1.500 hab./km² ou mais, somando 50 mil habitantes ou mais) aplicada à população Kontur. É a geografia comparável entre países. O polígono oficial GHS-FUA não foi usado.
- **Município:** limites das Overture Divisions. Tóquio são os 23 distritos, Londres é a Grande Londres (32 boroughs e a City of London) e Berlim é o Land de Berlim.
- **Núcleo denso:** descrito acima.

## Método

O relatório completo está em `relatorio/relatorio_metodologia_resultados.md`, com metodologia em `relatorio/01_metodologia.md` e resultados em `relatorio/02_resultados.md`. Em resumo:

- **Walk Score:** distância de rede a pé até nove categorias de destino, com decaimento calibrado e penalidades por densidade de interseções e tamanho de quarteirão.
- **Transit Score:** soma, sobre as linhas próximas, de viagens por semana × peso do modo × decaimento pela distância, em escala logarítmica calibrada (TS = −81,48 + 17,90·ln(soma)).
- **Bike Score:** versão de três componentes (infraestrutura cicloviária, relevo e destinos), porque fora dos EUA não há dado comparável de participação modal.
- **Grade:** células de 250 m; as notas de cidade são médias ponderadas por população.
- **Incerteza:** os intervalos de 95% vêm do erro de validação no nível de cidade em 10 cidades americanas (Walk ±4,5, Bike ±11, Transit com GTFS ±5,5, Transit só com OSM ±17,5; as cidades híbridas ficam no meio).

## Como rodar

Python 3.11 ou mais novo, com pandas, geopandas, pyarrow, numpy, scipy, shapely, pandana, osmium, rasterio, h3, scikit-learn e matplotlib.

Caminhos:
- `MS_BASE`: raiz do repositório (padrão `.`; rode os scripts da raiz, como `python code/05_grid.py paris`).
- `MS_WORK`: pasta de trabalho para bases baixadas e caches (padrão `work`).
- `CA_BUNDLE` (opcional): certificado de um proxy HTTPS, se houver.

Os scripts são numerados na ordem de execução, e cada um diz no início o que lê e o que grava:

1. `01` a `05`: centros urbanos, rede de ruas do OSM, Overture, municípios e grade.
2. `06` e `07`: destinos e distâncias a pé.
3. `08` a `09`: transporte. `08` lê GTFS do Mobility Database (feeds em `code/gtfs_feeds.json`); `08b` usa as linhas do OSM; `08c` calcula as medianas de imputação; `08d` monta as cidades híbridas; `08e` aplica os intervalos publicados (`data/published_headways/round1.csv`); `08f` recorta um GTFS nacional pela caixa da cidade; `09` calcula as distâncias até as linhas.
4. `10` e `11`: componentes do Bike Score e notas por célula.
5. `12` a `16`: calibração e validação (ver a nota abaixo).
6. `17` a `24`: resultados por cidade, variantes, sensibilidade, inventário de fontes, figuras e pacote de células.
7. `25` a `28`: dados abertos de Moscou (data.mos.ru).
8. `29` a `31`: tabelas do relatório e núcleo denso.

## O que ficou fora do repositório e como refazer

- **Pacote de células** (`results/cells_all.gpkg`, cerca de 217 MB; `results/cells_all.csv.gz`; `results/cells/*.parquet`; `results/dense_core_cells*.parquet`): acima do limite do GitHub ou grandes demais para versionar. Refaça com `17_city_results.py`, `23_package.py` e `30_dense_core.py`.
- **Bases brutas** (OSM, Overture, Kontur, Copernicus DEM, feeds GTFS) e caches em `work/`: baixadas pelos scripts `01` a `10`.
- **Dados abertos de Moscou** (`data/moscow_datamos/`, cerca de 183 MB): baixe os conjuntos listados em `results/source_inventory.csv` em https://data.mos.ru/ e coloque-os em `data/moscow_datamos/` antes de rodar `25` a `28`.
- **Notas oficiais do Walk Score usadas na validação** (por endereço e por cidade, coletadas à mão em walkscore.com): não são redistribuídas aqui, porque o conteúdo do walkscore.com pertence à Redfin. O repositório traz só as métricas agregadas (`results/validation_metrics*.csv`). Para refazer a calibração (`12` a `15`) e os intervalos (`17`), é preciso coletar essas notas de novo, à mão, respeitando os termos do site, no formato descrito em `code/13_validation_sample.py`. Os termos da Redfin proíbem consulta automatizada.

## Cautelas

- **Walk Score de Xangai, Pequim e Shenzhen é um limite inferior.** Há 2,3 a 4,5 destinos mapeados por mil habitantes nessas cidades, contra 11 a 43 nas demais.
- **Transit Score sem horários oficiais completos é estimativa.** Em Osaka, Xangai, Pequim e Shenzhen a margem é de cerca de ±17,5, com tendência a subestimar (forte em Osaka e Tóquio). Em Moscou e São Petersburgo, o trilho vem do OSM com intervalos publicados (margem de cerca de ±13); em Londres, Overground, Elizabeth line e National Rail vêm do OSM (cerca de ±8).
- **Feeds desatualizados:** ônibus de Barcelona (2020) e São Petersburgo (2021).
- **Município não é comparável entre países;** para comparar, use o centro urbano.
- **Validação só nos EUA,** único lugar com notas oficiais.

## Fontes e atribuição

- **OpenStreetMap:** © colaboradores do OpenStreetMap, dados sob a Open Database License (ODbL 1.0), https://www.openstreetmap.org/copyright. Planet de 09/11/2026.
- **Overture Maps Foundation:** release 2026-10-21.0. Places sob CDLA Permissive 2.0; Divisions e Land Use incluem dados do OpenStreetMap sob ODbL. https://overturemaps.org/
- **Kontur Population** (2023-11-01): CC BY 4.0, © Kontur, https://data.humdata.org/organization/kontur
- **Copernicus DEM GLO-30:** produzido com Copernicus WorldDEM-30 © DLR e.V. 2010-2014 e © Airbus Defence and Space GmbH 2014-2018, fornecido no âmbito do COPERNICUS pela União Europeia e pela ESA.
- **GTFS:** 87 feeds via Mobility Database (catálogo CC0); cada feed tem a licença do seu operador, listada em `results/source_inventory.csv`. Os feeds não são redistribuídos aqui, só resultados derivados.
- **Bus Open Data Service (Reino Unido):** Department for Transport, Open Government Licence v3.0.
- **VBB (Berlim-Brandemburgo):** GTFS via Mobility Database.
- **Portal de dados abertos do Governo de Moscou** (https://data.mos.ru/): CC BY 4.0, instantâneos de 12 a 18/11/2026.
- **Intervalos publicados por linha:** só os números, com a fonte de cada um em `data/published_headways/round1.csv`.

## Licença

O código está sob a licença MIT (ver `LICENSE`). Os dados derivados do OpenStreetMap ou das camadas Overture baseadas nele (limites em `data/study_areas/`, notas por célula, mapas e tabelas) continuam sob a ODbL 1.0 e exigem a atribuição acima. Os dados do data.mos.ru e da Kontur exigem atribuição (CC BY 4.0).
