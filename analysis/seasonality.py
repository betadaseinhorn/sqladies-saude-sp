"""Sazonalidade das internações por período e região.

- Índice sazonal mensal: para cada ano, internações do mês / média mensal do ano;
  depois a média dos anos. 1,20 = mês 20% acima da média.
- Decomposição STL (período 12) da série mensal do estado e de cada DRS.
  Com 24 meses a STL só separa bem a componente sazonal; a tendência é indicativa.
"""
from __future__ import annotations

import pandas as pd
from statsmodels.tsa.seasonal import STL

from analysis.common import query, save

ESTACOES = {12: "Verão", 1: "Verão", 2: "Verão", 3: "Outono", 4: "Outono", 5: "Outono",
            6: "Inverno", 7: "Inverno", 8: "Inverno", 9: "Primavera", 10: "Primavera",
            11: "Primavera"}


def indice_sazonal(df: pd.DataFrame, chave: str) -> pd.DataFrame:
    """df: colunas [chave, mes_inter, n] -> [chave, mes, indice, media_mensal]."""
    d = df.copy()
    d["ano"] = d["mes_inter"].str[:4]
    d["mes"] = d["mes_inter"].str[5:7].astype(int)
    d["media_ano"] = d.groupby([chave, "ano"])["n"].transform("mean")
    d["idx"] = d["n"] / d["media_ano"]
    out = (d.groupby([chave, "mes"])
             .agg(indice=("idx", "mean"), media_mensal=("n", "mean"))
             .reset_index())
    return out.rename(columns={chave: "chave"})


def stl(serie: pd.Series) -> pd.DataFrame:
    res = STL(serie.values, period=12, robust=True).fit()
    return pd.DataFrame({"mes_inter": serie.index, "observado": serie.values,
                         "tendencia": res.trend, "sazonal": res.seasonal,
                         "residuo": res.resid})


def run(con) -> None:
    base = """
        SELECT {k} AS chave, a.mes_inter, SUM(a.internacoes) AS n
        FROM agg_mensal_hosp a JOIN dim_municipio m ON m.cod_mun = a.mun_int
        {where} GROUP BY 1, 2"""
    frames = []
    for nivel, k, where in [
        ("Estado", "'São Paulo'", ""),
        ("DRS", "m.drs_nome", ""),
        ("Região de Saúde", "m.regsaud_nome", ""),
        ("RRAS", "m.rras_nome", ""),
        ("Caráter", "a.carater", ""),
    ]:
        idx = indice_sazonal(query(con, base.format(k=k, where=where)), "chave")
        idx.insert(0, "nivel", nivel)
        idx["cap_cid"] = None
        frames.append(idx)

    cap = query(con, """SELECT a.cap_cid AS chave, a.mes_inter, SUM(a.internacoes) AS n
                        FROM agg_mensal_hosp a WHERE a.cap_cid IS NOT NULL GROUP BY 1, 2""")
    idx = indice_sazonal(cap, "chave")
    idx.insert(0, "nivel", "Capítulo CID")
    idx["cap_cid"] = idx["chave"]
    frames.append(idx)

    # Capítulo × DRS (para "sazonalidade das doenças respiratórias por região")
    cd = query(con, """SELECT m.drs_nome || '|' || a.cap_cid AS chave, a.mes_inter,
                              SUM(a.internacoes) AS n
                       FROM agg_mensal_hosp a JOIN dim_municipio m ON m.cod_mun = a.mun_int
                       WHERE a.cap_cid IS NOT NULL GROUP BY 1, 2""")
    idx = indice_sazonal(cd, "chave")
    idx[["chave", "cap_cid"]] = idx["chave"].str.split("|", expand=True)
    idx.insert(0, "nivel", "DRS × Capítulo")
    frames.append(idx)

    saz = pd.concat(frames, ignore_index=True)
    saz["estacao"] = saz["mes"].map(ESTACOES)
    save(con, "res_sazonalidade", saz)

    # STL: estado e DRS
    serie = query(con, """SELECT 'São Paulo' AS chave, mes_inter, SUM(internacoes) n
                          FROM agg_mensal_hosp GROUP BY 2
                          UNION ALL
                          SELECT m.drs_nome, a.mes_inter, SUM(a.internacoes)
                          FROM agg_mensal_hosp a JOIN dim_municipio m ON m.cod_mun = a.mun_int
                          GROUP BY 1, 2""")
    out = []
    for chave, g in serie.groupby("chave"):
        s = g.set_index("mes_inter")["n"].sort_index().astype(float)
        r = stl(s)
        r.insert(0, "chave", chave)
        out.append(r)
    save(con, "res_stl", pd.concat(out, ignore_index=True))
