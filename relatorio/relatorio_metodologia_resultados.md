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

# Resultados, sensibilidade e limites

## 7. Notas por cidade

Média ponderada por população com intervalo de 95% (validação). Tabelas completas, com mediana, percentis 10/25/75/90 e a parcela da população em cada faixa, estão em `results/city_scores.csv`. Mapas por cidade estão em `results/maps/`. Gráficos: `results/fig_means_*.png` (médias e intervalos) e `results/fig_bands_*.png` (população por faixa).

**Cautelas que valem para toda a tabela:**
- **Walk Score em Xangai, Pequim e Shenzhen é um limite inferior.** Os destinos mapeados são poucos: 2,3 a 4,5 por mil habitantes nas três cidades chinesas, contra 11 a 43 nas demais (`results/poi_density.csv`). A nota baixa reflete o mapa, não a cidade.
- **Transit Score sem horários oficiais tem intervalo de cerca de ±18 e tende a subestimar.** Isso vale para Osaka e as três cidades chinesas, e para a parte OSM de Tóquio, São Petersburgo e Moscou (em Moscou, o trilho; o transporte de superfície já usa horários oficiais, e o intervalo cai para ±13). Em Londres, só os trens (Overground, Elizabeth line e National Rail) vêm do OSM, e o intervalo é de cerca de ±8. Em Osaka e Tóquio a subestimação é provável e grande: veja a seção 9.
- **Município não é comparável entre países.** Os municípios chineses incluem áreas rurais extensas, Lisboa e Paris são só o núcleo, Moscou inclui a Nova Moscou, Londres é a Grande Londres (32 boroughs mais a City) e Berlim é o Land de Berlim. Para comparar cidades, a geografia indicada é o centro urbano harmonizado.

### Centro urbano harmonizado (geografia comparável)

| Cidade | População (mi) | Walk | Transit | Bike | Variante Transit |
|---|---|---|---|---|---|
| Milão | 2,6 | 84 ± 5 | 69 ± 6 | 83 ± 11 | GTFS |
| Roma | 2,3 | 84 ± 5 | 71 ± 6 | 58 ± 11 | GTFS |
| Paris | 9,5 | 82 ± 5 | 84 ± 6 | 80 ± 11 | GTFS |
| Lisboa | 1,7 | 82 ± 5 | 69 ± 6 | 52 ± 11 | GTFS |
| Barcelona | 3,7 | 81 ± 5 | 70 ± 6 | 72 ± 11 | GTFS |
| Londres | 10,0 | 81 ± 5 | 81 ± 8 | 72 ± 11 | híbrida |
| Nova York | 12,8 | 79 ± 5 | 66 ± 6 | 64 ± 11 | GTFS |
| Madri | 4,9 | 77 ± 5 | 78 ± 6 | 65 ± 11 | GTFS |
| Tóquio | 32,8 | 76 ± 5 | 64 ± 17 | 51 ± 11 | híbrida |
| São Petersburgo | 4,8 | 75 ± 5 | 88 ± 13 | 52 ± 11 | híbrida |
| Moscou | 12,9 | 75 ± 5 | 86 ± 13 | 52 ± 11 | híbrida |
| Munique | 1,8 | 74 ± 5 | 70 ± 7 | 90 ± 11 | híbrida |
| Viena | 1,9 | 74 ± 5 | 79 ± 6 | 79 ± 11 | GTFS |
| Osaka | 15,2 | 74 ± 5 | 51 ± 17 | 50 ± 11 | OSM + intervalos |
| Chicago | 3,9 | 72 ± 5 | 60 ± 6 | 63 ± 11 | GTFS |
| Amsterdã | 1,1 | 71 ± 5 | 61 ± 6 | 90 ± 11 | GTFS |
| Berlim | 3,8 | 70 ± 5 | 74 ± 6 | 84 ± 11 | GTFS |
| Los Angeles | 10,4 | 64 ± 5 | 44 ± 6 | 56 ± 11 | GTFS |
| Pequim | 16,5 | 47 ± 5 | 74 ± 17 | 62 ± 11 | OSM + intervalos |
| Shenzhen | 11,3 | 46 ± 5 | 58 ± 17 | 42 ± 11 | OSM + intervalos |
| Xangai | 26,7 | 43 ± 5 | 74 ± 17 | 59 ± 11 | OSM + intervalos |

### Município

