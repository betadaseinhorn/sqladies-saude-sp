"""Indicadores por município e por hospital, base dos rankings e comparações.

Dois pontos de vista por município:
- residência (mun_res): demanda da população → taxa de internação por 1.000 hab.
- ocorrência (mun_int): onde a internação aconteceu → volume, atração de pacientes.
Valores anuais = total do período / número de anos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.common import N_ANOS, municipios, query, save


def indicadores_municipio(con) -> pd.DataFrame:
    mun = municipios(con)

    res = query(con, """
        SELECT mun_res AS cod_mun,
               SUM(internacoes) AS int_res, SUM(dias_perm) AS dias_res,
               SUM(valor_total) AS valor_res, SUM(obitos) AS obitos_res,
               SUM(internadas_fora) AS fora_res,
               SUM(CASE WHEN carater = 'Urgência' THEN internacoes END) AS urg_res,
               SUM(CASE WHEN faixa_etaria IN ('60-74', '75+') THEN internacoes END) AS idosos_res,
               SUM(CASE WHEN cap_cid = 'X' THEN internacoes END) AS resp_res
        FROM agg_mensal_res GROUP BY 1""")

    occ = query(con, """
        SELECT mun_int AS cod_mun,
               SUM(internacoes) AS int_occ, SUM(dias_perm) AS dias_occ,
               SUM(valor_total) AS valor_occ, SUM(residentes_fora) AS atraidos,
               COUNT(DISTINCT cnes) AS hospitais_sih
        FROM agg_mensal_hosp GROUP BY 1""")

    leitos = query(con, """
        SELECT cod_mun, AVG(sus) AS leitos_sus, AVG(tot) AS leitos_total, AVG(uti) AS leitos_uti_sus
        FROM (SELECT cod_mun, competencia, SUM(qt_sus) sus, SUM(qt_exist) tot,
                     SUM(CASE WHEN tp_leito LIKE 'Complementar%' THEN qt_sus ELSE 0 END) uti
              FROM fato_leitos GROUP BY 1, 2)
        GROUP BY 1""")

    est = query(con, """
        SELECT cod_mun,
               SUM(grupo = 'UBS') AS ubs, SUM(grupo = 'Hospital') AS hospitais,
               SUM(grupo = 'Urgência') AS urgencias
        FROM dim_estabelecimento GROUP BY 1""")

    df = (mun.merge(res, on="cod_mun", how="left").merge(occ, on="cod_mun", how="left")
             .merge(leitos, on="cod_mun", how="left").merge(est, on="cod_mun", how="left"))
    fill0 = ["int_res", "dias_res", "valor_res", "obitos_res", "fora_res", "urg_res",
             "idosos_res", "resp_res", "int_occ", "dias_occ", "valor_occ", "atraidos",
             "hospitais_sih", "leitos_sus", "leitos_total", "leitos_uti_sus", "ubs",
             "hospitais", "urgencias"]
    df[fill0] = df[fill0].fillna(0)

    per = lambda a, b: np.where(b > 0, a / b, np.nan)  # noqa: E731
    df["int_res_ano"] = df["int_res"] / N_ANOS
    df["int_occ_ano"] = df["int_occ"] / N_ANOS
    df["taxa_int_1k"] = per(df["int_res_ano"] * 1000, df["pop"])
    df["perm_media"] = per(df["dias_res"], df["int_res"])
    df["perm_media_occ"] = per(df["dias_occ"], df["int_occ"])
    df["valor_medio"] = per(df["valor_res"], df["int_res"])
    df["mortalidade"] = per(df["obitos_res"] * 100, df["int_res"])
    df["pct_urgencia"] = per(df["urg_res"] * 100, df["int_res"])
    df["pct_idosos"] = per(df["idosos_res"] * 100, df["int_res"])
    df["pct_resp"] = per(df["resp_res"] * 100, df["int_res"])
    df["pct_fora"] = per(df["fora_res"] * 100, df["int_res"])
    df["pct_atraidos"] = per(df["atraidos"] * 100, df["int_occ"])
    df["saldo_fluxo"] = (df["int_occ"] - df["int_res"]) / N_ANOS
    df["leitos_sus_10k"] = per(df["leitos_sus"] * 10000, df["pop"])
    df["ubs_10k"] = per(df["ubs"] * 10000, df["pop"])
    df["densidade"] = per(df["pop"], df["area_km2"])
    df["int_por_leito"] = per(df["int_occ_ano"], df["leitos_sus"])
    df["ocupacao_est"] = np.clip(per(df["dias_occ"] / N_ANOS * 100, df["leitos_sus"] * 365), 0, 200)
    return df


def indicadores_hospital(con) -> pd.DataFrame:
    h = query(con, """
        SELECT a.cnes, a.mun_int AS cod_mun,
               SUM(internacoes) AS internacoes, SUM(dias_perm) AS dias_perm,
               SUM(valor_total) AS valor_total, SUM(obitos) AS obitos,
               SUM(residentes_fora) AS atraidos, SUM(idosos) AS idosos,
               SUM(CASE WHEN carater = 'Urgência' THEN internacoes END) AS urgencias,
               SUM(uti_dias) AS uti_dias
        FROM agg_mensal_hosp a GROUP BY 1, 2""")
    # um hospital pode aparecer com mais de um município por erro de cadastro: fica o principal
    h = h.sort_values("internacoes", ascending=False).drop_duplicates("cnes")
    leitos = query(con, """
        SELECT cnes, AVG(sus) AS leitos_sus, AVG(tot) AS leitos_total, AVG(uti) AS leitos_uti_sus
        FROM (SELECT cnes, competencia, SUM(qt_sus) sus, SUM(qt_exist) tot,
                     SUM(CASE WHEN tp_leito LIKE 'Complementar%' THEN qt_sus ELSE 0 END) uti
              FROM fato_leitos GROUP BY 1, 2)
        GROUP BY 1""")
    est = query(con, """SELECT cnes, nome, tipo_desc, esfera, natureza_juridica, gestao,
                               telefone, email, lat, lon
                        FROM dim_estabelecimento""")
    mun = query(con, "SELECT cod_mun, nome AS municipio, drs_nome, regsaud_nome FROM dim_municipio")
    df = (h.merge(leitos, on="cnes", how="left").merge(est, on="cnes", how="left")
           .merge(mun, on="cod_mun", how="left"))
    df["nome"] = df["nome"].fillna("CNES " + df["cnes"].astype(str))
    df["internacoes_ano"] = df["internacoes"] / N_ANOS
    df["perm_media"] = df["dias_perm"] / df["internacoes"].where(df["internacoes"] > 0)
    df["valor_medio"] = df["valor_total"] / df["internacoes"].where(df["internacoes"] > 0)
    df["mortalidade"] = df["obitos"] * 100 / df["internacoes"].where(df["internacoes"] > 0)
    df["pct_urgencia"] = df["urgencias"].fillna(0) * 100 / df["internacoes"].where(df["internacoes"] > 0)
    df["pct_atraidos"] = df["atraidos"] * 100 / df["internacoes"].where(df["internacoes"] > 0)
    df["int_por_leito"] = df["internacoes_ano"] / df["leitos_sus"].where(df["leitos_sus"] > 0)
    df["ocupacao_est"] = np.clip(df["dias_perm"] / N_ANOS * 100
                                 / (df["leitos_sus"].where(df["leitos_sus"] > 0) * 365), 0, 200)
    return df


def run(con) -> pd.DataFrame:
    mun = indicadores_municipio(con)
    save(con, "res_municipio", mun)
    save(con, "res_hospital", indicadores_hospital(con))
    return mun
