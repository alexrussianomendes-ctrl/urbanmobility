# Walk Score, Transit Score e Bike Score reconstruídos para 21 cidades: metodologia

Data: 18/11/2026 (Moscou atualizada em 19/11/2026 com dados do data.mos.ru; Londres e Berlim incluídas em 19/11/2026). Código em `code/` (scripts numerados 01 a 31, na ordem de execução). Resultados em `results/`.

## 1. O que é documentado, o que foi inferido e o que é desconhecido

### Walk Score
- **Documentado (walkscore.com/methodology.shtml):** pontuação por distância a pé até categorias de destinos; pontos máximos até 0,25 milha (402 m, cerca de 5 minutos); decaimento com a distância; zero após 30 minutos (1,5 milha, 2.414 m); distâncias pela rede de ruas; penalidades por baixa densidade de interseções e quarteirões longos; notas de cidade e bairro como média ponderada por população de uma grade fina.
- **Documentado na literatura, não na página oficial:** as nove categorias e seus pesos (versão Street Smart): mercado 3; restaurantes e bares 10 itens (0,75 a 0,2); compras 5 itens; café 2 itens; banco, parque, escola, livraria e entretenimento 1 cada; total 15 (Kim et al. 2019; Statistics Canada 2015). Também as tabelas de penalidade por interseções/milha² e por comprimento médio de quarteirão.
- **Inferido (calibrado):** a forma da curva de decaimento entre 402 m e 2.414 m. Ajustada como exp(−α·((d−402,3)/1000)^β), com α = 1,023 e β = 0,655.
- **Desconhecido:** a base de destinos que o Walk Score usa hoje (provedor e filtros), o raio exato das penalidades e a grade exata (a página fala em cerca de 150 m nos EUA). Aqui usamos 250 m.

### Transit Score
- **Documentado (página oficial e patente US 9677892):** soma, sobre as linhas, de viagens por semana × peso do modo × decaimento pela distância até a parada mais próxima da linha. Pesos: trilho 2; balsa, teleférico e outros 1,5; ônibus 1. O decaimento é o mesmo do Walk Score. Normalização logarítmica, com 100 igual à média do centro de cinco cidades americanas.
- **Inferido (calibrado):** a constante e a escala do logaritmo. TS = a + b·ln(soma), com a = −81,48 e b = 17,90.
- **Desconhecido:** como linhas com várias variantes ou direções são consolidadas. Aqui: mesma linha, com 80% ou mais de paradas em comum, vira uma só, e conta a direção mais movimentada. Também é desconhecida a janela de tempo. Aqui: uma semana de referência comum a todas as cidades, com o feed deslocado para ela quando necessário e a distância em dias registrada.

### Bike Score
- **Documentado (página oficial):** componentes de infraestrutura (ciclovia vale 2× ciclofaixa e 3× via compartilhada; decaimento até zero em 1.000 m), relevo (maior declividade nas redondezas; 2% vale 100 e 10% vale 0), destinos/conectividade (Walk Score modificado) e participação modal da bicicleta (censo americano).
- **Divergência documentada:** a página fala em quatro componentes iguais. Winters et al. (2016) descrevem a versão de três componentes (faixas 50%, relevo 25%, destinos 25%), usada no Canadá. Fora dos EUA não há dado comparável de participação modal, então usamos a versão de três componentes nas 21 cidades. Isso foi testado na validação.
- **Inferido (calibrado):** o ponto de saturação do componente de faixas (lane_ref = 2.198 m ponderados).
- **Desconhecido:** a normalização exata das faixas ("média dos maiores valores amostrados") e a fonte de relevo fora dos EUA.

## 2. Geografia

- **Duas geografias por cidade, com a mesma grade:**
  - (a) **centro urbano harmonizado:** a regra DEGURBA (células contíguas com 1.500 hab./km² ou mais, somando 50 mil habitantes ou mais, com suavização e preenchimento de buracos) aplicada aos hexágonos H3 de cerca de 0,74 km² da população Kontur, em vez de quadrados de 1 km². O GHS-FUA pronto não pôde ser baixado deste ambiente.
  - (b) **município:** limites das Overture Divisions. Tóquio é a união dos 23 distritos; Moscou é a cidade federal, incluindo a Nova Moscou; Londres é a Grande Londres (32 boroughs mais a City of London, 1.595 km²); Berlim é o Land de Berlim (891 km²); Xangai, Pequim e Shenzhen são o município inteiro, com áreas rurais.
  - (c) **núcleo denso** (versão pedida depois): células contíguas ao pico de densidade com pelo menos 50% dela, sobre a densidade suavizada num raio de 1,5 km (seção 8a).