| Cidade | População (mi) | Walk | Transit | Bike | Variante Transit |
|---|---|---|---|---|---|
| Paris | 2,3 | 97 ± 5 | 99 ± 6 | 93 ± 11 | GTFS |
| Milão | 1,1 | 90 ± 5 | 92 ± 6 | 85 ± 11 | GTFS |
| Tóquio (23 distritos) | 9,3 | 89 ± 5 | 83 ± 16 | 64 ± 11 | híbrida |
| Lisboa | 0,5 | 88 ± 5 | 86 ± 6 | 71 ± 11 | GTFS |
| Barcelona | 1,6 | 88 ± 5 | 91 ± 6 | 79 ± 11 | GTFS |
| Osaka | 2,5 | 86 ± 5 | 67 ± 17 | 64 ± 11 | OSM + intervalos |
| Nova York | 8,2 | 86 ± 5 | 83 ± 6 | 76 ± 11 | GTFS |
| Londres | 9,2 | 82 ± 5 | 84 ± 8 | 73 ± 11 | híbrida |
| Roma | 2,5 | 80 ± 5 | 68 ± 6 | 57 ± 11 | GTFS |
| Madri | 3,3 | 79 ± 5 | 83 ± 6 | 65 ± 11 | GTFS |
| Chicago | 2,7 | 77 ± 5 | 70 ± 6 | 70 ± 11 | GTFS |
| Munique | 1,6 | 75 ± 5 | 73 ± 7 | 91 ± 11 | híbrida |
| Moscou | 12,2 | 74 ± 5 | 86 ± 12 | 52 ± 11 | híbrida |
| Viena | 1,9 | 73 ± 5 | 79 ± 6 | 79 ± 11 | GTFS |
| Amsterdã | 0,8 | 72 ± 5 | 66 ± 6 | 90 ± 11 | GTFS |
| São Petersburgo | 5,3 | 71 ± 5 | 84 ± 13 | 50 ± 11 | híbrida |
| Berlim | 3,8 | 70 ± 5 | 74 ± 6 | 83 ± 11 | GTFS |
| Los Angeles | 3,8 | 67 ± 5 | 54 ± 6 | 55 ± 11 | GTFS |
| Shenzhen | 12,0 | 45 ± 5 | 57 ± 17 | 42 ± 11 | OSM + intervalos |
| Xangai | 30,6 | 39 ± 5 | 70 ± 17 | 55 ± 11 | OSM + intervalos |
| Pequim | 23,0 | 36 ± 5 | 59 ± 17 | 53 ± 11 | OSM + intervalos |

## 8. Rankings separados

Cada índice tem seu próprio ranking, com a faixa de posições possíveis entre parênteses. A faixa vai da melhor à pior posição compatível com os intervalos de 95%. Detalhe em `results/rankings.csv`.

**Centro urbano harmonizado**
- **Walk:**
  1. Milão (1–9)
  2. Roma (1–10)
  3. Paris (1–14)
  4. Lisboa (1–14)
  5. Barcelona (1–14)
  6. Londres (1–15)
  7. Nova York (1–17)
  8. Madri (1–17)
  9. Tóquio (1–17)
  10. São Petersburgo (2–17)
  11. Moscou (3–17)
  12. Munique (3–17)
  13. Viena (3–17)
  14. Osaka (3–17)
  15. Chicago (6–18)
  16. Amsterdã (7–18)
  17. Berlim (7–18)
  18. Los Angeles (15–18)
  19. Pequim (19–21)*
  20. Shenzhen (19–21)*
  21. Xangai (19–21)*

  \* limite inferior.
- **Transit:**
  1. São Petersburgo (1–13)
  2. Moscou (1–16)
  3. Paris (1–10)
  4. Londres (1–16)
  5. Viena (1–16)
  6. Madri (1–16)
  7. Xangai (1–20)
  8. Berlim (1–17)
  9. Pequim (1–20)
  10. Roma (2–20)
  11. Munique (2–20)
  12. Barcelona (3–20)
  13. Lisboa (3–20)
  14. Milão (3–20)
  15. Nova York (7–20)
  16. Tóquio (1–21)
  17. Amsterdã (8–20)
  18. Chicago (8–20)
  19. Shenzhen (2–21)
  20. Osaka (8–21)
  21. Los Angeles (18–21)
- **Bike:**
  1. Amsterdã (1–8)
  2. Munique (1–8)
  3. Berlim (1–12)
  4. Milão (1–12)
  5. Paris (1–14)
  6. Viena (1–14)
  7. Barcelona (1–20)
  8. Londres (1–20)
  9. Madri (3–20)
  10. Nova York (3–21)
  11. Chicago (3–21)
  12. Pequim (3–21)
  13. Xangai (5–21)
  14. Roma (5–21)
  15. Los Angeles (7–21)
  16. Lisboa (7–21)
  17. São Petersburgo (7–21)
  18. Moscou (7–21)
  19. Tóquio (7–21)
  20. Osaka (7–21)
  21. Shenzhen (10–21)

**Município**
- **Walk:**
  1. Paris (1–5)
  2. Milão (1–8)
  3. Tóquio (1–9)
  4. Lisboa (1–10)
  5. Barcelona (1–10)
  6. Osaka (2–11)
  7. Nova York (2–11)
  8. Londres (2–14)
  9. Roma (3–16)
  10. Madri (4–16)
  11. Chicago (6–17)
  12. Munique (8–18)
  13. Moscou (8–18)
  14. Viena (8–18)
  15. Amsterdã (9–18)
  16. São Petersburgo (9–18)
  17. Berlim (11–18)
  18. Los Angeles (12–18)
  19. Shenzhen (19–20)*
  20. Xangai (19–21)*
  21. Pequim (20–21)*

  \* limite inferior.
