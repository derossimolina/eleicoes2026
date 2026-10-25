"""Exporta JSON compacto para o site em site/dados.

Lê os parquets já gravados pelo pipeline. Não recalcula pesquisa nem voto.
Rode de novo depois de um refresh do 2º turno.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "dados"


def sem_acento(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())


def lado(nome) -> str:
    n = sem_acento(nome)
    if n in ("", "NAN", "NONE", "<NA>"):
        return "sem"
    if "EMPATE" in n:
        return "empate"
    if "LULA" in n or "HADDAD" in n:
        return "pt"
    if "FLAVIO" in n or "BOLSONARO" in n:
        return "pl"
    return "outro"


def arred(valor, casas=2):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or pd.isna(valor):
        return None
    return round(float(valor), casas)


def inteiro(valor):
    if valor is None or pd.isna(valor):
        return None
    return int(valor)


def arredondar_coords(coords):
    if isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), 4), round(float(coords[1]), 4)]
    return [arredondar_coords(c) for c in coords]


def exportar_indice(t1: pd.DataFrame) -> None:
    """Lista enxuta para a página de apuração achar o código TSE do município."""
    linhas = []
    ordem = t1.sort_values(["sg_uf", "nm_municipio"])
    for r in ordem.itertuples(index=False):
        linhas.append({
            "uf": r.sg_uf,
            "cd": str(r.cd_municipio_tse).zfill(5),
            "ibge": None if pd.isna(r.cd_ibge) else str(r.cd_ibge).zfill(7),
            "nm": r.nm_municipio,
            "l": inteiro(r.votos_lula),
            "f": inteiro(r.votos_flavio),
            "v": inteiro(r.votos_validos),
        })
    destino = OUT / "municipios.json"
    destino.write_text(json.dumps(linhas, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"municipios.json {destino.stat().st_size / 1_048_576:.2f} MB ({len(linhas)})")


def exportar() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pred = json.loads((DATA / "prediction_inicial.json").read_text(encoding="utf-8"))
    (OUT / "prediction.json").write_text(json.dumps(pred, ensure_ascii=False), encoding="utf-8")

    comp = pd.read_parquet(DATA / "presidente_municipio_comparativo.parquet")
    t1 = pd.read_parquet(DATA / "presidente_municipio_2026_1t.parquet")
    dep = pd.read_parquet(DATA / "candidatos_df.parquet")

    validos = float(t1["votos_validos"].sum())
    lula = float(t1["votos_lula"].sum())
    flavio = float(t1["votos_flavio"].sum())
    por_uf = (
        t1.groupby("sg_uf", as_index=False)[["votos_lula", "votos_flavio", "votos_validos"]]
        .sum()
        .sort_values("sg_uf")
    )
    ufs = []
    for r in por_uf.itertuples(index=False):
        vv = float(r.votos_validos) or 1
        ufs.append({
            "uf": r.sg_uf,
            "lula": int(r.votos_lula),
            "flavio": int(r.votos_flavio),
            "validos": int(r.votos_validos),
            "pct_lula": round(100 * float(r.votos_lula) / vv, 2),
            "pct_flavio": round(100 * float(r.votos_flavio) / vv, 2),
        })

    eleitos = int(dep["eleito"].fillna(False).sum())
    gap = (
        dep.groupby("sg_uf")
        .agg(eleitos=("eleito", "sum"), cadeiras=("cadeiras_uf", "first"))
        .reset_index()
    )
    gap = gap[gap["eleitos"] != gap["cadeiras"]]
    nota_cadeira = None
    if len(gap) == 1 and gap.iloc[0]["sg_uf"] == "ES" and int(gap.iloc[0]["eleitos"]) == 9:
        nota_cadeira = (
            "A base tem 512 eleitos para 513 cadeiras. No Espírito Santo são 9 para 10. "
            "Lucas o Federal da Direita (PL) consta na votação como eleito por quociente partidário, "
            "com 43.973 votos nominais, mas o julgamento está pendente, então não entrou no filtro de deferidos."
        )

    partidos = (
        dep.groupby("sg_partido", as_index=False)
        .agg(candidatos=("sq_candidato", "size"), eleitos=("eleito", "sum"), votos=("votos_nominais", "sum"))
        .sort_values("votos", ascending=False)
    )
    resumo = {
        "gerado_de": "parquets da Fase 1",
        "prediction": {
            "data_referencia": pred["data_referencia"],
            "flavio_pct": pred["media_ponderada_flavio_pct"],
            "lula_pct": pred["media_ponderada_lula_pct"],
            "prob_flavio": pred["prob_vitoria_flavio"],
            "prob_lula": pred["prob_vitoria_lula"],
            "intervalo_flavio": pred["intervalo_95_flavio_tau_2pp"],
            "sensibilidade": pred["sensibilidade_prob_flavio"],
            "n_pesquisas": pred["n_pesquisas_na_media"],
            "aviso": pred["aviso"],
        },
        "primeiro_turno_2026": {
            "municipios": int(t1["cd_municipio_tse"].nunique()),
            "votos_lula": int(lula),
            "votos_flavio": int(flavio),
            "votos_validos": int(validos),
            "pct_lula": round(100 * lula / validos, 2),
            "pct_flavio": round(100 * flavio / validos, 2),
            "abrangencia": "Municípios. O exterior (ZZ) não entra nestes totais.",
        },
        "ufs": ufs,
        "segundo_turno": {
            "secoes_totalizadas": 0,
            "secoes_totais": 499248,
            "carimbo_tse": "24/10/2026 19:19:13",
            "apuracao_completa": False,
            "aviso": "O arquivo nacional do TSE estava com zero seções totalizadas. O mapa não pinta um 2º turno.",
        },
        "deputado": {
            "candidaturas": int(len(dep)),
            "eleitos": eleitos,
            "cadeiras": 513,
            "votos_nominais": int(dep["votos_nominais"].sum()),
            "superaram_quociente": int(dep["superou_quociente"].fillna(False).sum()),
            "nota_cadeira": nota_cadeira,
            "partidos": [
                {
                    "partido": r.sg_partido,
                    "candidatos": int(r.candidatos),
                    "eleitos": int(r.eleitos),
                    "votos": int(r.votos),
                }
                for r in partidos.itertuples(index=False)
            ],
        },
    }
    (OUT / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False), encoding="utf-8")

    cols = [
        "sq_candidato", "nr_candidato", "nm_urna", "nm_candidato", "sg_uf", "sg_partido",
        "sg_federacao", "votos_nominais", "eleito", "superou_quociente", "experiencia_previa",
        "votos_presidente_partido_uf", "n_candidatos_partido_uf", "quociente_eleitoral",
        "ds_genero", "idade_na_eleicao",
    ]
    tabela = dep[cols].sort_values("votos_nominais", ascending=False).copy()
    tabela["sg_federacao"] = tabela["sg_federacao"].map(lambda v: None if sem_acento(v) in ("", "#NULO", "#NULO#", "NAN") else v)
    tabela["votos_nominais"] = tabela["votos_nominais"].map(inteiro)
    tabela["votos_presidente_partido_uf"] = tabela["votos_presidente_partido_uf"].map(inteiro)
    tabela["quociente_eleitoral"] = tabela["quociente_eleitoral"].map(inteiro)
    tabela["experiencia_previa"] = tabela["experiencia_previa"].map(lambda v: None if pd.isna(v) else int(v))
    tabela["eleito"] = tabela["eleito"].map(lambda v: None if pd.isna(v) else bool(v))
    tabela["superou_quociente"] = tabela["superou_quociente"].map(lambda v: None if pd.isna(v) else bool(v))
    tabela["idade_na_eleicao"] = tabela["idade_na_eleicao"].map(lambda v: arred(v, 0))
    tabela["nr_candidato"] = tabela["nr_candidato"].map(inteiro)
    tabela["n_candidatos_partido_uf"] = tabela["n_candidatos_partido_uf"].map(inteiro)
    (OUT / "deputados.json").write_text(tabela.to_json(orient="records", force_ascii=False), encoding="utf-8")
    exportar_indice(t1)

    import geopandas as gpd

    malha = gpd.read_file(DATA / "malha_municipios.geojson")
    malha = malha[["CD_MUN", "NM_MUN", "geometry"]].copy()
    malha["cd_ibge"] = malha["CD_MUN"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    comp = comp.copy()
    comp["cd_ibge"] = comp["cd_ibge"].map(lambda v: None if pd.isna(v) else str(v).replace(".0", "").zfill(7))
    juntar = [
        "cd_ibge", "sg_uf", "nm_municipio",
        "votos_lula_2026_1t", "votos_flavio_2026_1t", "validos_2026_1t",
        "pct_lula_2026_1t", "pct_flavio_2026_1t", "vencedor_par_2026_1t",
        "votos_lula_2022_2t", "votos_bolsonaro_2022_2t", "validos_2022_2t",
        "pct_lula_2022_2t", "pct_bolsonaro_2022_2t", "vencedor_2022_2t",
        "votos_haddad_2018_2t", "votos_bolsonaro_2018_2t", "validos_2018_2t",
        "pct_haddad_2018_2t", "pct_bolsonaro_2018_2t", "vencedor_2018_2t",
    ]
    malha = malha.merge(comp[juntar], on="cd_ibge", how="left")
    features = []
    for r in malha.itertuples(index=False):
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        geom = geom.simplify(0.012, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {
                "ibge": r.cd_ibge,
                "uf": None if pd.isna(r.sg_uf) else r.sg_uf,
                "nm": r.NM_MUN if pd.isna(r.nm_municipio) else r.nm_municipio,
                "l26": inteiro(r.votos_lula_2026_1t),
                "f26": inteiro(r.votos_flavio_2026_1t),
                "v26": inteiro(r.validos_2026_1t),
                "pl26": arred(r.pct_lula_2026_1t, 1),
                "pf26": arred(r.pct_flavio_2026_1t, 1),
                "w26": None if pd.isna(r.vencedor_par_2026_1t) else r.vencedor_par_2026_1t,
                "c26": lado(r.vencedor_par_2026_1t),
                "l22": inteiro(r.votos_lula_2022_2t),
                "b22": inteiro(r.votos_bolsonaro_2022_2t),
                "v22": inteiro(r.validos_2022_2t),
                "pl22": arred(r.pct_lula_2022_2t, 1),
                "pb22": arred(r.pct_bolsonaro_2022_2t, 1),
                "w22": None if pd.isna(r.vencedor_2022_2t) else r.vencedor_2022_2t,
                "c22": lado(r.vencedor_2022_2t),
                "h18": inteiro(r.votos_haddad_2018_2t),
                "b18": inteiro(r.votos_bolsonaro_2018_2t),
                "v18": inteiro(r.validos_2018_2t),
                "ph18": arred(r.pct_haddad_2018_2t, 1),
                "pb18": arred(r.pct_bolsonaro_2018_2t, 1),
                "w18": None if pd.isna(r.vencedor_2018_2t) else r.vencedor_2018_2t,
                "c18": lado(r.vencedor_2018_2t),
            },
            "geometry": {"type": geom.geom_type, "coordinates": arredondar_coords(geom.__geo_interface__["coordinates"])},
        })
    colecao = {"type": "FeatureCollection", "features": features}
    (OUT / "municipios.geojson").write_text(json.dumps(colecao, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"features {len(features)}")
    print(f"deputados {len(tabela)}")
    print(f"1º turno válidos {int(validos)} flavio {resumo['primeiro_turno_2026']['pct_flavio']} lula {resumo['primeiro_turno_2026']['pct_lula']}")
    for nome in ("resumo.json", "prediction.json", "deputados.json", "municipios.json", "municipios.geojson"):
        caminho = OUT / nome
        print(f"{nome} {caminho.stat().st_size / 1_048_576:.2f} MB")


if __name__ == "__main__":
    exportar()
