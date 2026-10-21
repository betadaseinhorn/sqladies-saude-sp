"""Indicadores de capacidade mensais: internações, permanência e leitos por DRS.

Ocupação estimada = dias de permanência das internações iniciadas no mês
/ (leitos SUS × dias do mês). É uma aproximação: a AIH registra a permanência
total no mês da internação, e nem todo leito SUS recebe pacientes do SIH.
"""
from __future__ import annotations

import pandas as pd

from analysis.common import query, save


def run(con) -> None:
    occ = query(con, """
        SELECT m.drs_nome, a.mes_inter,
               SUM(a.internacoes) AS internacoes, SUM(a.dias_perm) AS dias_perm
        FROM agg_mensal_hosp a JOIN dim_municipio m ON m.cod_mun = a.mun_int
        GROUP BY 1, 2""")
    leitos = query(con, """
        SELECT m.drs_nome,
               substr(l.competencia, 1, 4) || '-' || substr(l.competencia, 5, 2) AS mes_inter,
               SUM(l.qt_sus) AS leitos_sus, SUM(l.qt_exist) AS leitos_total
        FROM fato_leitos l JOIN dim_municipio m ON m.cod_mun = l.cod_mun
        GROUP BY 1, 2""")
    df = occ.merge(leitos, on=["drs_nome", "mes_inter"], how="left")
    dias_mes = pd.to_datetime(df["mes_inter"] + "-01").dt.days_in_month
    df["perm_media"] = df["dias_perm"] / df["internacoes"]
    df["ocupacao_est"] = df["dias_perm"] * 100 / (df["leitos_sus"] * dias_mes)
    df["int_por_100_leitos"] = df["internacoes"] * 100 / df["leitos_sus"]
    save(con, "res_capacidade_drs_mensal", df)