- **Transit:**
  1. Paris (1–6)
  2. Milão (1–11)
  3. Barcelona (1–11)
  4. Moscou (1–19)
  5. Lisboa (2–14)
  6. São Petersburgo (1–20)
  7. Londres (2–16)
  8. Tóquio (1–20)
  9. Nova York (2–15)
  10. Madri (2–15)
  11. Viena (4–19)
  12. Berlim (5–20)
  13. Munique (4–20)
  14. Chicago (8–20)
  15. Xangai (2–21)
  16. Roma (8–20)
  17. Osaka (4–21)
  18. Amsterdã (10–20)
  19. Pequim (7–21)
  20. Shenzhen (8–21)
  21. Los Angeles (17–21)
- **Bike:**
  1. Paris (1–10)
  2. Munique (1–11)
  3. Amsterdã (1–11)
  4. Milão (1–14)
  5. Berlim (1–14)
  6. Barcelona (1–14)
  7. Viena (1–14)
  8. Nova York (1–17)
  9. Londres (1–19)
  10. Lisboa (1–20)
  11. Chicago (2–20)
  12. Madri (4–20)
  13. Tóquio (4–21)
  14. Osaka (4–21)
  15. Roma (8–21)
  16. Xangai (8–21)
  17. Los Angeles (8–21)
  18. Pequim (9–21)
  19. Moscou (9–21)
  20. São Petersburgo (10–21)
  21. Shenzhen (13–21)

**Leitura:**
- **Walk:** o ranking é firme nas pontas. Há um grupo europeu no alto, Los Angeles abaixo dele, e as cidades chinesas no fim por falta de dados. O meio é um empate largo.
- **Transit:** a ordem só é confiável entre as cidades com GTFS. Paris lidera; Los Angeles fica por último.
- **Bike:** só Amsterdã, Munique e Paris, no alto, e Shenzhen, embaixo, se separam do resto.

## 8a. Duas versões novas: município como ranking principal e núcleo denso

Pedidas depois da primeira entrega. As notas por célula são as mesmas; muda só a área sobre a qual a média é feita.

### Município como ranking principal

É o recorte do Walk Score oficial, que dá a nota da cidade dentro do limite municipal. Por isso Nova York fica em 78,7 no centro urbano harmonizado (que inclui subúrbios de Nova Jersey, Long Island e Westchester) e em 85,5 no município, a 2,5 pontos do oficial (88), dentro da margem de ±4,5. Londres entra como a Grande Londres (os 32 boroughs mais a City of London, 1.595 km²) e Berlim como o Land de Berlim (891 km²).

| Cidade | Walk (posição) | Transit (posição) | Bike (posição) |
|---|---|---|---|
| Paris | 97 ± 5 (1º, 1–5) | 99 ± 6 (1º, 1–6) | 93 ± 11 (1º, 1–10) |
| Milão | 90 ± 5 (2º, 1–8) | 92 ± 6 (2º, 1–11) | 85 ± 11 (4º, 1–14) |
| Tóquio (23 distritos) | 89 ± 5 (3º, 1–9) | 83 ± 16 (8º, 1–20) | 64 ± 11 (13º, 4–21) |
| Lisboa | 88 ± 5 (4º, 1–10) | 86 ± 6 (5º, 2–14) | 71 ± 11 (10º, 1–20) |
| Barcelona | 88 ± 5 (5º, 1–10) | 91 ± 6 (3º, 1–11) | 79 ± 11 (6º, 1–14) |
| Osaka | 86 ± 5 (6º, 2–11) | 67 ± 17 (17º, 4–21) | 64 ± 11 (14º, 4–21) |
| Nova York | 86 ± 5 (7º, 2–11) | 83 ± 6 (9º, 2–15) | 76 ± 11 (8º, 1–17) |
| Londres (Grande Londres) | 82 ± 5 (8º, 2–14) | 84 ± 8 (7º, 2–16) | 73 ± 11 (9º, 1–19) |
| Roma | 80 ± 5 (9º, 3–16) | 68 ± 6 (16º, 8–20) | 57 ± 11 (15º, 8–21) |
| Madri | 79 ± 5 (10º, 4–16) | 83 ± 6 (10º, 2–15) | 65 ± 11 (12º, 4–20) |
| Chicago | 77 ± 5 (11º, 6–17) | 70 ± 6 (14º, 8–20) | 70 ± 11 (11º, 2–20) |
| Munique | 75 ± 5 (12º, 8–18) | 73 ± 7 (13º, 4–20) | 91 ± 11 (2º, 1–11) |
| Moscou | 74 ± 5 (13º, 8–18) | 86 ± 12 (4º, 1–19) | 52 ± 11 (19º, 9–21) |
| Viena | 73 ± 5 (14º, 8–18) | 79 ± 6 (11º, 4–19) | 79 ± 11 (7º, 1–14) |
| Amsterdã | 72 ± 5 (15º, 9–18) | 66 ± 6 (18º, 10–20) | 90 ± 11 (3º, 1–11) |
| São Petersburgo | 71 ± 5 (16º, 9–18) | 84 ± 13 (6º, 1–20) | 50 ± 11 (20º, 10–21) |
| Berlim | 70 ± 5 (17º, 11–18) | 74 ± 6 (12º, 5–20) | 83 ± 11 (5º, 1–14) |
| Los Angeles | 67 ± 5 (18º, 12–18) | 54 ± 6 (21º, 17–21) | 55 ± 11 (17º, 8–21) |
| Shenzhen | 45 ± 5 (19º, 19–20) | 57 ± 17 (20º, 8–21) | 42 ± 11 (21º, 13–21) |
| Xangai | 39 ± 5 (20º, 19–21) | 70 ± 17 (15º, 2–21) | 55 ± 11 (16º, 8–21) |
| Pequim | 36 ± 5 (21º, 20–21) | 59 ± 17 (19º, 7–21) | 53 ± 11 (18º, 9–21) |

