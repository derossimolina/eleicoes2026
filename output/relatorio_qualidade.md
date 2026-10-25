# Relatório de qualidade — Fase 1

Gerado em 2026-10-25T15:14:23.

## Prediction

- Pesquisas na média: 16
- Flávio 50.96% | Lula 49.04%
- P(vitória), tau 2 p.p.: Flávio 0.6827 | Lula 0.3173
- Excluídas: ['Meio/Ideia', 'Ipespe/Abrapel']

## Presidente

- Municípios no de-para do TSE (2º turno): 5571. Referência IBGE usada só como ordem de grandeza: 5.570 municípios em 2024.
- Municípios com voto em 2026 1º turno: 5571. Com código IBGE: 5571.
- Municípios no 2º turno de 2022: 5570. No 2º turno de 2018: 5570.
- Totais lidos nos arquivos de seção (sem exterior): {'2026_1t_lula': 53722151, '2026_1t_flavio': 55960603, '2026_1t_validos': 118975029, '2022_2t_lula': 60193094, '2022_2t_bolsonaro': 58061090, '2018_2t_haddad': 46987176, '2018_2t_bolsonaro': 57666176}
- Exterior (ZZ), soma de votos e os quatro números mais votados, por ano e turno: {'2018': {'1': {'votos': 202766, 'topo': {'17': 113690, '12': 28073, '13': 19540, '30': 13637}}, '2': {'votos': 201166, 'topo': {'17': 131671, '13': 53730, '96': 8524, '95': 7241}}}, '2022': {'1': {'votos': 304032, 'topo': {'13': 138933, '22': 122548, '12': 13341, '15': 13167}}, '2': {'votos': 310148, 'topo': {'13': 152905, '22': 145264, '96': 6079, '95': 5900}}}, '2026': {'1': {'votos': 341766, 'topo': {'13': 157387, '22': 143900, '70': 9734, '14': 8580}}}}
- 2º turno ao vivo: {'url': 'https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json', 'dg': '24/10/2026', 'hg': '19:19:13', 'tf': 'n', 'and': 'n', 'secoes_totalizadas': 0, 'secoes_totais': 499248, 'pct_secoes': 0.0, 'votos_validos_br': 0, 'apuracao_completa': False}

O 1º turno de 2026, nos dados abertos, deve ficar perto de 47% para Flávio e 45% para Lula nos votos válidos. Os totais acima são a soma do arquivo, não um número recolocado.

## Deputado federal

- {'linhas': 7049, 'eleitos_preenchidos': 512, 'eleito_nulo': 0, 'votos_zero': 0, 'experiencia': 0.6647751454106966, 'soma_votos': 110199601}

Contexto IBGE por UF não entrou. O Censo municipal não foi baixado nesta fase; a coluna ficaria vazia e foi omitida.

## Malha

- {'poligonos': 5573, 'casados': 5571}

## Decisões e achados

- De-para TSE→IBGE: 186 localidades do exterior (ZZ) saíram da base municipal. O voto delas segue só no relatório, somado a partir da seção.
- 2º turno: o arquivo nacional br-c0001-e006258-u.json está com zero seções totalizadas. Os votos municipais ficaram nulos. Não houve uma requisição por município, porque o total nacional zero implica que nenhuma seção entrou. Rode de novo com --refresh-2t quando a totalização começar.
- 2026 tem 5571 municípios com voto e 2022 tem 5570. Só em 2026: BOA ESPERANÇA DO NORTE (MT, TSE 73709, IBGE 5101837). Na malha baixada, Boa Esperança do Norte entrou. Os dois polígonos sem voto são as lagoas dos Patos e Mirim, no Rio Grande do Sul.
- consulta_cand_2026 publica DS_SITUACAO_CANDIDATURA = #NE e código -3 para todos os deputados federais. O filtro usa DS_SITUACAO_JULGAMENTO da votação por município e zona. Entra o texto que começa com DEFERIDO, o que cobre deferido e deferido com recurso. Indeferido, inclusive em prazo recursal, fica de fora.
- Deputado: 7803 candidaturas no consulta_cand, fora ZZ. 541 sem julgamento na votação nominal. 7049 permaneceram porque o julgamento começa com DEFERIDO.
- Deputado: 0 deferidos sem título eleitoral; experiencia_previa ficou nula nesses casos.
- Quociente: votos válidos da UF = QT_VOTOS_NOMINAIS_VALIDOS + QT_TOTAL_VOTOS_LEG_VALIDOS, cargo 6, turno 1. Em 100.0% das linhas, o total de legenda é a soma de legenda e nominais convertidos em legenda. QE = divisão inteira desses válidos pelo número de cadeiras (a fração é desprezada, como na lei).
- votos_presidente_partido_uf é o voto do candidato a presidente do mesmo número de partido na UF, no 1º turno de 2026. Partido sem candidato a presidente fica 0. Não usa a federação.
- Deputado: 512 candidaturas com situação começando em ELEITO. A Câmara tem 513 cadeiras. O número do arquivo foi mantido, sem ajuste.
- A cadeira que falta é do Espírito Santo. LUCAS O FEDERAL DA DIREITA (ES, PL) está como ELEITO POR QP na votação, com 43.973 votos nominais, mas o julgamento é PENDENTE DE JULGAMENTO. Por isso não entrou na base de deferidos. O estado fica com 9 eleitos na base e 10 cadeiras.
- Malha: 5573 polígonos, 5571 com voto municipal casado pelo código IBGE.
- Mapa: a base cartográfica é OpenStreetMap. O Folium instalado avisa que o CartoDB positron exige chave.
- PNG do 2º turno não foi desenhado: não há voto totalizado. Foi salvo o mapa do 1º turno de 2026.

## O que este relatório não fecha

- A prediction não observa urna. O tau de 2 p.p. é cenário, calibrado na literatura, não um erro histórico reestimado para 2026.
- Experiência prévia usa o título eleitoral em 2018, 2020, 2022 e 2024. Título ausente ou com dígito diferente não casa.
- Município criado ou com código TSE que não está no JSON de 25/10/2026 fica sem código IBGE e fora do mapa.
