# Dicionário de variáveis

Data de referência da prediction: 25/10/2026. Apuração do 2º turno: o que o TSE servir na hora em que o script roda.

## Prediction (`data/prediction_inicial.json`)

Média ponderada das pesquisas com votos válidos preenchidos em `data/raw/pesquisas_2t_2026.csv`.

Peso: precisão publicada vezes decaimento com meia-vida de 3 dias, no espírito de Jackman (2005). Probabilidade: normal, com erro não amostral no sentido de Shirani-Mehr, Rothschild, Goel e Gelman (2018, JASA). Tau principal = 2 pontos percentuais.

`p` de cada pesquisa é Flávio / (Flávio + Lula), em proporção dos votos válidos.

## Deputado federal (`data/candidatos_df.parquet`)

Uma linha por candidatura a deputado federal em 2026, `CD_CARGO = 6`, UF diferente de ZZ, situação normalizada começando com DEFERIDO (inclui deferido com recurso). Indeferido, cassado, cancelado e renúncia ficam de fora.

| Variável | Definição |
|---|---|
| sq_candidato, nr_candidato, nm_urna, nm_candidato | Identificação no consulta_cand_2026 |
| sg_uf, nr_partido, sg_partido, nm_partido, sg_federacao | Partido e UF da candidatura |
| ds_situacao_candidatura | Texto de DS_SITUACAO_JULGAMENTO na votação nominal. Em 2026 o consulta_cand traz #NE nessa situação, então o filtro não usa aquele campo |
| votos_nominais | Soma de QT_VOTOS_NOMINAIS_VALIDOS na votação nominal por município e zona, turno 1. Sem voto de legenda. Ausência de linha vira 0 |
| log_votos | log(1 + votos_nominais). Voto nulo permanece nulo |
| eleito | Verdadeiro se DS_SIT_TOT_TURNO normalizado começa com ELEITO. Nulo se o TSE ainda não preencheu a coluna. Não é zero |
| superou_quociente | votos_nominais >= quociente eleitoral da UF |
| quociente_eleitoral | Divisão inteira dos votos válidos do cargo na UF pelo número de cadeiras. A fração é desprezada |
| votos_validos_uf | Nominais válidos + total de votos de legenda válidos, cargo 6, turno 1 |
| cadeiras_uf | QT_VAGA em consulta_vagas_2026. Se a UF repetir, fica o máximo, não a soma |
| experiencia_previa | 1 se o título eleitoral aparece em consulta_cand de 2018, 2020, 2022 ou 2024, em qualquer cargo. 0 se o título existe e não aparece. Nulo se o título falta |
| votos_presidente_partido_uf | Votos do candidato a presidente com o mesmo número de partido, na UF, 1º turno de 2026. Partido sem candidato a presidente: 0. Federação não herda o voto do PT ou do PL |
| n_candidatos_partido_uf | Deferidos a deputado federal do mesmo partido na UF, nesta base |
| ds_genero, idade_na_eleicao, ds_grau_instrucao, ds_estado_civil, ds_cor_raca, ds_ocupacao | Características do consulta_cand. A idade é calculada em 04/10/2026 porque o arquivo de 2026 não traz NR_IDADE_DATA_POSSE. Fora de 18 a 100 vira nulo |
| uf_* | Dummies de UF, todas as unidades presentes, sem omitir uma categoria |

Voto negativo vira nulo. Voto não é winsorizado. Exterior (ZZ) fica de fora.

## Presidente

Chave: `sg_uf` + `cd_municipio_tse` (5 dígitos). `cd_ibge` vem de `mun-e006258-cm.json` (`cdi`), o de-para oficial do TSE para o 2º turno. Sem correspondência, o código IBGE fica nulo. Não há imputação por nome.

Branco é 95 e nulo é 96. Votos válidos são o resto. Comparecimento é a soma de tudo no cargo de presidente. Exterior ZZ não entra no parquet municipal; o total vai para o relatório.

| Arquivo | Conteúdo |
|---|---|
| presidente_municipio_2026_1t.parquet | Lula (13) e Flávio (22) |
| presidente_municipio_2026_2t.parquet | Os mesmos números. Votos nulos se nenhuma seção foi totalizada |
| presidente_municipio_2022.parquet | Turnos 1 e 2. Lula (13) e Bolsonaro (22). Coluna `turno` |
| presidente_municipio_2018.parquet | Turnos 1 e 2. Haddad (13) e Bolsonaro (17) |
| presidente_municipio_comparativo.parquet | Uma linha por município, com as fatias usadas no mapa |

`pct_*` é a fatia dos votos válidos, em percentual. `vencedor` é quem teve mais votos entre todos os candidatos do turno; empate fica EMPATE. `vencedor_par` compara só os dois nomes do turno (no 1º turno de 2026, Lula e Flávio, mesmo quando um terceiro ficou à frente no município).

`diferenca_pp` é a distância absoluta, em pontos percentuais dos válidos, entre esses dois nomes.

No 2º turno de 2026:

- `delta_lula_pp_vs_1t` e `delta_flavio_pp_vs_1t`: fatia do 2º turno menos a fatia do 1º turno de 2026. As duas podem subir, porque o 1º turno tinha mais candidatos.
- `delta_lula_pp_vs_2022_2t`: Lula 2026 menos Lula 2022, os dois no 2º turno.
- `delta_22_pp_vs_2022_2t`: fatia do candidato 22 em 2026 (Flávio) menos a fatia do candidato 22 em 2022 (Bolsonaro). Não é a mesma pessoa.
- `pct_secoes_apuradas`, `apuracao_completa`, `dh_arquivo_tse`, `fonte`: estado do arquivo do TSE.

Quando o arquivo nacional está com zero seções, voto municipal não é gravado como zero. Zero seria lido como empate.

## Mapa

`output/mapa_presidente_municipios.html`. Cor do vencedor da camada: Lula/Haddad `#E04B4B`, Flávio/Bolsonaro `#2F6FED`, empate ou sem dado em cinza. O tooltip do 2º turno traz votos, percentuais, diferença e as variações contra o 1º turno de 2026 e contra o 2º turno de 2022.