A posição vem com a faixa de posições compatível com os intervalos de 95%. A cautela da seção 7 continua: os municípios têm tamanhos muito diferentes (Paris e Lisboa são só o núcleo; Xangai, Pequim e Shenzhen incluem áreas rurais), e isso pesa na nota.

### Núcleo denso (50% da densidade do lugar mais denso)

**Como foi recortado:**
- **Densidade suavizada:** a densidade de cada célula de 250 m é a média das células num raio de 1,5 km (janela de cerca de 3 km), para que um conjunto isolado de prédios não defina o pico.
- **Pico e limiar:** o pico é a célula de maior densidade suavizada na área de estudo; o núcleo são as células com pelo menos 50% dessa densidade.
- **Contiguidade:** só entram as células ligadas ao pico por outras células acima do limiar. Bolsões densos separados ficam de fora.
- **Por que não 1 km:** com janela de 1 km, o pico caiu sobre um único hexágono de população em Shenzhen, Xangai, Lisboa, Chicago, Roma e Moscou, e o núcleo encolheu para 1 a 6 km² em volta de um bloco de torres. Com raio de 1,5 km ou mais, todo núcleo tem pelo menos 20 km². Os raios de 1 e 2 km ficaram como teste.

**O pico é de moradia, não de centro histórico.** Em Lisboa ele fica no limite com a Amadora (só 15% do núcleo está dentro do município), em Moscou num bairro de prédios altos do sul, em São Petersburgo no distrito de Primorsky, em Nova York no Upper East Side, em Londres no leste, perto de Stratford, e em Berlim em Charlottenburg-Wilmersdorf. Em Paris, Madri, Milão e Barcelona o núcleo coincide com o centro.

| Cidade | Área (km²) | População (mi) | Walk | Transit | Bike |
|---|---|---|---|---|---|
| Paris | 90 | 2,4 | 98 ± 5 | 99 ± 6 | 92 ± 11 |
| Milão | 64 | 0,7 | 97 ± 5 | 98 ± 6 | 87 ± 11 |
| Barcelona | 92 | 1,8 | 93 ± 5 | 93 ± 6 | 84 ± 11 |
| Roma | 34 | 0,4 | 93 ± 5 | 83 ± 6 | 75 ± 11 |
| Londres | 243 | 3,3 | 92 ± 5 | 95 ± 8 | 84 ± 11 |
| Nova York | 90 | 2,2 | 92 ± 5 | 93 ± 6 | 89 ± 11 |
| Madri | 143 | 2,0 | 92 ± 5 | 92 ± 6 | 71 ± 11 |
| Tóquio | 634 | 9,9 | 91 ± 5 | 82 ± 16 | 64 ± 11 |
| Osaka | 472 | 5,0 | 86 ± 5 | 61 ± 17 | 61 ± 11 |
| Lisboa | 48 | 0,4 | 86 ± 5 | 69 ± 6 | 54 ± 11 |
| Los Angeles | 33 | 0,4 | 86 ± 5 | 77 ± 6 | 55 ± 11 |
| Chicago | 123 | 1,0 | 86 ± 5 | 75 ± 6 | 82 ± 11 |
| Viena | 134 | 1,0 | 83 ± 5 | 87 ± 6 | 82 ± 11 |
| Moscou | 25 | 0,7 | 82 ± 5 | 92 ± 14 | 71 ± 11 |
| Amsterdã | 81 | 0,6 | 80 ± 5 | 73 ± 6 | 94 ± 11 |
| Munique | 198 | 1,3 | 79 ± 5 | 77 ± 7 | 94 ± 11 |
| São Petersburgo | 20 | 0,4 | 79 ± 5 | 96 ± 10 | 50 ± 11 |
| Berlim | 370 | 2,5 | 73 ± 5 | 77 ± 6 | 86 ± 11 |
| Pequim | 212 | 5,9 | 65 ± 5 | 88 ± 17 | 67 ± 11 |
| Xangai | 313 | 11,5 | 62 ± 5 | 89 ± 17 | 76 ± 11 |
| Shenzhen | 77 | 2,6 | 61 ± 5 | 77 ± 17 | 41 ± 11 |

