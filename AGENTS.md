# AGENTS.md – Análise Eleitoral 2026 (Deputado Federal + Presidente 2º Turno)

## Objetivo do projeto
1. Acompanhar e analisar o 2º turno presidencial (Flávio Bolsonaro vs Lula) com dados em tempo real ou mais recentes do TSE.
2. Analisar o desempenho de partidos nas eleições de 2026 para Deputado Federal de todos os partidos políticos
3. Gerar mapa municipal do Brasil com votos, vencedor local, comparação com 1º turno 2026, com 2022 e 2018 para presidente da República
4. No início de cada execução relevante: cálculo de voting prediction atualizado com chance de vitória.

Pergunta central (Deputado): quais fatores estruturais (experiência, concentração territorial, arrasto presidencial, tamanho da chapa, contexto estadual) explicam eleitos e cláusula de barreira?

## Stack
- Python 3.11+, Javascript e bibliotecas de animação como ThreeJS
- pandas, numpy, statsmodels, scikit-learn, plotly, streamlit, geopandas (ou folium), requests
- Dados em `data/`
- Mapas e saídas intermediárias em `data/` ou `output/`

## Fontes de dados prioritárias
- **Candidatos e resultados oficiais**: https://dadosabertos.tse.jus.br/ (Candidatos-2026, Resultados-2026, Histórico)
- **Apuração em tempo real / mais recente**: https://resultados.tse.jus.br (JSON via config `ele-c.json` e endpoints de totalização municipal/UF/BR). Atualizar após 17h do dia 25/10/2026.
- **Histórico 2022 e 2018**: arquivos equivalentes do portal de dados abertos ou repositórios consolidados.
- **Malha municipal**: IBGE (shapefile ou GeoJSON da Malha Municipal). Preferir versão nacional unificada.
- Pesquisas: agregar últimos levantamentos públicos (Datafolha, RealTime, PoderData etc.) apenas para a prediction inicial.

## Convenções
- Código modular e bem comentado.
- Documentar todas as decisões de limpeza, joins e tratamento de missings.
- Salvar DataFrames em parquet.
- Mapas: Plotly (choropleth) ou Folium/GeoPandas. Município colorido pelo vencedor + tooltip com votos absolutos e % + comparação (Δ vs 1º turno e vs 2022).
- Prediction no início: média simples ou ponderada de pesquisas + intervalo de confiança ou probabilidade aproximada de vitória (documentar método).
- Preferir funções reutilizáveis. Usar Plan mode antes de implementar.

## Estrutura esperada (expandida)

/
├── AGENTS.md
├── data/
│   ├── candidatos_df.parquet
│   ├── presidente_municipio_2026_1t.parquet
│   ├── presidente_municipio_2026_2t.parquet   # atualizado em tempo real
│   ├── presidente_municipio_2022.parquet
│   ├── malha_municipios.geojson (ou .shp)
│   └── dicionario_variaveis.md
├── 01_pipeline_dados.py
├── analise_descritiva.py
├── modelos.py
├── mapas.py
├── app.py
├── requirements.txt
└── artigo_esqueleto.md

## Regras de trabalho
- Não inventar dados. Se endpoint ou arquivo não estiver disponível, documentar e usar o mais recente possível.
- Dados de apuração ao vivo mudam rapidamente após 17h do dia 25/10. Prever função de refresh.
- Sempre gerar o bloco de prediction no início do pipeline ou do dashboard.
- Mapas devem permitir comparação clara (abas, layers ou figuras lado a lado).
