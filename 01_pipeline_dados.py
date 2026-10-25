"""Pipeline da Fase 1 — presidente (municipal) e deputado federal.

Imprime a prediction no início. A ordem interna dos blocos pesados coloca o
1º turno presidencial de 2026 antes do deputado, porque
votos_presidente_partido_uf sai dessa agregação. A prediction continua sendo
a primeira coisa impressa.

Não inventa apuração: se o arquivo nacional do 2º turno estiver com zero
seções totalizadas, os votos municipais ficam nulos e a função
atualizar_segundo_turno baixa município a município só quando a totalização
já começou.

Fontes, filtros e o modelo da probabilidade estão no dicionário e no
relatório gerados ao final.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
import zipfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw" / "tse"
OUT = ROOT / "output"
PESQUISAS = DATA / "raw" / "pesquisas_2t_2026.csv"
SIB = Path(r"D:\projects\eleicoes_pib\data\raw\tse")
CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
TSE = "https://resultados.tse.jus.br/oficial/ele2026/6258"
# Código da eleição federal de 2026 no nome dos arquivos do TSE, com 6 dígitos.
ELE = "006258"
REF = date(2026, 10, 25)
# Meia-vida de 3 dias na reta final do 2º turno. Jackman (2005) pondera por
# precisão; a meia-vida curta é a escolha aplicada porque só entra uma rodada
# por instituto e o campo cabe em duas semanas.
MEIA_VIDA_DIAS = 3.0
# Erro de eleição que não encolhe ao juntar pesquisas. Shirani-Mehr, Rothschild,
# Goel e Gelman (2018, JASA) mostram que o erro total das pesquisas é bem maior
# que a margem publicada. 2 p.p. é o cenário principal; 1,5 e 3 são sensibilidade.
TAU_PRINCIPAL = 0.02
TAUS_SENSIBILIDADE = (0.015, 0.03)

ARQUIVOS = {
    "votacao_secao_2018_BR.zip": f"{CDN}/votacao_secao/votacao_secao_2018_BR.zip",
    "votacao_secao_2022_BR.zip": f"{CDN}/votacao_secao/votacao_secao_2022_BR.zip",
    "votacao_secao_2026_BR.zip": f"{CDN}/votacao_secao/votacao_secao_2026_BR.zip",
    "votacao_partido_munzona_2026.zip": f"{CDN}/votacao_partido_munzona/votacao_partido_munzona_2026.zip",
    "votacao_candidato_munzona_2026.zip": f"{CDN}/votacao_candidato_munzona/votacao_candidato_munzona_2026.zip",
    "consulta_vagas_2026.zip": f"{CDN}/consulta_vagas/consulta_vagas_2026.zip",
    "consulta_cand_2018.zip": f"{CDN}/consulta_cand/consulta_cand_2018.zip",
    "consulta_cand_2020.zip": f"{CDN}/consulta_cand/consulta_cand_2020.zip",
    "consulta_cand_2022.zip": f"{CDN}/consulta_cand/consulta_cand_2022.zip",
    "consulta_cand_2024.zip": f"{CDN}/consulta_cand/consulta_cand_2024.zip",
    "consulta_cand_2026.zip": f"{CDN}/consulta_cand/consulta_cand_2026.zip",
}
MALHAS = [
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2024/Brasil/BR_Municipios_2024.zip",
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2023/Brasil/BR_Municipios_2023.zip",
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/Brasil/BR_Municipios_2022.zip",
]
CORES = {"pt": "#E04B4B", "pl": "#2F6FED", "outro": "#8C8378", "empate": "#B7B1A8", "sem_dado": "#E6E2DA"}
# Números de urna. Conferidos depois da agregação: se não estiverem entre os
# mais votados do turno, o script para em vez de gravar a coluna errada.
PARES = {
    2018: {1: [(13, "haddad"), (17, "bolsonaro")], 2: [(13, "haddad"), (17, "bolsonaro")]},
    2022: {1: [(13, "lula"), (22, "bolsonaro")], 2: [(13, "lula"), (22, "bolsonaro")]},
    2026: {1: [(13, "lula"), (22, "flavio")], 2: [(13, "lula"), (22, "flavio")]},
}

NOTAS: list[str] = []
AMOSTRAS: list[str] = []
ESTADO: dict = {}


def log(msg: str) -> None:
    print(msg, flush=True)


def sem_acento(valor) -> str:
    texto = "" if valor is None or (isinstance(valor, float) and math.isnan(valor)) else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).upper().strip()


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def num_br(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    texto = str(valor).strip()
    if texto == "":
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "eleicoes2026-pipeline/0.1 (analise de dados eleitorais)"
    return s


def localizar(nome: str) -> Path | None:
    for pasta in (RAW, SIB):
        caminho = pasta / nome
        if caminho.exists() and caminho.stat().st_size > 0:
            return caminho
    return None


def baixar(nome: str, url: str | None = None, destino: Path | None = None) -> Path:
    destino = destino or (RAW / nome)
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    url = url or ARQUIVOS[nome]
    if ESTADO.get("sem_download"):
        raise FileNotFoundError(f"Arquivo ausente e --sem-download ligado: {destino} ({url})")
    destino.parent.mkdir(parents=True, exist_ok=True)
    log(f"Baixando {url}")
    with sessao().get(url, stream=True, timeout=120) as resposta:
        resposta.raise_for_status()
        with destino.open("wb") as saida:
            for bloco in resposta.iter_content(1024 * 256):
                if bloco:
                    saida.write(bloco)
    return destino


def garantir(nome: str) -> Path:
    achado = localizar(nome)
    if achado is not None:
        log(f"Usando {achado}")
        return achado
    return baixar(nome)


def publicar(df: pd.DataFrame, caminho: Path, nome: str) -> None:
    """Mostra shape, colunas e cinco linhas e só então grava o parquet."""
    prev = df.head(5)
    with pd.option_context("display.max_columns", 40, "display.width", 200, "display.max_colwidth", 40):
        amostra = prev.to_string(index=False)
    bloco = f"## {nome}\n\nshape: {df.shape}\n\ncolunas: {list(df.columns)}\n\n```\n{amostra}\n```"
    log("\n" + bloco + "\n")
    AMOSTRAS.append(bloco)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(caminho, index=False)
    log(f"Salvo {caminho}")


def csvs_zip(caminho: Path) -> tuple[zipfile.ZipFile, list[str]]:
    z = zipfile.ZipFile(caminho)
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    return z, nomes


# --------------------------------------------------------------------------- prediction
def calcular_prediction() -> dict:
    if not PESQUISAS.exists():
        raise FileNotFoundError(PESQUISAS)
    bruto = pd.read_csv(PESQUISAS, dtype={"registro_tse": str})
    bruto["data_inicio"] = pd.to_datetime(bruto["data_inicio"]).dt.date
    bruto["data_fim"] = pd.to_datetime(bruto["data_fim"]).dt.date
    ok = bruto["flavio_validos"].notna() & bruto["lula_validos"].notna() & bruto["margem_erro_pp"].notna()
    fora = bruto.loc[~ok].copy()
    base = bruto.loc[ok].copy()
    if base.empty:
        raise RuntimeError("Nenhuma pesquisa com votos válidos preenchidos.")

    soma = base["flavio_validos"] + base["lula_validos"]
    base["p_flavio"] = base["flavio_validos"] / soma
    meio = base.apply(lambda r: (r["data_inicio"].toordinal() + r["data_fim"].toordinal()) / 2, axis=1)
    base["idade_dias"] = REF.toordinal() - meio
    # Variância publicada da proporção. A margem está em pontos percentuais.
    base["var"] = (base["margem_erro_pp"] / 100.0 / 1.96) ** 2
    lam = math.log(2) / MEIA_VIDA_DIAS
    base["peso"] = np.exp(-lam * base["idade_dias"]) / base["var"]
    peso = base["peso"].sum()
    p_bar = float((base["peso"] * base["p_flavio"]).sum() / peso)
    var_am = float((base["peso"] ** 2 * base["var"]).sum() / peso ** 2)

    def prob(tau: float) -> float:
        sigma = math.sqrt(var_am + tau ** 2)
        return phi((p_bar - 0.5) / sigma)

    pesquisas = []
    for _, r in base.sort_values("data_fim").iterrows():
        pesquisas.append({
            "instituto": r["instituto"],
            "data_inicio": r["data_inicio"].isoformat(),
            "data_fim": r["data_fim"].isoformat(),
            "n": int(r["n"]) if pd.notna(r["n"]) else None,
            "margem_erro_pp": float(r["margem_erro_pp"]),
            "flavio_validos": float(r["flavio_validos"]),
            "lula_validos": float(r["lula_validos"]),
            "p_flavio": round(float(r["p_flavio"]), 6),
            "idade_dias": round(float(r["idade_dias"]), 2),
            "peso_relativo": round(float(r["peso"] / peso), 4),
            "registro_tse": r["registro_tse"],
            "url_fonte": r["url_fonte"],
            "observacao": None if pd.isna(r["observacao"]) else str(r["observacao"]),
        })
    excluidas = [
        {"instituto": r["instituto"], "observacao": None if pd.isna(r["observacao"]) else str(r["observacao"])}
        for _, r in fora.iterrows()
    ]
    sigma = math.sqrt(var_am + TAU_PRINCIPAL ** 2)
    resultado = {
        "tipo": "previsao_pre_eleitoral",
        "aviso": "Não é leitura de urna. Usa só pesquisas com campo encerrado até 24/10/2026.",
        "data_referencia": REF.isoformat(),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "disputa": "Flávio Bolsonaro (PL) x Lula (PT), 2º turno, votos válidos",
        "metodo": {
            "media": "Média ponderada por precisão publicada e recência, no espírito de Jackman (2005), Pooling the polls over an election campaign, Australian Journal of Political Science 40(4): 499-517. Com uma rodada por instituto, efeito de casa não é identificável e não entra no peso.",
            "peso": "w_i = exp(-ln(2)/3 * idade_dias) / v_i, v_i = (margem_erro_pp/100/1,96)^2. Idade medida do meio do campo até 25/10/2026. Meia-vida de 3 dias.",
            "proporcao": "p_i = flavio / (flavio + lula), para absorver arredondamento que não soma 100.",
            "probabilidade": "Fonte principal do intervalo: Shirani-Mehr, Rothschild, Goel e Gelman (2018), Disentangling Bias and Variance in Election Polls, JASA 113(522): 607-614. O erro amostral da média encolhe; o erro comum de eleição não. P(Flávio > 0,5) = Phi((p_barra - 0,5) / sigma), sigma^2 = variância amostral da média + tau^2.",
            "tau_principal_pontos": TAU_PRINCIPAL * 100,
            "tau_e_escolha": "2 pontos percentuais no cenário principal. Não é um RMSE estimado para o Brasil nesta rodada; é a ordem de grandeza do erro não amostral que o artigo da JASA separa da margem publicada. Sensibilidade em 1,5 e 3,0.",
        },
        "n_pesquisas_na_media": int(len(base)),
        "media_ponderada_flavio": round(p_bar, 6),
        "media_ponderada_lula": round(1 - p_bar, 6),
        "media_ponderada_flavio_pct": round(100 * p_bar, 2),
        "media_ponderada_lula_pct": round(100 * (1 - p_bar), 2),
        "sigma_amostral": round(math.sqrt(var_am), 6),
        "sigma_total_tau_2pp": round(sigma, 6),
        "intervalo_95_flavio_tau_2pp": [round(p_bar - 1.96 * sigma, 6), round(p_bar + 1.96 * sigma, 6)],
        "prob_vitoria_flavio": round(prob(TAU_PRINCIPAL), 4),
        "prob_vitoria_lula": round(1 - prob(TAU_PRINCIPAL), 4),
        "sensibilidade_prob_flavio": {f"tau_{tau * 100:.1f}pp": round(prob(tau), 4) for tau in TAUS_SENSIBILIDADE},
        "pesquisas": pesquisas,
        "excluidas": excluidas,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "prediction_inicial.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = [
        "# Prediction inicial — 2º turno presidencial 2026",
        "",
        "Previsão pré-eleitoral com data de referência 25/10/2026. Não é apuração.",
        "",
        f"- Pesquisas na média: {resultado['n_pesquisas_na_media']}",
        f"- Média ponderada, votos válidos: Flávio {resultado['media_ponderada_flavio_pct']}% e Lula {resultado['media_ponderada_lula_pct']}%",
        f"- Probabilidade aproximada de vitória (tau = 2 p.p.): Flávio {resultado['prob_vitoria_flavio']:.1%} e Lula {resultado['prob_vitoria_lula']:.1%}",
        f"- Sensibilidade da probabilidade de Flávio: {resultado['sensibilidade_prob_flavio']}",
        f"- Intervalo de 95% para a fatia de Flávio, no mesmo tau: {resultado['intervalo_95_flavio_tau_2pp']}",
        "",
        "Modelo: peso de Jackman (2005) com precisão publicada e meia-vida de 3 dias; probabilidade normal com erro não amostral no sentido de Shirani-Mehr, Rothschild, Goel e Gelman (2018, JASA). O tau de 2 p.p. é cenário, não estimativa própria para o Brasil.",
        "",
        "## Pesquisas",
        "",
    ]
    for item in pesquisas:
        linhas.append(
            f"- {item['instituto']} ({item['data_inicio']} a {item['data_fim']}, n={item['n']}, "
            f"margem {item['margem_erro_pp']} p.p., {item['registro_tse']}): "
            f"Flávio {item['flavio_validos']} / Lula {item['lula_validos']}, peso {item['peso_relativo']:.1%}. {item['url_fonte']}"
        )
    linhas += ["", "## Fora da média", ""]
    for item in excluidas:
        linhas.append(f"- {item['instituto']}: {item['observacao']}")
    (DATA / "prediction_inicial.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    ESTADO["prediction"] = resultado
    log("")
    log("=== PREDICTION INICIAL (pré-eleitoral, referência 25/10/2026) ===")
    log(f"Média ponderada dos votos válidos: Flávio {resultado['media_ponderada_flavio_pct']}% | Lula {resultado['media_ponderada_lula_pct']}%")
    log(f"P(vitória) com tau de 2 p.p.: Flávio {resultado['prob_vitoria_flavio']:.1%} | Lula {resultado['prob_vitoria_lula']:.1%}")
    log(f"Sensibilidade P(Flávio): {resultado['sensibilidade_prob_flavio']}")
    log(f"Fonte do intervalo: Shirani-Mehr et al. (2018, JASA). Pooling: Jackman (2005).")
    log(f"Pesquisas na média: {resultado['n_pesquisas_na_media']}. Excluídas: {len(excluidas)}.")
    log("Detalhe em data/prediction_inicial.md")
    log("")
    return resultado


def grafico_prediction(resultado: dict) -> None:
    try:
        import plotly.graph_objects as go
    except ImportError:
        NOTAS.append("Plotly não está instalado; o HTML das pesquisas não foi gerado.")
        return
    itens = resultado["pesquisas"]
    fig = go.Figure()
    fig.add_bar(name="Flávio", x=[i["instituto"] for i in itens], y=[i["flavio_validos"] for i in itens], marker_color="#2F6FED")
    fig.add_bar(name="Lula", x=[i["instituto"] for i in itens], y=[i["lula_validos"] for i in itens], marker_color="#E04B4B")
    fig.add_hline(y=resultado["media_ponderada_flavio_pct"], line_dash="dash", line_color="#2F6FED",
                  annotation_text=f"média Flávio {resultado['media_ponderada_flavio_pct']}%")
    fig.update_layout(
        barmode="group", template="plotly_white",
        title="Pesquisas do 2º turno usadas na média (votos válidos, %)",
        yaxis_title="%", yaxis_range=[45, 55], height=480,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    fig.write_html(OUT / "prediction_pesquisas.html", include_plotlyjs="cdn")
    log(f"Salvo {OUT / 'prediction_pesquisas.html'}")


# ----------------------------------------------------------------------- presidente
def agregar_secao(zip_path: Path, ano: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    z, nomes = csvs_zip(zip_path)
    nome = nomes[0]
    log(f"Lendo {nome} em {zip_path.name}")
    partes, exterior = [], []
    colunas = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_TURNO", "CD_CARGO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]
    leitor = pd.read_csv(
        z.open(nome), sep=";", encoding="latin1", usecols=colunas, chunksize=2_000_000,
        dtype={"SG_UF": str, "CD_MUNICIPIO": str, "NM_MUNICIPIO": str, "NM_VOTAVEL": str},
    )
    for i, chunk in enumerate(leitor, start=1):
        chunk = chunk[chunk["CD_CARGO"] == 1]
        if chunk.empty:
            continue
        for col in ("NR_TURNO", "NR_VOTAVEL", "QT_VOTOS"):
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
        negativo = chunk["QT_VOTOS"].notna() & (chunk["QT_VOTOS"] < 0)
        if negativo.any():
            NOTAS.append(f"{ano}: {int(negativo.sum())} linhas de seção com voto negativo; descartadas.")
            chunk = chunk.loc[~negativo]
        chunk["SG_UF"] = chunk["SG_UF"].str.upper()
        zz = chunk[chunk["SG_UF"] == "ZZ"]
        br = chunk[chunk["SG_UF"] != "ZZ"]
        if len(zz):
            exterior.append(zz.groupby(["NR_TURNO", "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum())
        if len(br):
            partes.append(br.groupby(["SG_UF", "CD_MUNICIPIO", "NR_TURNO", "NR_VOTAVEL"], as_index=False).agg(
                QT_VOTOS=("QT_VOTOS", "sum"), NM_MUNICIPIO=("NM_MUNICIPIO", "first"), NM_VOTAVEL=("NM_VOTAVEL", "first"),
            ))
        log(f"  {ano}: chunk {i} lido")
    votos = pd.concat(partes, ignore_index=True)
    votos = votos.groupby(["SG_UF", "CD_MUNICIPIO", "NR_TURNO", "NR_VOTAVEL"], as_index=False).agg(
        QT_VOTOS=("QT_VOTOS", "sum"), NM_MUNICIPIO=("NM_MUNICIPIO", "first"), NM_VOTAVEL=("NM_VOTAVEL", "first"),
    )
    votos["CD_MUNICIPIO"] = votos["CD_MUNICIPIO"].str.replace(r"\.0$", "", regex=True).str.zfill(5)
    ext = pd.concat(exterior, ignore_index=True).groupby(["NR_TURNO", "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum() if exterior else pd.DataFrame()
    return votos, ext


def conferir_numeros(votos: pd.DataFrame, ano: int, turno: int) -> None:
    d = votos[(votos["NR_TURNO"] == turno) & (~votos["NR_VOTAVEL"].isin([95, 96]))]
    top = d.groupby("NR_VOTAVEL")["QT_VOTOS"].sum().sort_values(ascending=False).head(6)
    log(f"  {ano} turno {turno}, números mais votados: { {int(k): int(v) for k, v in top.items()} }")
    for numero, _ in PARES[ano][turno]:
        if numero not in set(top.head(4).index.astype(int)):
            raise RuntimeError(f"{ano} turno {turno}: urna {numero} não está entre os quatro mais votados. Top {top.to_dict()}")


def tabela_turno(votos: pd.DataFrame, ano: int, turno: int, cross: pd.DataFrame) -> pd.DataFrame:
    d = votos[votos["NR_TURNO"] == turno].copy()
    if d.empty:
        return pd.DataFrame()
    chave = ["SG_UF", "CD_MUNICIPIO"]
    nomes = d.groupby(chave, as_index=False)["NM_MUNICIPIO"].first()
    base = nomes.rename(columns={"SG_UF": "sg_uf", "CD_MUNICIPIO": "cd_municipio_tse", "NM_MUNICIPIO": "nm_municipio"})
    d = d.rename(columns={"SG_UF": "sg_uf", "CD_MUNICIPIO": "cd_municipio_tse"})
    chave_n = ["sg_uf", "cd_municipio_tse"]
    branco = d.loc[d["NR_VOTAVEL"] == 95].groupby(chave_n)["QT_VOTOS"].sum()
    nulo = d.loc[d["NR_VOTAVEL"] == 96].groupby(chave_n)["QT_VOTOS"].sum()
    val = d.loc[~d["NR_VOTAVEL"].isin([95, 96])].copy()
    validos = val.groupby(chave_n)["QT_VOTOS"].sum()
    comparecimento = d.groupby(chave_n)["QT_VOTOS"].sum()
    maximo = val.groupby(chave_n)["QT_VOTOS"].transform("max")
    lideres = val.loc[val["QT_VOTOS"] == maximo]
    n_lideres = lideres.groupby(chave_n).size()
    um = lideres.drop_duplicates(chave_n)
    base = base.merge(um[chave_n + ["NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]], on=chave_n, how="left")
    base = base.rename(columns={"NR_VOTAVEL": "nr_vencedor", "NM_VOTAVEL": "vencedor", "QT_VOTOS": "votos_vencedor"})
    base = base.merge(n_lideres.rename("n_lideres"), on=chave_n, how="left")
    empate = base["n_lideres"] > 1
    base.loc[empate, ["nr_vencedor", "vencedor", "votos_vencedor"]] = [pd.NA, "EMPATE", pd.NA]
    base["votos_brancos"] = base.set_index(chave_n).index.map(branco).fillna(0).astype("int64")
    # map via merge is clearer
    base = base.drop(columns=["votos_brancos"])
    base = base.merge(branco.rename("votos_brancos"), on=chave_n, how="left")
    base = base.merge(nulo.rename("votos_nulos"), on=chave_n, how="left")
    base = base.merge(validos.rename("votos_validos"), on=chave_n, how="left")
    base = base.merge(comparecimento.rename("comparecimento"), on=chave_n, how="left")
    for numero, apelido in PARES[ano][turno]:
        pedaco = val.loc[val["NR_VOTAVEL"] == numero, chave_n + ["QT_VOTOS", "NM_VOTAVEL"]]
        pedaco = pedaco.rename(columns={"QT_VOTOS": f"votos_{apelido}", "NM_VOTAVEL": f"nome_{apelido}"})
        base = base.merge(pedaco, on=chave_n, how="left")
        base[f"votos_{apelido}"] = base[f"votos_{apelido}"].fillna(0)
        base[f"pct_{apelido}"] = np.where(base["votos_validos"] > 0, 100 * base[f"votos_{apelido}"] / base["votos_validos"], np.nan)
    a, b = PARES[ano][turno]
    base["diferenca_pp"] = (base[f"pct_{a[1]}"] - base[f"pct_{b[1]}"]).abs()
    base["vencedor_par"] = np.where(
        base[f"votos_{a[1]}"] > base[f"votos_{b[1]}"], base[f"nome_{a[1]}"],
        np.where(base[f"votos_{b[1]}"] > base[f"votos_{a[1]}"], base[f"nome_{b[1]}"], "EMPATE"),
    )
    base["ano"] = ano
    base["turno"] = turno
    base["votos_brancos"] = base["votos_brancos"].fillna(0)
    base["votos_nulos"] = base["votos_nulos"].fillna(0)
    base = base.merge(cross[["sg_uf", "cd_municipio_tse", "cd_ibge", "nm_municipio_tse"]], on=chave_n, how="left")
    tem_nome = base["nm_municipio_tse"].notna()
    base.loc[tem_nome, "nm_municipio"] = base.loc[tem_nome, "nm_municipio_tse"]
    base = base.drop(columns=["nm_municipio_tse", "n_lideres"])
    return base


def carregar_cross(s: requests.Session) -> pd.DataFrame:
    destino = RAW / "mun-e006258-cm.json"
    if not destino.exists():
        url = f"{TSE}/config/mun-e006258-cm.json"
        log(f"Baixando códigos de município {url}")
        resposta = s.get(url, timeout=60)
        resposta.raise_for_status()
        destino.write_bytes(resposta.content)
    dados = json.loads(destino.read_text(encoding="utf-8"))
    linhas = []
    for uf in dados["abr"]:
        for mu in uf["mu"]:
            linhas.append({
                "sg_uf": str(uf["cd"]).upper(),
                "cd_municipio_tse": str(mu["cd"]).zfill(5),
                "cd_ibge": str(mu["cdi"]).zfill(7),
                "nm_municipio_tse": mu["nm"],
            })
    cross = pd.DataFrame(linhas).drop_duplicates(["sg_uf", "cd_municipio_tse"])
    n_zz = int((cross["sg_uf"] == "ZZ").sum())
    cross = cross[cross["sg_uf"] != "ZZ"].copy()
    log(f"De-para TSE→IBGE: {len(cross)} municípios. {n_zz} localidades do exterior (ZZ) ficaram de fora do parquet municipal.")
    NOTAS.append(
        f"De-para TSE→IBGE: {n_zz} localidades do exterior (ZZ) saíram da base municipal. "
        "O voto delas segue só no relatório, somado a partir da seção."
    )
    return cross


def parse_candidato_json(dados: dict) -> dict[int, dict]:
    achados = {}
    for cargo in dados.get("carg") or []:
        if str(cargo.get("cd")) != "1":
            continue
        for agr in cargo.get("agr") or []:
            for par in agr.get("par") or []:
                for cand in par.get("cand") or []:
                    achados[int(cand["n"])] = {
                        "nome": cand.get("nmu") or cand.get("nm"),
                        "votos": int(str(cand.get("vap") or "0").replace(".", "")),
                        "partido": par.get("sg"),
                    }
    return achados


def atualizar_segundo_turno(cross: pd.DataFrame, forcar_municipios: bool = False) -> tuple[pd.DataFrame, dict]:
    """Lê o JSON oficial do 2º turno. Município a município só se a totalização começou."""
    s = sessao()
    url_br = f"{TSE}/dados/br/br-c0001-e{ELE}-u.json"
    resposta = s.get(url_br, timeout=60)
    resposta.raise_for_status()
    vivo = RAW / "tse_live"
    vivo.mkdir(parents=True, exist_ok=True)
    (vivo / "br-c0001-e006258-u.json").write_bytes(resposta.content)
    dados = resposta.json()
    secoes = dados.get("s") or {}
    votos = dados.get("v") or {}
    st = int(secoes.get("st") or 0)
    meta = {
        "url": url_br,
        "dg": dados.get("dg"),
        "hg": dados.get("hg"),
        "tf": dados.get("tf"),
        "and": dados.get("and"),
        "secoes_totalizadas": st,
        "secoes_totais": int(secoes.get("ts") or 0),
        "pct_secoes": num_br(secoes.get("pst")),
        "votos_validos_br": int(votos.get("vv") or 0),
        "apuracao_completa": str(dados.get("tf")) == "s" or (num_br(secoes.get("pst")) or 0) >= 100,
    }
    ESTADO["segundo_turno_meta"] = meta
    log(f"2º turno nacional: {meta['dg']} {meta['hg']}, seções {st}/{meta['secoes_totais']} ({meta['pct_secoes']}%), tf={meta['tf']}")
    if st == 0 and not forcar_municipios:
        NOTAS.append(
            "2º turno: o arquivo nacional br-c0001-e006258-u.json está com zero seções totalizadas. "
            "Os votos municipais ficaram nulos. Não houve uma requisição por município, porque o total nacional zero implica que nenhuma seção entrou. "
            "Rode de novo com --refresh-2t quando a totalização começar."
        )
        vazio = cross[["sg_uf", "cd_municipio_tse", "cd_ibge", "nm_municipio_tse"]].rename(columns={"nm_municipio_tse": "nm_municipio"}).copy()
        vazio["ano"] = 2026
        vazio["turno"] = 2
        for col in ("votos_lula", "votos_flavio", "votos_validos", "votos_brancos", "votos_nulos", "comparecimento",
                    "pct_lula", "pct_flavio", "diferenca_pp", "nr_vencedor"):
            vazio[col] = pd.NA
        vazio["nome_lula"] = "LULA"
        vazio["nome_flavio"] = "FLAVIO BOLSONARO"
        vazio["vencedor"] = pd.NA
        vazio["vencedor_par"] = pd.NA
        vazio["pct_secoes_apuradas"] = 0.0
        vazio["apuracao_completa"] = False
        vazio["dh_arquivo_tse"] = f"{meta['dg']} {meta['hg']}"
        vazio["fonte"] = url_br
        return vazio, meta

    linhas = []
    falhas = []
    municipios = cross.to_dict("records")
    for i, mu in enumerate(municipios, start=1):
        uf = mu["sg_uf"].lower()
        cd = mu["cd_municipio_tse"]
        url = f"{TSE}/dados/{uf}/{uf}{cd}-c0001-e{ELE}-u.json"
        conteudo = None
        for tentativa in range(3):
            try:
                r = s.get(url, timeout=30)
                if r.status_code == 200:
                    conteudo = r.json()
                    break
            except requests.RequestException:
                time.sleep(1 + tentativa)
        if conteudo is None:
            falhas.append(cd)
        else:
            cands = parse_candidato_json(conteudo)
            sec = conteudo.get("s") or {}
            vv = conteudo.get("v") or {}
            st_mu = int(sec.get("st") or 0)
            linha = {
                "sg_uf": mu["sg_uf"], "cd_municipio_tse": cd, "cd_ibge": mu["cd_ibge"],
                "nm_municipio": mu["nm_municipio_tse"], "ano": 2026, "turno": 2,
                "pct_secoes_apuradas": num_br(sec.get("pst")),
                "apuracao_completa": str(conteudo.get("tf")) == "s",
                "dh_arquivo_tse": f"{conteudo.get('dg')} {conteudo.get('hg')}",
                "fonte": url,
            }
            if st_mu == 0:
                for col in ("votos_lula", "votos_flavio", "votos_validos", "votos_brancos", "votos_nulos", "comparecimento",
                            "pct_lula", "pct_flavio", "diferenca_pp"):
                    linha[col] = pd.NA
                linha["vencedor"] = pd.NA
                linha["vencedor_par"] = pd.NA
                linha["nr_vencedor"] = pd.NA
            else:
                linha["votos_lula"] = cands.get(13, {}).get("votos", 0)
                linha["votos_flavio"] = cands.get(22, {}).get("votos", 0)
                linha["nome_lula"] = cands.get(13, {}).get("nome", "LULA")
                linha["nome_flavio"] = cands.get(22, {}).get("nome", "FLAVIO BOLSONARO")
                linha["votos_validos"] = int(vv.get("vv") or 0)
                linha["votos_brancos"] = int(vv.get("vb") or 0)
                linha["votos_nulos"] = int(vv.get("vn") or 0)
                linha["comparecimento"] = int(vv.get("tv") or 0)
                if linha["votos_validos"]:
                    linha["pct_lula"] = 100 * linha["votos_lula"] / linha["votos_validos"]
                    linha["pct_flavio"] = 100 * linha["votos_flavio"] / linha["votos_validos"]
                else:
                    linha["pct_lula"] = pd.NA
                    linha["pct_flavio"] = pd.NA
                if linha["votos_lula"] == linha["votos_flavio"]:
                    linha["vencedor_par"] = "EMPATE"
                    linha["nr_vencedor"] = pd.NA
                elif linha["votos_lula"] > linha["votos_flavio"]:
                    linha["vencedor_par"] = linha["nome_lula"]
                    linha["nr_vencedor"] = 13
                else:
                    linha["vencedor_par"] = linha["nome_flavio"]
                    linha["nr_vencedor"] = 22
                linha["vencedor"] = linha["vencedor_par"]
                linha["diferenca_pp"] = abs((linha["pct_lula"] or 0) - (linha["pct_flavio"] or 0)) if linha["votos_validos"] else pd.NA
            linhas.append(linha)
        if i % 200 == 0:
            log(f"  2º turno: {i}/{len(municipios)} municípios")
        time.sleep(0.12)  # cerca de 8 req/s, abaixo do teto de 100/s do TSE
    if falhas:
        NOTAS.append(f"2º turno: {len(falhas)} municípios sem JSON depois de 3 tentativas. Códigos TSE (amostra): {falhas[:15]}")
    return pd.DataFrame(linhas), meta


def acrescentar_deltas(turno2: pd.DataFrame, t1: pd.DataFrame, t2022: pd.DataFrame) -> pd.DataFrame:
    a = t1.loc[t1["turno"] == 1, ["sg_uf", "cd_municipio_tse", "pct_lula", "pct_flavio"]].rename(
        columns={"pct_lula": "pct_lula_1t", "pct_flavio": "pct_flavio_1t"})
    b = t2022.loc[t2022["turno"] == 2, ["sg_uf", "cd_municipio_tse", "pct_lula", "pct_bolsonaro"]].rename(
        columns={"pct_lula": "pct_lula_2022_2t", "pct_bolsonaro": "pct_bolsonaro_2022_2t"})
    saida = turno2.merge(a, on=["sg_uf", "cd_municipio_tse"], how="left").merge(b, on=["sg_uf", "cd_municipio_tse"], how="left")
    saida["delta_lula_pp_vs_1t"] = saida["pct_lula"] - saida["pct_lula_1t"]
    saida["delta_flavio_pp_vs_1t"] = saida["pct_flavio"] - saida["pct_flavio_1t"]
    saida["delta_lula_pp_vs_2022_2t"] = saida["pct_lula"] - saida["pct_lula_2022_2t"]
    # Candidato 22: Flávio em 2026, Bolsonaro em 2022. A comparação é da fatia, não da mesma pessoa.
    saida["delta_22_pp_vs_2022_2t"] = saida["pct_flavio"] - saida["pct_bolsonaro_2022_2t"]
    return saida


def pipeline_presidente() -> None:
    s = sessao()
    cross = carregar_cross(s)
    cross.to_parquet(DATA / "crosswalk_municipio_tse_ibge.parquet", index=False)
    quadros = {}
    exterior = {}
    for ano, arquivo in ((2018, "votacao_secao_2018_BR.zip"), (2022, "votacao_secao_2022_BR.zip"), (2026, "votacao_secao_2026_BR.zip")):
        votos, ext = agregar_secao(garantir(arquivo), ano)
        exterior[ano] = ext
        for turno in (1, 2):
            if turno not in set(votos["NR_TURNO"].dropna().astype(int)):
                log(f"{ano}: turno {turno} não está no arquivo de seção.")
                continue
            conferir_numeros(votos, ano, turno)
            quadros[(ano, turno)] = tabela_turno(votos, ano, turno, cross)
            log(f"{ano} turno {turno}: {len(quadros[(ano, turno)])} municípios, válidos {int(quadros[(ano, turno)]['votos_validos'].sum())}")
        if len(ext):
            item = {}
            for turno, pedaco in ext.groupby("NR_TURNO"):
                top = pedaco.groupby("NR_VOTAVEL")["QT_VOTOS"].sum().sort_values(ascending=False).head(4)
                item[str(int(turno))] = {
                    "votos": int(pedaco["QT_VOTOS"].sum()),
                    "topo": {str(int(k)): int(v) for k, v in top.items()},
                }
            ESTADO.setdefault("exterior_resumo", {})[str(ano)] = item
        else:
            ESTADO.setdefault("exterior_resumo", {})[str(ano)] = None

    t2026_1 = quadros[(2026, 1)]
    t2022 = pd.concat([quadros[(2022, 1)], quadros[(2022, 2)]], ignore_index=True)
    t2018 = pd.concat([quadros[(2018, t)] for t in (1, 2) if (2018, t) in quadros], ignore_index=True)
    publicar(t2026_1, DATA / "presidente_municipio_2026_1t.parquet", "presidente 2026 1º turno")
    publicar(t2022, DATA / "presidente_municipio_2022.parquet", "presidente 2022")
    publicar(t2018, DATA / "presidente_municipio_2018.parquet", "presidente 2018")

    if (2026, 2) in quadros and quadros[(2026, 2)]["votos_validos"].sum() > 0:
        NOTAS.append("2º turno de 2026 já estava na votação por seção dos dados abertos; esse arquivo foi usado no lugar do JSON ao vivo.")
        t2 = quadros[(2026, 2)]
        t2["pct_secoes_apuradas"] = pd.NA
        t2["apuracao_completa"] = True
        t2["fonte"] = "votacao_secao_2026"
        t2["dh_arquivo_tse"] = pd.NA
    else:
        t2, _ = atualizar_segundo_turno(cross, forcar_municipios=ESTADO.get("refresh_2t", False) and False)
        # forcar_municipios fica falso de propósito quando st==0: --refresh-2t só baixa
        # municípios se o arquivo nacional já tiver seção totalizada. Ver atualizar_segundo_turno.
        if ESTADO.get("refresh_2t"):
            meta = ESTADO.get("segundo_turno_meta") or {}
            if meta.get("secoes_totalizadas", 0) > 0:
                t2, _ = atualizar_segundo_turno(cross, forcar_municipios=True)
    t2 = acrescentar_deltas(t2, t2026_1, t2022)
    publicar(t2, DATA / "presidente_municipio_2026_2t.parquet", "presidente 2026 2º turno")

    comparativo = montar_comparativo(t2026_1, t2, t2022, t2018)
    publicar(comparativo, DATA / "presidente_municipio_comparativo.parquet", "comparativo municipal")
    ESTADO["n_mun"] = {
        "2026_1t": int(t2026_1["cd_municipio_tse"].nunique()),
        "2022": int(t2022.loc[t2022.turno == 2, "cd_municipio_tse"].nunique()),
        "2018": int(t2018.loc[t2018.turno == 2, "cd_municipio_tse"].nunique()) if len(t2018) else 0,
        "cross": int(len(cross)),
        "ibge_2026_1t": int(t2026_1["cd_ibge"].notna().sum()),
    }
    ch26 = set(zip(t2026_1["sg_uf"], t2026_1["cd_municipio_tse"]))
    base22 = t2022.loc[t2022["turno"] == 1]
    ch22 = set(zip(base22["sg_uf"], base22["cd_municipio_tse"]))
    so_2026 = ch26 - ch22
    if so_2026:
        nomes = t2026_1[t2026_1.apply(lambda r: (r["sg_uf"], r["cd_municipio_tse"]) in so_2026, axis=1)]
        lista = ", ".join(f"{r.nm_municipio} ({r.sg_uf}, TSE {r.cd_municipio_tse}, IBGE {r.cd_ibge})" for r in nomes.itertuples())
        NOTAS.append(
            f"2026 tem {len(ch26)} municípios com voto e 2022 tem {len(ch22)}. "
            f"Só em 2026: {lista}. Na malha baixada, Boa Esperança do Norte entrou. Os polígonos sem voto são as lagoas dos Patos e Mirim, no Rio Grande do Sul."
        )
    ESTADO["totais_presidente"] = {
        "2026_1t_lula": int(t2026_1["votos_lula"].sum()),
        "2026_1t_flavio": int(t2026_1["votos_flavio"].sum()),
        "2026_1t_validos": int(t2026_1["votos_validos"].sum()),
        "2022_2t_lula": int(t2022.loc[t2022.turno == 2, "votos_lula"].sum()),
        "2022_2t_bolsonaro": int(t2022.loc[t2022.turno == 2, "votos_bolsonaro"].sum()),
        "2018_2t_haddad": int(t2018.loc[t2018.turno == 2, "votos_haddad"].sum()) if len(t2018) else None,
        "2018_2t_bolsonaro": int(t2018.loc[t2018.turno == 2, "votos_bolsonaro"].sum()) if len(t2018) else None,
    }


def montar_comparativo(t1, t2, t2022, t2018) -> pd.DataFrame:
    def recorte(df, turno, mapa):
        d = df[df["turno"] == turno] if "turno" in df.columns else df
        cols = ["sg_uf", "cd_municipio_tse", "nm_municipio", "cd_ibge"]
        for origem, destino in mapa.items():
            if origem in d.columns:
                cols.append(origem)
        saida = d[cols].copy()
        return saida.rename(columns=mapa)

    partes = [
        recorte(t1, 1, {"votos_lula": "votos_lula_2026_1t", "votos_flavio": "votos_flavio_2026_1t",
                        "votos_validos": "validos_2026_1t", "pct_lula": "pct_lula_2026_1t",
                        "pct_flavio": "pct_flavio_2026_1t", "vencedor": "vencedor_2026_1t",
                        "vencedor_par": "vencedor_par_2026_1t"}),
    ]
    base = partes[0]
    outros = [
        (t2, 2, {"votos_lula": "votos_lula_2026_2t", "votos_flavio": "votos_flavio_2026_2t",
                 "votos_validos": "validos_2026_2t", "pct_lula": "pct_lula_2026_2t",
                 "pct_flavio": "pct_flavio_2026_2t", "vencedor_par": "vencedor_2026_2t",
                 "diferenca_pp": "diferenca_pp_2026_2t", "pct_secoes_apuradas": "pct_secoes_2026_2t",
                 "delta_lula_pp_vs_1t": "delta_lula_pp_vs_1t", "delta_flavio_pp_vs_1t": "delta_flavio_pp_vs_1t",
                 "delta_lula_pp_vs_2022_2t": "delta_lula_pp_vs_2022_2t", "delta_22_pp_vs_2022_2t": "delta_22_pp_vs_2022_2t"}),
        (t2022, 2, {"votos_lula": "votos_lula_2022_2t", "votos_bolsonaro": "votos_bolsonaro_2022_2t",
                    "pct_lula": "pct_lula_2022_2t", "pct_bolsonaro": "pct_bolsonaro_2022_2t",
                    "vencedor_par": "vencedor_2022_2t", "votos_validos": "validos_2022_2t"}),
        (t2018, 2, {"votos_haddad": "votos_haddad_2018_2t", "votos_bolsonaro": "votos_bolsonaro_2018_2t",
                    "pct_haddad": "pct_haddad_2018_2t", "pct_bolsonaro": "pct_bolsonaro_2018_2t",
                    "vencedor_par": "vencedor_2018_2t", "votos_validos": "validos_2018_2t"}),
    ]
    for df, turno, mapa in outros:
        pedaco = recorte(df, turno, mapa)
        pedaco = pedaco.drop(columns=[c for c in ("nm_municipio", "cd_ibge") if c in pedaco.columns])
        base = base.merge(pedaco, on=["sg_uf", "cd_municipio_tse"], how="outer")
    return base


# ------------------------------------------------------------------- deputado federal
def ler_cand(ano: int, colunas: list[str]) -> pd.DataFrame:
    z, nomes = csvs_zip(garantir(f"consulta_cand_{ano}.zip"))
    partes = []
    for nome in nomes:
        if "BRASIL" in nome.upper():
            continue
        df = pd.read_csv(z.open(nome), sep=";", encoding="latin1", usecols=lambda c: c in colunas, dtype=str, low_memory=False)
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


def chave_titulo(serie: pd.Series) -> pd.Series:
    dig = serie.fillna("").astype(str).str.replace(r"\D", "", regex=True)
    dig = dig.where(~dig.str.fullmatch(r"0*"), other=pd.NA)
    return dig.str.lstrip("0")


def pipeline_deputado() -> None:
    colunas = [
        "SG_UF", "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "NM_CANDIDATO",
        "NR_PARTIDO", "SG_PARTIDO", "NM_PARTIDO", "SG_FEDERACAO", "DS_SITUACAO_CANDIDATURA", "DS_GENERO",
        "DS_GRAU_INSTRUCAO", "DS_ESTADO_CIVIL", "DS_COR_RACA", "DS_OCUPACAO", "DT_NASCIMENTO",
        "NR_TITULO_ELEITORAL_CANDIDATO", "DS_SIT_TOT_TURNO", "CD_SIT_TOT_TURNO",
    ]
    cand = ler_cand(2026, colunas)
    cand["CD_CARGO"] = pd.to_numeric(cand["CD_CARGO"], errors="coerce")
    cand["SG_UF"] = cand["SG_UF"].str.upper()
    cargos = cand["DS_CARGO"].value_counts().head(12)
    log(f"Cargos em consulta_cand_2026 (topo):\n{cargos.to_string()}")
    df = cand[(cand["CD_CARGO"] == 6) & (cand["SG_UF"] != "ZZ")].copy()
    df["situacao_norm"] = df["DS_SITUACAO_CANDIDATURA"].map(sem_acento)
    log(f"Situação no consulta_cand, deputado federal:\n{df['situacao_norm'].value_counts().to_string()}")
    df = df.drop_duplicates("SQ_CANDIDATO")
    NOTAS.append(
        "consulta_cand_2026 publica DS_SITUACAO_CANDIDATURA = #NE e código -3 para todos os deputados federais. "
        "O filtro usa DS_SITUACAO_JULGAMENTO da votação por município e zona. "
        "Entra o texto que começa com DEFERIDO, o que cobre deferido e deferido com recurso. "
        "Indeferido, inclusive em prazo recursal, fica de fora."
    )

    votos = ler_votos_nominais()
    df = df.merge(votos, on="SQ_CANDIDATO", how="left", suffixes=("", "_voto"))
    df["julgamento_norm"] = df["DS_SITUACAO_JULGAMENTO"].map(sem_acento)
    log(f"Julgamento na votação nominal:\n{df['julgamento_norm'].value_counts(dropna=False).to_string()}")
    sem_julg = df["julgamento_norm"].isna() | df["julgamento_norm"].isin(["", "#NE", "#NULO#", "NAN", "NONE"])
    sit_bruto = df["DS_SIT_TOT_TURNO_voto"].fillna("").map(sem_acento)
    eleito_fora = sit_bruto.str.startswith("ELEITO", na=False) & ~df["julgamento_norm"].str.startswith("DEFERIDO", na=False)
    if eleito_fora.any():
        fora = df.loc[eleito_fora, ["SG_UF", "NM_URNA_CANDIDATO", "SG_PARTIDO", "DS_SITUACAO_JULGAMENTO", "DS_SIT_TOT_TURNO_voto"]]
        lista = "; ".join(
            f"{r.NM_URNA_CANDIDATO} ({r.SG_UF}, {r.SG_PARTIDO}, {r.DS_SIT_TOT_TURNO_voto}, julgamento {r.DS_SITUACAO_JULGAMENTO})"
            for r in fora.itertuples()
        )
        NOTAS.append(
            f"Deputado: {int(eleito_fora.sum())} candidatura com situação de eleito e julgamento que não começa com DEFERIDO ficou de fora da base: {lista}."
        )
    antes = len(df)
    df = df[df["julgamento_norm"].str.startswith("DEFERIDO", na=False)].copy()
    NOTAS.append(
        f"Deputado: {antes} candidaturas no consulta_cand, fora ZZ. "
        f"{int(sem_julg.sum())} sem julgamento na votação nominal. "
        f"{len(df)} permaneceram porque o julgamento começa com DEFERIDO."
    )

    nasc = pd.to_datetime(df["DT_NASCIMENTO"], dayfirst=True, errors="coerce")
    idade = (pd.Timestamp("2026-10-04") - nasc).dt.days / 365.25
    fora_idade = idade.notna() & ((idade < 18) | (idade > 100))
    if fora_idade.any():
        NOTAS.append(f"Deputado: {int(fora_idade.sum())} idades fora de 18–100 na data do 1º turno (04/10/2026); viraram nulo. O arquivo de 2026 não traz NR_IDADE_DATA_POSSE.")
    df["idade_na_eleicao"] = idade.where(~fora_idade)
    df["titulo"] = chave_titulo(df["NR_TITULO_ELEITORAL_CANDIDATO"])
    NOTAS.append(f"Deputado: {int(df['titulo'].isna().sum())} deferidos sem título eleitoral; experiencia_previa ficou nula nesses casos.")

    vistos = set()
    for ano in (2018, 2020, 2022, 2024):
        antigo = ler_cand(ano, ["NR_TITULO_ELEITORAL_CANDIDATO"])
        vistos.update(chave_titulo(antigo["NR_TITULO_ELEITORAL_CANDIDATO"]).dropna().unique())
        log(f"  títulos únicos acumulados até {ano}: {len(vistos)}")
    df["experiencia_previa"] = df["titulo"].map(lambda t: pd.NA if pd.isna(t) else int(t in vistos))

    sem_voto = df["votos_nominais"].isna()
    if sem_voto.any():
        NOTAS.append(f"Deputado: {int(sem_voto.sum())} deferidos sem linha na votação nominal; votos_nominais = 0.")
        df.loc[sem_voto, "votos_nominais"] = 0
    negativo = df["votos_nominais"] < 0
    if negativo.any():
        NOTAS.append(f"Deputado: {int(negativo.sum())} votos nominais negativos; viraram nulo.")
        df.loc[negativo, "votos_nominais"] = pd.NA
    df["log_votos"] = np.log1p(df["votos_nominais"])

    sit = df["DS_SIT_TOT_TURNO_voto"].fillna(df["DS_SIT_TOT_TURNO"]).map(sem_acento)
    vazio = sit.isin(["", "#NULO#", "NULO", "NAN", "NONE"]) | sit.isna()
    if vazio.all():
        df["eleito"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
        NOTAS.append("Deputado: DS_SIT_TOT_TURNO ainda não classifica eleitos. A coluna eleito ficou nula, não falsa.")
    else:
        eleito = sit.str.startswith("ELEITO", na=False).astype("boolean")
        eleito.loc[vazio] = pd.NA
        df["eleito"] = eleito
        log(f"Situação final (topo):\n{sit.value_counts().head(12).to_string()}")

    qe = quociente_eleitoral()
    df = df.merge(qe, left_on="SG_UF", right_on="sg_uf", how="left")
    superou = (df["votos_nominais"] >= df["quociente_eleitoral"]).astype("boolean")
    superou.loc[df["quociente_eleitoral"].isna() | df["votos_nominais"].isna()] = pd.NA
    df["superou_quociente"] = superou

    pres = votos_presidente_por_partido()
    df["nr_partido_num"] = pd.to_numeric(df["NR_PARTIDO"], errors="coerce")
    df = df.merge(pres, left_on=["SG_UF", "nr_partido_num"], right_on=["sg_uf_pres", "nr_partido"], how="left", suffixes=("", "_pres"))
    df["votos_presidente_partido_uf"] = df["votos_presidente_partido_uf"].fillna(0)
    NOTAS.append("votos_presidente_partido_uf é o voto do candidato a presidente do mesmo número de partido na UF, no 1º turno de 2026. Partido sem candidato a presidente fica 0. Não usa a federação.")

    df["n_candidatos_partido_uf"] = df.groupby(["SG_UF", "SG_PARTIDO"])["SQ_CANDIDATO"].transform("size")
    dummies = pd.get_dummies(df["SG_UF"], prefix="uf", dtype="int8")
    df = pd.concat([df, dummies], axis=1)

    saida = pd.DataFrame({
        "sq_candidato": df["SQ_CANDIDATO"],
        "nr_candidato": pd.to_numeric(df["NR_CANDIDATO"], errors="coerce"),
        "nm_urna": df["NM_URNA_CANDIDATO"],
        "nm_candidato": df["NM_CANDIDATO"],
        "sg_uf": df["SG_UF"],
        "nr_partido": df["nr_partido_num"],
        "sg_partido": df["SG_PARTIDO"],
        "nm_partido": df["NM_PARTIDO"],
        "sg_federacao": df["SG_FEDERACAO"],
        "ds_situacao_candidatura": df["DS_SITUACAO_JULGAMENTO"],
        "votos_nominais": df["votos_nominais"],
        "log_votos": df["log_votos"],
        "eleito": df["eleito"],
        "superou_quociente": df["superou_quociente"],
        "quociente_eleitoral": df["quociente_eleitoral"],
        "votos_validos_uf": df["votos_validos_uf"],
        "cadeiras_uf": df["cadeiras_uf"],
        "experiencia_previa": df["experiencia_previa"],
        "votos_presidente_partido_uf": df["votos_presidente_partido_uf"],
        "n_candidatos_partido_uf": df["n_candidatos_partido_uf"],
        "ds_genero": df["DS_GENERO"],
        "idade_na_eleicao": df["idade_na_eleicao"],
        "ds_grau_instrucao": df["DS_GRAU_INSTRUCAO"],
        "ds_estado_civil": df["DS_ESTADO_CIVIL"],
        "ds_cor_raca": df["DS_COR_RACA"],
        "ds_ocupacao": df["DS_OCUPACAO"],
    })
    saida = pd.concat([saida, dummies.reset_index(drop=True)], axis=1)
    extremos = saida["votos_nominais"].dropna()
    if len(extremos) and (extremos > 5_000_000).any():
        NOTAS.append(f"Deputado: {(extremos > 5_000_000).sum()} candidaturas com mais de 5 milhões de votos nominais. Mantidas; não houve winsorização.")
    ESTADO["deputado"] = {
        "linhas": int(len(saida)),
        "eleitos_preenchidos": None if saida["eleito"].isna().all() else int(saida["eleito"].fillna(False).sum()),
        "eleito_nulo": int(saida["eleito"].isna().sum()),
        "votos_zero": int((saida["votos_nominais"] == 0).sum()),
        "experiencia": None if saida["experiencia_previa"].dropna().empty else float(saida["experiencia_previa"].mean(skipna=True)),
        "soma_votos": None if saida["votos_nominais"].isna().all() else int(saida["votos_nominais"].sum()),
    }
    if saida["eleito"].notna().any():
        n_eleitos = int(saida["eleito"].fillna(False).sum())
        ESTADO["deputado"]["eleitos_preenchidos"] = n_eleitos
        if n_eleitos != 513:
            NOTAS.append(
                f"Deputado: {n_eleitos} candidaturas com situação começando em ELEITO. "
                "A Câmara tem 513 cadeiras. O número do arquivo foi mantido, sem ajuste."
            )
    publicar(saida, DATA / "candidatos_df.parquet", "deputado federal 2026")


def ler_votos_nominais() -> pd.DataFrame:
    z, nomes = csvs_zip(garantir("votacao_candidato_munzona_2026.zip"))
    partes = []
    cols = ["SQ_CANDIDATO", "SG_UF", "CD_CARGO", "NR_TURNO", "QT_VOTOS_NOMINAIS", "QT_VOTOS_NOMINAIS_VALIDOS", "DS_SIT_TOT_TURNO", "DS_SITUACAO_JULGAMENTO"]
    for nome in nomes:
        if "BRASIL" in nome.upper():
            continue
        df = pd.read_csv(
            z.open(nome), sep=";", encoding="latin1", usecols=cols,
            dtype={"SQ_CANDIDATO": str, "SG_UF": str, "DS_SIT_TOT_TURNO": str, "DS_SITUACAO_JULGAMENTO": str},
        )
        df["CD_CARGO"] = pd.to_numeric(df["CD_CARGO"], errors="coerce")
        df["NR_TURNO"] = pd.to_numeric(df["NR_TURNO"], errors="coerce")
        df = df[(df["CD_CARGO"] == 6) & (df["NR_TURNO"] == 1) & (df["SG_UF"].str.upper() != "ZZ")]
        if df.empty:
            continue
        df["QT_VOTOS_NOMINAIS_VALIDOS"] = pd.to_numeric(df["QT_VOTOS_NOMINAIS_VALIDOS"], errors="coerce")
        g = df.groupby("SQ_CANDIDATO", as_index=False).agg(
            votos_nominais=("QT_VOTOS_NOMINAIS_VALIDOS", "sum"),
            DS_SIT_TOT_TURNO_voto=("DS_SIT_TOT_TURNO", "first"),
            DS_SITUACAO_JULGAMENTO=("DS_SITUACAO_JULGAMENTO", "first"),
        )
        partes.append(g)
    votos = pd.concat(partes, ignore_index=True)
    votos = votos.groupby("SQ_CANDIDATO", as_index=False).agg(
        votos_nominais=("votos_nominais", "sum"),
        DS_SIT_TOT_TURNO_voto=("DS_SIT_TOT_TURNO_voto", "first"),
        DS_SITUACAO_JULGAMENTO=("DS_SITUACAO_JULGAMENTO", "first"),
    )
    log(f"Votação nominal de deputado: {len(votos)} candidaturas com pelo menos uma linha")
    return votos


def quociente_eleitoral() -> pd.DataFrame:
    z, nomes = csvs_zip(garantir("votacao_partido_munzona_2026.zip"))
    partes = []
    cols = ["SG_UF", "CD_CARGO", "NR_TURNO", "QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_LEGENDA_VALIDOS",
            "QT_VOTOS_NOM_CONVR_LEG_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS"]
    for nome in nomes:
        if "BRASIL" in nome.upper():
            continue
        df = pd.read_csv(z.open(nome), sep=";", encoding="latin1", usecols=cols)
        df["CD_CARGO"] = pd.to_numeric(df["CD_CARGO"], errors="coerce")
        df["NR_TURNO"] = pd.to_numeric(df["NR_TURNO"], errors="coerce")
        df = df[(df["CD_CARGO"] == 6) & (df["NR_TURNO"] == 1) & (df["SG_UF"].astype(str).str.upper() != "ZZ")]
        if len(df):
            partes.append(df)
    partido = pd.concat(partes, ignore_index=True)
    for col in cols[3:]:
        partido[col] = pd.to_numeric(partido[col], errors="coerce").fillna(0)
    bate = np.isclose(partido["QT_VOTOS_LEGENDA_VALIDOS"] + partido["QT_VOTOS_NOM_CONVR_LEG_VALIDOS"], partido["QT_TOTAL_VOTOS_LEG_VALIDOS"])
    log(f"Linhas em que legenda + nominais convertidos = total de legenda: {bate.mean():.3%}")
    NOTAS.append(
        "Quociente: votos válidos da UF = QT_VOTOS_NOMINAIS_VALIDOS + QT_TOTAL_VOTOS_LEG_VALIDOS, "
        f"cargo 6, turno 1. Em {bate.mean():.1%} das linhas, o total de legenda é a soma de legenda e nominais convertidos em legenda. "
        "QE = divisão inteira desses válidos pelo número de cadeiras (a fração é desprezada, como na lei)."
    )
    partido["SG_UF"] = partido["SG_UF"].astype(str).str.upper()
    validos = partido.groupby("SG_UF", as_index=False).apply(
        lambda g: pd.Series({"votos_validos_uf": g["QT_VOTOS_NOMINAIS_VALIDOS"].sum() + g["QT_TOTAL_VOTOS_LEG_VALIDOS"].sum()}),
        include_groups=False,
    ).reset_index(drop=True) if False else None
    # groupby.apply com include_groups varia entre versões do pandas. Soma direta:
    validos = partido.groupby("SG_UF", as_index=False)[["QT_VOTOS_NOMINAIS_VALIDOS", "QT_TOTAL_VOTOS_LEG_VALIDOS"]].sum()
    validos["votos_validos_uf"] = validos["QT_VOTOS_NOMINAIS_VALIDOS"] + validos["QT_TOTAL_VOTOS_LEG_VALIDOS"]
    validos = validos.rename(columns={"SG_UF": "sg_uf"})[["sg_uf", "votos_validos_uf"]]

    zv, nomes_v = csvs_zip(garantir("consulta_vagas_2026.zip"))
    vagas = []
    for nome in nomes_v:
        if "BRASIL" in nome.upper():
            continue
        df = pd.read_csv(zv.open(nome), sep=";", encoding="latin1", usecols=["SG_UF", "CD_CARGO", "QT_VAGA"], dtype=str)
        df["CD_CARGO"] = pd.to_numeric(df["CD_CARGO"], errors="coerce")
        df = df[df["CD_CARGO"] == 6]
        if len(df):
            vagas.append(df)
    vagas = pd.concat(vagas, ignore_index=True)
    vagas["QT_VAGA"] = pd.to_numeric(vagas["QT_VAGA"], errors="coerce")
    vagas["SG_UF"] = vagas["SG_UF"].str.upper()
    vagas = vagas.groupby("SG_UF", as_index=False)["QT_VAGA"].max().rename(columns={"SG_UF": "sg_uf", "QT_VAGA": "cadeiras_uf"})
    soma_cadeiras = int(vagas["cadeiras_uf"].sum())
    log(f"Cadeiras de deputado federal somadas: {soma_cadeiras}")
    if soma_cadeiras != 513:
        NOTAS.append(f"A soma de QT_VAGA de deputado federal deu {soma_cadeiras}, não 513. O quociente usa o número que está no arquivo.")
    tabela = validos.merge(vagas, on="sg_uf", how="left")
    tabela["quociente_eleitoral"] = (tabela["votos_validos_uf"] // tabela["cadeiras_uf"]).astype("Int64")
    return tabela


def votos_presidente_por_partido() -> pd.DataFrame:
    caminho = garantir("votacao_secao_2026_BR.zip")
    z, nomes = csvs_zip(caminho)
    partes = []
    cols = ["SG_UF", "NR_TURNO", "CD_CARGO", "NR_VOTAVEL", "QT_VOTOS"]
    for chunk in pd.read_csv(z.open(nomes[0]), sep=";", encoding="latin1", usecols=cols, chunksize=2_000_000, dtype={"SG_UF": str}):
        chunk["CD_CARGO"] = pd.to_numeric(chunk["CD_CARGO"], errors="coerce")
        chunk["NR_TURNO"] = pd.to_numeric(chunk["NR_TURNO"], errors="coerce")
        chunk = chunk[(chunk["CD_CARGO"] == 1) & (chunk["NR_TURNO"] == 1)]
        if chunk.empty:
            continue
        chunk["SG_UF"] = chunk["SG_UF"].str.upper()
        chunk = chunk[~chunk["SG_UF"].isin(["ZZ", "BR"])]
        chunk["NR_VOTAVEL"] = pd.to_numeric(chunk["NR_VOTAVEL"], errors="coerce")
        chunk["QT_VOTOS"] = pd.to_numeric(chunk["QT_VOTOS"], errors="coerce")
        chunk = chunk[~chunk["NR_VOTAVEL"].isin([95, 96])]
        partes.append(chunk.groupby(["SG_UF", "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum())
    votos = pd.concat(partes, ignore_index=True).groupby(["SG_UF", "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()
    # O número do candidato a presidente é o número do partido. Conferido na lista abaixo.
    log("Votos de presidente por número, Brasil (1º turno 2026):")
    log(votos.groupby("NR_VOTAVEL")["QT_VOTOS"].sum().sort_values(ascending=False).head(12).to_string())
    return votos.rename(columns={"SG_UF": "sg_uf_pres", "NR_VOTAVEL": "nr_partido", "QT_VOTOS": "votos_presidente_partido_uf"})


# ------------------------------------------------------------------------------ mapa
def lado_de(nome) -> str:
    n = sem_acento(nome)
    if n in ("", "NAN", "NONE", "<NA>"):
        return "sem_dado"
    if "EMPATE" in n:
        return "empate"
    if "LULA" in n or "HADDAD" in n:
        return "pt"
    if "FLAVIO" in n or "BOLSONARO" in n:
        return "pl"
    return "outro"


def baixar_malha() -> Path:
    destino = RAW / "malha_municipios.zip"
    if destino.exists() and destino.stat().st_size > 1_000_000:
        return destino
    s = sessao()
    for url in MALHAS:
        try:
            cabeca = s.head(url, timeout=40, allow_redirects=True)
            if cabeca.status_code != 200:
                continue
            log(f"Baixando malha {url}")
            with s.get(url, stream=True, timeout=180) as r:
                r.raise_for_status()
                with destino.open("wb") as saida:
                    for bloco in r.iter_content(1024 * 256):
                        if bloco:
                            saida.write(bloco)
            return destino
        except requests.RequestException as exc:
            NOTAS.append(f"Malha não baixada de {url}: {exc}")
    raise FileNotFoundError("Nenhuma malha municipal do IBGE respondeu.")


def pipeline_mapa() -> None:
    comparativo = pd.read_parquet(DATA / "presidente_municipio_comparativo.parquet")
    try:
        import geopandas as gpd
    except ImportError:
        NOTAS.append("GeoPandas não está instalado. O mapa HTML e o PNG não foram gerados.")
        return
    malha_zip = baixar_malha()
    gdf = gpd.read_file(malha_zip)
    log(f"Malha: {gdf.shape}, colunas {list(gdf.columns)}")
    col_cd = next(c for c in gdf.columns if c.upper() in {"CD_MUN", "CD_MUNICIP", "GEOCODIGO"})
    col_nm = next((c for c in gdf.columns if c.upper() in {"NM_MUN", "NM_MUNICIP"}), None)
    gdf["cd_ibge"] = gdf[col_cd].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    gdf["geometry"] = gdf.geometry.simplify(0.012, preserve_topology=True)
    juntar = comparativo.copy()
    juntar["cd_ibge"] = juntar["cd_ibge"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    juntar.loc[juntar["cd_ibge"].isin(["", "NAN", "NONE", "<NA>"]), "cd_ibge"] = pd.NA
    gdf = gdf.merge(juntar, on="cd_ibge", how="left")
    cobertura = int(gdf["cd_municipio_tse"].notna().sum()) if "cd_municipio_tse" in gdf.columns else 0
    NOTAS.append(f"Malha: {len(gdf)} polígonos, {cobertura} com voto municipal casado pelo código IBGE.")
    ESTADO["malha"] = {"poligonos": int(len(gdf)), "casados": cobertura}
    gdf.to_file(DATA / "malha_municipios.geojson", driver="GeoJSON")

    tem_2t = gdf["votos_lula_2026_2t"].notna().any() and gdf["votos_lula_2026_2t"].fillna(0).sum() > 0 if "votos_lula_2026_2t" in gdf.columns else False
    camadas = []
    if tem_2t:
        camadas.append(("Vencedor 2º turno 2026", "vencedor_2026_2t", True))
    camadas.append(("Lula x Flávio, 1º turno 2026", "vencedor_par_2026_1t", not tem_2t))
    camadas.append(("2º turno 2022", "vencedor_2022_2t", False))
    camadas.append(("2º turno 2018", "vencedor_2018_2t", False))

    import folium

    # CartoDB positron passou a exigir chave nesta versão do Folium. OpenStreetMap abre sem chave.
    mapa = folium.Map(location=[-14.2, -51.9], zoom_start=4, tiles="OpenStreetMap")
    NOTAS.append("Mapa: a base cartográfica é OpenStreetMap. O Folium instalado avisa que o CartoDB positron exige chave.")
    for titulo, coluna, ligado in camadas:
        if coluna not in gdf.columns:
            continue
        pedaco = gdf[["geometry", "cd_ibge", coluna, "nm_municipio", "sg_uf"]].copy()
        extras = [c for c in (
            "votos_lula_2026_2t", "votos_flavio_2026_2t", "pct_lula_2026_2t", "pct_flavio_2026_2t",
            "diferenca_pp_2026_2t", "delta_lula_pp_vs_1t", "delta_flavio_pp_vs_1t",
            "delta_lula_pp_vs_2022_2t", "delta_22_pp_vs_2022_2t", "pct_secoes_2026_2t",
            "votos_lula_2026_1t", "votos_flavio_2026_1t", "pct_lula_2026_1t", "pct_flavio_2026_1t",
        ) if c in gdf.columns]
        pedaco = gdf[["geometry", "cd_ibge", coluna, "nm_municipio", "sg_uf", *extras]].copy()
        pedaco["lado"] = pedaco[coluna].map(lado_de)
        for c in pedaco.columns:
            if c == "geometry":
                continue
            pedaco[c] = pedaco[c].apply(lambda v: "—" if pd.isna(v) else (f"{v:.1f}" if isinstance(v, float) else str(v)))

        def estilo(feat, _pedaco=pedaco):
            lado = feat["properties"].get("lado", "sem_dado")
            return {"fillColor": CORES.get(lado, CORES["sem_dado"]), "color": "#ffffff", "weight": 0.3, "fillOpacity": 0.85}

        campos = ["nm_municipio", "sg_uf", coluna, "votos_lula_2026_2t", "votos_flavio_2026_2t",
                  "pct_lula_2026_2t", "pct_flavio_2026_2t", "diferenca_pp_2026_2t",
                  "delta_lula_pp_vs_1t", "delta_flavio_pp_vs_1t", "delta_lula_pp_vs_2022_2t",
                  "delta_22_pp_vs_2022_2t", "pct_secoes_2026_2t"]
        campos = [c for c in campos if c in pedaco.columns]
        rotulos = {
            "nm_municipio": "Município", "sg_uf": "UF", coluna: "Vencedor desta camada",
            "votos_lula_2026_2t": "Votos Lula 2º turno", "votos_flavio_2026_2t": "Votos Flávio 2º turno",
            "pct_lula_2026_2t": "% Lula 2º turno", "pct_flavio_2026_2t": "% Flávio 2º turno",
            "diferenca_pp_2026_2t": "Diferença 2º turno (p.p.)",
            "delta_lula_pp_vs_1t": "Δ Lula vs 1º turno (p.p.)", "delta_flavio_pp_vs_1t": "Δ Flávio vs 1º turno (p.p.)",
            "delta_lula_pp_vs_2022_2t": "Δ Lula vs 2º turno 2022 (p.p.)",
            "delta_22_pp_vs_2022_2t": "Δ candidato 22 vs 2022 (p.p.)",
            "pct_secoes_2026_2t": "% seções apuradas",
        }
        folium.GeoJson(
            pedaco, name=titulo, show=ligado, style_function=estilo,
            tooltip=folium.GeoJsonTooltip(fields=campos, aliases=[rotulos.get(c, c) for c in campos], localize=True),
        ).add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)
    aviso = "" if tem_2t else "<br>2º turno 2026 ainda sem seção totalizada no TSE. A camada aberta é o 1º turno."
    titulo_html = (
        '<div style="position:fixed;top:12px;left:60px;z-index:9999;background:#fff;padding:8px 12px;'
        'font-family:sans-serif;font-size:14px;border:1px solid #ddd;">'
        f"<b>Presidente por município</b>{aviso}</div>"
    )
    mapa.get_root().html.add_child(folium.Element(titulo_html))
    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / "mapa_presidente_municipios.html"
    mapa.save(destino)
    log(f"Salvo {destino}")

    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
        coluna_png = "vencedor_2026_2t" if tem_2t else "vencedor_par_2026_1t"
        nome_png = "mapa_presidente_2026_2t.png" if tem_2t else "mapa_presidente_2026_1t.png"
        fig, ax = plt.subplots(figsize=(11, 10))
        gdf["_lado"] = gdf[coluna_png].map(lado_de) if coluna_png in gdf.columns else "sem_dado"
        gdf["_cor"] = gdf["_lado"].map(CORES)
        gdf.plot(color=gdf["_cor"], ax=ax, linewidth=0.05, edgecolor="white")
        ax.set_axis_off()
        ax.set_title("2º turno 2026" if tem_2t else "1º turno 2026 — Lula x Flávio (2º turno ainda sem apuração)")
        ax.legend(handles=[
            Patch(facecolor=CORES["pt"], label="Lula / Haddad"),
            Patch(facecolor=CORES["pl"], label="Flávio / Bolsonaro"),
            Patch(facecolor=CORES["empate"], label="Empate"),
            Patch(facecolor=CORES["sem_dado"], label="Sem dado"),
        ], loc="lower left", frameon=False)
        fig.tight_layout()
        fig.savefig(OUT / nome_png, dpi=140)
        plt.close(fig)
        log(f"Salvo {OUT / nome_png}")
        if not tem_2t:
            NOTAS.append("PNG do 2º turno não foi desenhado: não há voto totalizado. Foi salvo o mapa do 1º turno de 2026.")
    except Exception as exc:
        NOTAS.append(f"PNG não gerado: {exc}")


# ----------------------------------------------------------------------- documentação
def escrever_documentos() -> None:
    (DATA / "amostras_pre_save.md").write_text("# Amostras imediatamente antes de gravar os parquets\n\n" + "\n\n".join(AMOSTRAS) + "\n", encoding="utf-8")
    pred = ESTADO.get("prediction") or {}
    meta = ESTADO.get("segundo_turno_meta") or {}
    n = ESTADO.get("n_mun") or {}
    totais = ESTADO.get("totais_presidente") or {}
    dep = ESTADO.get("deputado") or {}
    malha = ESTADO.get("malha") or {}
    rel = [
        "# Relatório de qualidade — Fase 1",
        "",
        f"Gerado em {datetime.now().isoformat(timespec='seconds')}.",
        "",
        "## Prediction",
        "",
        f"- Pesquisas na média: {pred.get('n_pesquisas_na_media')}",
        f"- Flávio {pred.get('media_ponderada_flavio_pct')}% | Lula {pred.get('media_ponderada_lula_pct')}%",
        f"- P(vitória), tau 2 p.p.: Flávio {pred.get('prob_vitoria_flavio')} | Lula {pred.get('prob_vitoria_lula')}",
        f"- Excluídas: {[e['instituto'] for e in pred.get('excluidas', [])]}",
        "",
        "## Presidente",
        "",
        f"- Municípios no de-para do TSE (2º turno): {n.get('cross')}. Referência IBGE usada só como ordem de grandeza: 5.570 municípios em 2024.",
        f"- Municípios com voto em 2026 1º turno: {n.get('2026_1t')}. Com código IBGE: {n.get('ibge_2026_1t')}.",
        f"- Municípios no 2º turno de 2022: {n.get('2022')}. No 2º turno de 2018: {n.get('2018')}.",
        f"- Totais lidos nos arquivos de seção (sem exterior): {totais}",
        f"- Exterior (ZZ), soma de votos e os quatro números mais votados, por ano e turno: {ESTADO.get('exterior_resumo')}",
        f"- 2º turno ao vivo: {meta}",
        "",
        "O 1º turno de 2026, nos dados abertos, deve ficar perto de 47% para Flávio e 45% para Lula nos votos válidos. Os totais acima são a soma do arquivo, não um número recolocado.",
        "",
        "## Deputado federal",
        "",
        f"- {dep}",
        "",
        "Contexto IBGE por UF não entrou. O Censo municipal não foi baixado nesta fase; a coluna ficaria vazia e foi omitida.",
        "",
        "## Malha",
        "",
        f"- {malha}",
        "",
        "## Decisões e achados",
        "",
    ]
    rel += [f"- {n}" for n in NOTAS]
    rel += [
        "",
        "## O que este relatório não fecha",
        "",
        "- A prediction não observa urna. O tau de 2 p.p. é cenário, calibrado na literatura, não um erro histórico reestimado para 2026.",
        "- Experiência prévia usa o título eleitoral em 2018, 2020, 2022 e 2024. Título ausente ou com dígito diferente não casa.",
        "- Município criado ou com código TSE que não está no JSON de 25/10/2026 fica sem código IBGE e fora do mapa.",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "relatorio_qualidade.md").write_text("\n".join(rel) + "\n", encoding="utf-8")
    log(f"Salvo {OUT / 'relatorio_qualidade.md'}")

    dicionario = """# Dicionário de variáveis

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
"""
    (DATA / "dicionario_variaveis.md").write_text(dicionario, encoding="utf-8")
    log(f"Salvo {DATA / 'dicionario_variaveis.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline eleitoral Fase 1")
    parser.add_argument("--somente", default="all", choices=["all", "prediction", "deputado", "presidente", "mapa"])
    parser.add_argument("--refresh-2t", action="store_true", help="Reconsulta o TSE. Municípios só são baixados se o arquivo nacional já tiver seção totalizada.")
    parser.add_argument("--sem-download", action="store_true")
    args = parser.parse_args()
    ESTADO["sem_download"] = args.sem_download
    ESTADO["refresh_2t"] = args.refresh_2t
    for pasta in (DATA, RAW, OUT):
        pasta.mkdir(parents=True, exist_ok=True)

    if args.somente in ("all", "prediction"):
        grafico_prediction(calcular_prediction())
    if args.somente in ("all", "presidente"):
        pipeline_presidente()
    if args.somente in ("all", "deputado"):
        pipeline_deputado()
    if args.somente in ("all", "mapa"):
        pipeline_mapa()
    escrever_documentos()


if __name__ == "__main__":
    main()