O tamanho do núcleo varia muito: de 20 km² (São Petersburgo) a 634 km² (Tóquio), e de 0,35 a 11,5 milhões de habitantes. Cidades com densidade alta e uniforme (Tóquio, Osaka, Xangai) têm núcleos enormes; cidades com um pico forte e queda rápida (São Petersburgo, Moscou, Los Angeles, Roma) têm núcleos pequenos.

**Rankings do núcleo denso** (faixa de posições entre parênteses; detalhe em `results/dense_core_rankings.csv`):
- **Walk:** 1. Paris (1–8); 2. Milão (1–8); 3. Barcelona (1–12); 4. Roma (1–12); 5. Londres (1–13); 6. Nova York (1–13); 7. Madri (1–13); 8. Tóquio (1–14); 9. Osaka (3–17); 10. Lisboa (3–17); 11. Los Angeles (3–17); 12. Chicago (3–17); 13. Viena (5–17); 14. Moscou (8–18); 15. Amsterdã (9–18); 16. Munique (9–18); 17. São Petersburgo (9–18); 18. Berlim (14–19); 19. Pequim (18–21); 20. Xangai (19–21); 21. Shenzhen (19–21).
- **Transit:** 1. Paris (1–12); 2. Milão (1–13); 3. São Petersburgo (1–14); 4. Londres (1–14); 5. Nova York (1–14); 6. Barcelona (1–14); 7. Madri (1–14); 8. Moscou (1–20); 9. Xangai (1–21); 10. Pequim (1–21); 11. Viena (2–17); 12. Roma (3–20); 13. Tóquio (1–21); 14. Berlim (8–21); 15. Shenzhen (1–21); 16. Los Angeles (8–21); 17. Munique (8–21); 18. Chicago (9–21); 19. Amsterdã (9–21); 20. Lisboa (11–21); 21. Osaka (9–21).
- **Bike:** 1. Munique (1–12); 2. Amsterdã (1–12); 3. Paris (1–14); 4. Nova York (1–14); 5. Milão (1–15); 6. Berlim (1–15); 7. Barcelona (1–16); 8. Londres (1–16); 9. Chicago (1–17); 10. Viena (1–17); 11. Xangai (1–19); 12. Roma (1–19); 13. Moscou (3–20); 14. Madri (3–20); 15. Pequim (5–20); 16. Tóquio (7–20); 17. Osaka (9–21); 18. Los Angeles (11–21); 19. Lisboa (11–21); 20. São Petersburgo (13–21); 21. Shenzhen (17–21).

**O recorte mexe nos rankings?**
- **Walk: pouco.** Correlação de postos de 0,87 com o município e 0,86 com o centro urbano. Paris e Milão seguem no topo e as cidades chinesas no fim (ainda como limite inferior); o que muda é o meio, com Los Angeles subindo (seu núcleo é Koreatown e arredores, bem servido) e São Petersburgo caindo.
- **Transit: bastante.** Correlação de 0,64 com o município e 0,65 com o centro urbano. Lisboa cai para 20º porque o núcleo é suburbano; São Petersburgo e Nova York sobem; Osaka fica em último. Entre município e centro urbano a correlação já era baixa (0,53), porque o Transit depende muito de onde se corta a cidade.
- **Bike: moderado.** Correlação de 0,86 com o município e 0,88 com o centro urbano. Munique e Amsterdã seguem no topo e Shenzhen no fim.
- **Raio da suavização:** trocar 1,5 km por 1 ou 2 km dá correlação de postos de 0,83 ou mais com a versão principal; a maior mudança é Lisboa no Transit com raio de 1 km.
- **Margem de 95%:** a mesma da versão principal. No Transit híbrido ela é recalculada pela fração do OSM dentro do núcleo: Moscou fica em ±14, São Petersburgo em ±10 e Londres em ±8.

Arquivos: `results/dense_core_scores.csv` (área, população, densidade do pico e do limiar, notas), `results/dense_core_rankings.csv`, `results/dense_core_cells.parquet` (que células entram), `results/ranking_comparison.csv` e as versões com raio de 1 e 2 km (`_r1000`, `_r2000`). Código: `code/30_dense_core.py`.