- **Grade:** células de 250 m na projeção local. Cada célula recebe uma parte igual da população de cada hexágono Kontur (H3 r8) que toca. As notas de cidade são médias ponderadas por população, a convenção do Walk Score.
- **Efeito de borda:** destinos e linhas de transporte fora do limite contam, porque as distâncias foram calculadas numa área de estudo maior que as duas geografias.

## 3. Componentes e fontes

- **Rede de caminhada:** OpenStreetMap (planet de 09/11/2026), com vias caminháveis e distâncias de rede (pandana).
- **Destinos:** OSM mesclado com Overture Places (confiança de 0,5 ou mais), sem estabelecimentos marcados como fechados. Um ponto Overture a menos de 25 m de um ponto OSM da mesma categoria é tratado como duplicata. Parques entram por pontos de acesso a cada 100 m no perímetro do polígono.
- **Moscou, destinos extras:** estabelecimentos do portal de dados abertos da prefeitura (data.mos.ru, CC BY 4.0): alimentação, comércio, bibliotecas, cinemas, teatros e museus, com a mesma regra de duplicata de 25 m. Cantinas e bufês ficam de fora; escolas só no teste de sensibilidade.
- **Ciclovias:** classes OSM. Ciclovia segregada = path; ciclofaixa = lane; compartilhada/sharrow e ruas de bicicleta = shared.
- **Relevo:** Copernicus DEM GLO-30, que é um modelo de superfície. Aplicamos abertura morfológica 7×7 para tirar prédios e árvores. A declividade é calculada nas pontas de cada trecho de rua ou ciclovia de 100 m ou mais, sem pontes e túneis, e conta a maior declividade entre os trechos cujo meio está a até 200 m da célula. O comprimento de ciclovias é medido em anéis de 100 m até 1.000 m.
- **Transporte:** GTFS do Mobility Database onde existe: 87 feeds, contando as cidades de validação. Em Londres, o feed nacional do Reino Unido (BODS, Open Government Licence) foi recortado pela caixa da cidade (`code/08f_subset_gtfs.py`). Onde não existe ou falta parte da rede, usamos as linhas do OSM (relações route=*) com frequência:
  - (i) do próprio OSM (tag interval), quando há;
  - (ii) dos intervalos publicados por linha, para metrô e trem, vindos de operador, governo, imprensa, enciclopédia ou guia, cada um com grau de qualidade;
  - (iii) senão, a mediana de viagens por semana do mesmo modo nas cidades com GTFS (rotulada como "imputada").
- **Moscou, transporte de superfície:** linhas, viagens e calendários oficiais do data.mos.ru (CC BY 4.0), contados na semana de referência como um GTFS. As paradas de cada linha vêm do registro de linhas, por nome e a até 60 m do traçado, porque o arquivo de horários por parada não pôde ser baixado.
- **População:** Kontur Population 2023-11-01.

O inventário completo, com URL, dono, licença, datas, cobertura e status de acesso, está em `results/source_inventory.csv`.

## 4. Variante de Transit Score por cidade

| Variante | Cidades | O que é |
|---|---|---|
| GTFS | Nova York, Chicago, Los Angeles, Paris, Viena, Lisboa, Amsterdã, Madri, Barcelona, Milão, Roma, Berlim (VBB) | horários oficiais completos |
| Híbrida (GTFS + OSM) | Munique (S-Bahn sem viagens no feed), Tóquio (GTFS só da Toei), São Petersburgo (GTFS de 2021 sem metrô), Moscou (horários oficiais só do transporte de superfície), Londres (BODS, recortado do feed nacional, sem Overground, Elizabeth line e trens da National Rail) | GTFS onde há; linhas OSM que faltam, com intervalos publicados ou mediana |
| OSM + intervalos publicados | Osaka, Xangai, Pequim, Shenzhen | sem GTFS utilizável; trilho com intervalos publicados, ônibus com mediana imputada |