## 9. Sensibilidade (`results/sensitivity.csv`)

Cada teste muda uma escolha inferida e mantém o resto. A tabela abaixo mostra o desvio médio, o maior desvio em pontos e a correlação de Spearman do ranking com o principal (centro urbano, 21 cidades).

| Índice | Teste | Desvio médio | Maior desvio | Spearman |
|---|---|---|---|---|
| Walk | decaimento em tabela (formato documentado, sem calibrar) | +7,5 | 9,9 | 0,95 |
| Walk | sem penalidades de interseção e quarteirão | +2,1 | 7,1 (Moscou) | 0,95 |
| Bike | classes "suaves" (ciclofaixa 0,75, compartilhada 0,5) | +1,3 | 4,2 | 0,99 |
| Bike | classes "estritas" (compartilhada 0) | −1,8 | 4,6 | 0,99 |
| Bike | declividade p90 em vez de máxima | +0,8 | 2,1 | 0,99 |
| Bike | saturação das faixas ±25% | ±2,6 | 4,3 | 1,00 |
| Bike | sem componente de relevo | −6,4 | 15,3 | 0,97 |
| Transit | só OSM com mediana imputada, em vez da variante principal | −1,8 | 13,5 (Chicago) | 0,84 |
| Transit | modelo de frequência de ônibus (8 cidades sem GTFS completo) | +5,3 | 14,5 (Xangai) | 0,90 |
| Transit | mediana local de linhas OSM com intervalo (9 cidades) | +3,4 | 9,5 (Tóquio) | 0,93 |
| Transit | erro da fórmula de intervalos (p10/p90) | −0,3/+0,7 | 1,5 | 1,00 |
| Transit | só intervalos de grau A/B (os C/D viram mediana) | −0,5 | 1,4 | 1,00 |

**Conclusões:**
- **Os rankings resistem a quase todas as escolhas de método** (Spearman de 0,84 ou mais; o teste mais forte é trocar o Transit inteiro pelo proxy do OSM). O decaimento sem calibração eleva todas as notas de Walk em 6 a 7 pontos, mas quase não muda a ordem.
- **O que mais move as notas é a frequência dos ônibus** nas cidades sem GTFS. O modelo de ônibus sobe Xangai em 14 pontos e Pequim em 13. O motivo é que a mediana imputada (188 viagens/semana) é baixa para linhas chinesas longas. Mas o modelo não reduziu o erro na validação (seção 10), então fica como teste, não como estimativa principal.
- **Japão:** no OSM, as linhas de trem de Tóquio e Osaka que têm intervalo marcado rodam 756 viagens/semana (mediana), contra as 164 imputadas a partir de trens suburbanos dos EUA e da Europa. Usar a mediana local sobe Tóquio em 5 a 10 pontos e Osaka em 7. É um teste com viés para cima, porque linhas com intervalo marcado tendem a ser as mais movimentadas. Mesmo assim, é forte o indício de que o Transit Score principal do Japão está baixo, e o ranking de Osaka (20º) não deve ser lido como fato.
- **Relevo:** o modelo de superfície ainda deixa prédios altos em Manhattan, Paris e Moscou, o que reduz o componente de relevo (73,8 em Paris, que é plana na maior parte). O Bike Score dessas cidades pode estar alguns pontos baixo. Lisboa (52,9) e Barcelona (66,2) são de fato acidentadas.
- **Feeds desatualizados:**
  - Em São Petersburgo, 51% da soma de transporte vem do GTFS de 2021, e o metrô vem do OSM.
  - Em Barcelona, 11% (município) e 22% (centro urbano) vêm do feed de ônibus da AMB, de 2020.
  - Em Viena, 9%, e em Munique, 7%, vêm de feeds com mais de um ano.
  - Nas demais, a parcela é de 0 a 2%.

## 10. Fontes alternativas de horários: o que se achou e o que mudou na incerteza

**O que se procurou:**
- GTFS e APIs: Mobility Database, Transitland, TransitFeeds, ODPT/GTFS-JP, portais de dados de Moscou e de São Petersburgo e repositórios no GitHub.
- Intervalos por linha publicados por operadores, governos, imprensa, enciclopédias e guias.

**O que se achou e foi usado (só fontes cujos termos permitem o uso; dos intervalos, só os números):**
- **Mobility Database:**
  - Tóquio: só a Toei (metrô e ônibus municipais), usada.
  - São Petersburgo: feed de 2021, sem metrô, usado com rótulo de desatualizado.
  - Moscou: feed inativo no catálogo. Os horários do transporte de superfície vieram depois, do portal da prefeitura (ver a seção 10a).
  - Osaka e China: nada.
- **Intervalos publicados**, em `data/published_headways/round1.csv`, com grau A (oficial e datado), B (enciclopédia ou mais antigo), C (guia) ou D (limite regulatório):
  - **Shenzhen:** 15 linhas, grau A (horários oficiais citados pela imprensa em fev/2025).
  - **Pequim:** cerca de 20 linhas, grau B, e as linhas 15 e 17 em grau A. Os ramais Changping, Daxing, Fangshan, Yizhuang, Batong e Expresso do Aeroporto não foram associados às linhas do OSM com segurança e ficaram com a mediana.
  - **Moscou:** 12 linhas, mais o 8A, em grau B/C; o anel MCC em grau A. As linhas 11 e 15 a 17 e os trens MCD ficaram com a mediana.
  - **Xangai:** 18 linhas, grau D, porque o pico vem do teto regulatório de 3 a 5 min e o fora do pico foi imputado pela razão.
  - **Tóquio:** Ginza e Marunouchi em grau A, Yurakucho em grau B e Yamanote em grau C.
  - **Osaka:** Midosuji, Tanimachi e Chuo, grau C.
  - **São Petersburgo:** valor único para o sistema todo ("a cada 2 a 4 min"), grau C.
- **Teste da fórmula** em 61 linhas de metrô com GTFS: superestima 9,6% (corrigido), com erro típico de 15%, cerca de ±2,5 pontos.

**O que não deu para acessar:**
- A política de rede deste ambiente bloqueou, com 403, sem tentativa de contorno: gtfs-data.jp, ODPT, data.mos.ru (os arquivos depois chegaram pelo Drive do usuário), Transitland, TransitFeeds, o portal de transporte de São Petersburgo e os sites dos operadores (metrôs de Osaka, Xangai, Pequim, Shenzhen e Tóquio; transporte de Moscou).
- A API de membros da ODPT exige cadastro de desenvolvedor, que não foi feito sem autorização.
- A busca no GitHub exige conta vinculada, que não está disponível aqui.

**O que mudou na incerteza:**
- **Saber a frequência do trilho quase não reduz o erro.** Nas 10 cidades de validação, trocar a frequência imputada do trilho pela frequência real do GTFS mudou o erro da nota de cidade de 7,2 para 7,6 pontos (MAE no teste). O erro vem dos ônibus.
- **Por isso o intervalo das cidades sem GTFS continua em cerca de ±18 pontos**, contra ±5,5 com GTFS. O ganho dos intervalos publicados é de outro tipo: tira a dúvida sobre o metrô em cidades onde ele domina, como Moscou (+3,5 pontos sobre a mediana) e Shenzhen (+1,2).
- **O modelo de ônibus** (gradiente boosting em atributos do OSM, treinado em 21 cidades com GTFS) remove o viés de −6,5 para −1,7 nas cidades de validação, mas quase não reduz o erro (RMSE de 10,3 contra 10,5 no nível de cidade). Por ponto, o erro até aumenta (MAE de 9,4 contra 7,7 no teste).

## 10a. Moscou com dados abertos da prefeitura (data.mos.ru, CC BY 4.0)

Fonte: Portal de dados abertos do Governo de Moscou, https://data.mos.ru/ (licença CC BY 4.0, termos em https://data.mos.ru/terms), instantâneos de 12 a 18/11/2026, baixados pelo usuário.

**O que entrou:**
- **Transporte de superfície com horários oficiais:** linhas, viagens e calendários de 964 linhas (927 de ônibus, 36 de bonde, 1 de trólebus). Viagens por semana na direção mais movimentada, na mesma semana de referência das outras cidades (16 a 22/11/2026). A mediana é de 376 viagens/semana por linha de ônibus, o dobro da mediana imputada (188).
- **Paradas de cada linha:** o arquivo de horários por parada é grande demais para a rota de download disponível aqui, então as paradas vieram do registro de linhas (nome da parada na lista da linha, mesmo modo e até 60 m do traçado). Deu certo para 806 linhas; outras 134 foram ligadas à cópia da mesma linha no OSM, com as viagens oficiais. Faltaram 24.
- **Metrô, MCD, MCC e trens suburbanos não estão no portal** e seguem pelo OSM com intervalos publicados. Por isso Moscou passou a ser híbrida, não GTFS completa: 45% (município) a 49% (centro urbano) da soma de transporte ainda vem do OSM.
- **Destinos:** cerca de 25.600 estabelecimentos novos depois de tirar duplicatas a 25 m de um ponto da mesma categoria (a mesma regra de OSM × Overture): 8.249 lojas, 7.463 mercados, 6.343 cafés, 3.284 restaurantes e bares, 213 bibliotecas e livrarias e 90 cinemas, teatros e museus. Cantinas e bufês ficaram de fora, porque muitos ficam dentro de escolas, escritórios e hospitais. As escolas do portal vêm como complexos com prédios de educação infantil misturados; incluí-las sobe o Walk só 0,2 ponto, então ficaram só como teste.

**O que mudou:**