**Fórmula dos intervalos publicados:** viagens/semana = [5·(4 h de pico a 60/intervalo de pico + (horas de operação − 4) a 60/intervalo fora do pico) + 2·horas de operação·60/intervalo de fim de semana] / 1,096.
- O divisor 1,096 vem do teste da fórmula em 61 linhas de metrô de 9 cidades com GTFS: a fórmula superestima em 9,6% na mediana, com erro absoluto médio de 15% e efeito de cerca de ±2,5 pontos de Transit Score.
- Quando falta o pico ou o fora do pico, usamos a razão mediana entre os dois (da própria cidade, se houver 3 linhas ou mais com ambos; senão, a de todas as linhas de grau A/B).

## 5. Validação (cada índice separado, cidades inteiras fora da calibração)

- **Calibração:**
  - pontos de Boston, São Francisco e Seattle;
  - nota de cidade dessas três e de Washington, Portland, Filadélfia e Minneapolis.
- **Teste:** Chicago, Nova York e Los Angeles, que nunca entraram no ajuste.
- **Pontos:** 120 endereços com nota oficial coletada manualmente pelo usuário, de 150 sorteados em 5 anéis de população. 20 foram excluídos por serem endereços genéricos e 10 por não poderem ser localizados com segurança.
- **Notas de cidade:** da tabela de 129 cidades enviada pelo usuário, entraram as 10 com insumos processados.

| Índice | Nível | Conjunto | n | MAE | RMSE | Viés | Spearman | % a ±10 |
|---|---|---|---|---|---|---|---|---|
| Walk | cidade | teste | 3 | 1,7 | 2,0 | −1,7 | 1,00 | 100 |
| Walk | ponto | teste | 60 | 6,1 | 7,7 | −0,9 | 0,87 | 82 |
| Transit (GTFS) | cidade | teste | 3 | 3,9 | 4,4 | 0,0 | 1,00 | 100 |
| Transit (GTFS) | ponto | teste | 60 | 5,1 | 6,3 | +1,5 | 0,97 | 87 |
| Bike | cidade | teste | 3 | 4,4 | 5,0 | +0,6 | 0,50 | 100 |
| Bike | ponto | teste | 60 | 10,3 | 12,8 | +1,0 | 0,72 | 50 |
| Transit (só OSM, mediana imputada) | cidade | teste | 3 | 7,6 | 7,8 | −7,6 | 1,00 | 100 |
| Transit (só OSM, mediana imputada) | ponto | teste | 60 | 7,7 | 12,1 | −6,0 | n/d | n/d |

- **Erro por faixa de nota:** está em `results/validation_metrics.csv`. O Walk Score erra mais nas faixas 25–49 e 50–69. O Transit Score subestima um pouco a faixa 90–100 (viés −7 no teste). O Bike Score acerta a média da cidade, mas por ponto erra em média 10 pontos: a participação modal, que não existe fora dos EUA, pesa na nota oficial americana.
- **Leitura:** o Walk Score e o Transit Score com GTFS reproduzem bem a nota oficial no nível de cidade (erro de 2 a 4 pontos). O Bike Score é uma aproximação mais grosseira. O Transit Score sem horários (só OSM) tem erro de 8 a 12 pontos e tende a subestimar.

## 6. Incerteza: como foi calculada

Os intervalos de 95% das notas de cidade são 1,96 × o RMSE de validação no nível de cidade, juntando as 10 cidades americanas:
- **Walk:** ±4,5.
- **Bike:** ±11,0.
- **Transit com GTFS:** ±5,5.
- **Transit só com OSM** (Osaka, Xangai, Pequim, Shenzhen): combina dois erros, o do modelo GTFS e a diferença "proxy menos GTFS". Essa diferença foi medida em todas as cidades que têm os dois: as 10 de validação e as 9 cidades europeias do estudo com GTFS completo, com RMSE de 8,5 pontos e viés de −4,0. O resultado é ±17,5 (era ±17,9 antes de Berlim entrar nessa conta).
- **Híbridas:** mistura os dois intervalos pela fração da soma de transporte que vem do OSM. Em Moscou, as linhas do OSM cujas viagens vêm do data.mos.ru contam como horário oficial.

Os intervalos de ranking (`rank_best` e `rank_worst` em `results/rankings.csv`) contam quantas cidades estão certamente acima e certamente abaixo, com intervalos que não se sobrepõem.