| Moscou | Antes (OSM + intervalos) | Agora (híbrida com data.mos.ru) |
|---|---|---|
| Walk, centro urbano / município | 72,6 / 72,2 | 74,6 / 74,5 |
| Bike, centro urbano / município | 51,3 / 51,1 | 51,8 / 51,7 |
| Transit, centro urbano / município | 86,1 / 86,6 | 85,7 / 86,2 |
| Intervalo de 95% do Transit | ±17,9 | ±13,2 / ±12,6 |

- **A margem do Transit caiu cerca de 5 pontos**, de ±17,9 para ±13 nas duas geografias. Não chega aos ±5,5 das cidades com GTFS completo, porque o trilho continua estimado.
- **A nota quase não mudou** (−0,4 ponto). As linhas de ônibus reais rodam o dobro da mediana imputada, mas o proxy antigo contava variantes da mesma linha no OSM como linhas separadas, e os dois efeitos se compensaram. Por célula, a diferença média absoluta é de 2,7 pontos (correlação de 0,99).
- **Ranking:** Moscou segue em 2º no Transit do centro urbano, agora com faixa de 1º a 14º (antes 1º a 16º). No Walk do centro urbano, sobe de 13º para 10º.

## 11. O que está parcial

- **Transit Score de Osaka, Xangai, Pequim e Shenzhen**, e a parte OSM de Tóquio, São Petersburgo e Moscou: estimativa com rótulo. Ônibus e parte dos trens têm frequência imputada. O intervalo é de cerca de ±18 (±13 em Moscou e São Petersburgo), com tendência a subestimar, forte em Osaka e Tóquio.
- **Moscou, trilho:** metrô, MCD, MCC e trens suburbanos seguem com intervalos publicados ou mediana; o portal da prefeitura só traz o transporte de superfície. As escolas do portal ficaram só no teste de sensibilidade.
- **Walk Score das cidades chinesas:** limite inferior, por falta de destinos mapeados.
- **Bike Score:** versão de três componentes (sem participação modal). Por ponto erra em média 10 pontos nos EUA; o relevo usa modelo de superfície.
- **Feeds desatualizados:** ônibus de Barcelona (AMB, 2020), São Petersburgo (2021) e alguns trens (Metrolink 2023, ÖBB e MVV com mais de um ano).
- **Londres, trens:** o feed de ônibus e metrô (BODS) não traz Overground, Elizabeth line nem trens da National Rail. Eles entraram pelo OSM: 84 linhas com intervalo marcado e 103 com mediana. Por isso Londres é híbrida, com margem de cerca de ±8 no Transit.
- **Munique:** o S-Bahn não tem viagens no feed e entrou pelo OSM, com mediana.
- **Centro urbano:** refeito pela regra DEGURBA sobre a grade Kontur, porque o GHS-FUA oficial não pôde ser baixado. Pode diferir um pouco do polígono oficial.
- **Validação só nos EUA:** é o único lugar com notas oficiais. A transferência para outros países é uma suposição, testada só indiretamente: no Japão, pela Toei, e nas cidades europeias, comparando o proxy com o GTFS.

## 12. Registros de transparência

- Os termos da Redfin (§2.3.5) proíbem consulta automatizada ao walkscore.com, e nenhuma nota foi coletada automaticamente. Uma página de cidade (Chicago) foi lida pela ferramenta de leitura antes de os termos serem verificados. Os números dela não entram na validação: as notas de cidade usadas vêm dos valores copiados à mão pelo usuário.
- **Pontos de validação:** 120 de 150 usados. 20 eram endereços genéricos, como "rua X" sem número, e 10 não puderam ser localizados com segurança.
- **Notas de cidade:** da tabela de 129 cidades, entraram 10 (as que têm os insumos processados).
- Nenhuma conta foi criada, nada foi pago e nenhum cadastro foi feito.

## 13. Arquivos

- `results/city_scores.csv`: tabela comparativa, com média, mediana, percentis, parcelas por faixa e intervalos.
- `results/rankings.csv`: rankings separados por índice e geografia, com faixa de posições.
- `results/cells/<cidade>_cells.parquet`: GeoParquet com todas as células e todas as variantes de transporte.
- `results/cells_all.gpkg` (212 MB, uma camada por cidade) e `results/cells_all.csv.gz`.
- `results/maps/`, `results/fig_*.png`: mapas e gráficos.
- `results/validation_*.csv`: validação, incluindo os pontos e as métricas por cidade e por faixa.
- `results/sensitivity.csv`, `results/poi_density.csv`, `results/local_tagged_medians.csv`, `results/proxy_variants_*.csv`, `results/bus_model_*.csv`, `results/headway_formula_check.csv`: sensibilidade e testes.
- `results/source_inventory.csv`: inventário de fontes, com licenças e auditoria.
- `code/`: código reproduzível, scripts 01 a 29 em ordem (25 a 28: dados abertos de Moscou; 29: tabelas deste relatório). Os parâmetros calibrados estão em `code/params_calibrated.json`.
