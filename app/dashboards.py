"""Builders de dashboard: um por pergunta do catálogo.

Cada builder recebe os parâmetros extraídos pelo matcher e devolve um dicionário:

    {title, subtitle, filtros, kpis[], charts[], tables[], insights[], nota}

Os gráficos vão como traces do Plotly sem cores: o front-end aplica o tema e a
paleta (claro/escuro). `colorSlot` = posição na paleta categórica;
`colorRole` = "muted" para contexto; heatmaps usam `scale` = diverging|sequential.

`build()` guarda o resultado em cache por (pergunta, filtros): o banco é somente leitura,
então o mesmo pedido sempre gera o mesmo dashboard. Depois de refazer o banco, reinicie o
servidor (vale também para os caches de app/db.py e alerts.referencias()).
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from app import alerts as A
from app import db
from app import relevancia as R
from app.questions import POR_ID, SEGUINTES
from app.sql_oracle import oracle_sql

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                "setembro", "outubro", "novembro", "dezembro"]


# ------------------------------------------------------------------ formatos --
def fmt_int(v) -> str:
    return f"{v:,.0f}".replace(",", ".") if v == v and v is not None else "–"


def fmt_dec(v, casas=1) -> str:
    if v is None or v != v:
        return "–"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_compact(v) -> str:
    if v is None or v != v:
        return "–"
    a = abs(v)
    if a >= 1e9:
        return fmt_dec(v / 1e9, 1) + " bi"
    if a >= 1e6:
        return fmt_dec(v / 1e6, 1) + " mi"
    if a >= 1e4:
        return fmt_dec(v / 1e3, 0) + " mil"
    return fmt_int(v)


def fmt_brl(v) -> str:
    return "R$ " + fmt_compact(v) if abs(v) >= 1e4 else "R$ " + fmt_dec(v, 0)


def fmt_pct(v, casas=1) -> str:
    return fmt_dec(v, casas) + "%"


def signed(v, casas=0) -> str:
    """+5 / −7 / 0 com vírgula decimal (sem "-0")."""
    r = round(float(v), casas)
    if r == 0:
        return fmt_dec(0, casas)
    return ("+" if r > 0 else "−") + fmt_dec(abs(r), casas)


def mes_label(ym: str) -> str:
    return f"{MESES[int(ym[5:7]) - 1]}/{ym[2:4]}"


# --------------------------------------------------------------- componentes --
def kpi(label: str, value: str, hint: str = "") -> dict:
    return {"label": label, "value": value, "hint": hint}


def chart(title: str, traces: list, *, subtitle: str = "", layout: dict | None = None,
          height: int = 340, wide: bool = False) -> dict:
    return {"title": title, "subtitle": subtitle, "traces": traces,
            "layout": layout or {}, "height": height, "wide": wide}


def mapa_mun(title: str, df: pd.DataFrame, col: str, hover: str, *, subtitle: str = "", legenda: str = "",
             categorias: list[str] | None = None, base=None, extras: list | None = None) -> dict:
    """Mapa coroplético dos municípios de SP (malha IBGE em static/vendor/sp_municipios.geojson).

    `geojson: "sp"` é resolvido pelo front. A escala vai até o percentil 97 para que poucos
    municípios extremos não apaguem as diferenças entre os demais.
    `categorias`: valores inteiros 0..n-1 em `col`, coloridos com a paleta categórica.
    `base`: códigos dos municípios da região, desenhados em cinza por baixo (quem não tem valor
    aparece sem cor, em vez de sumir do mapa).
    """
    d = df[df[col].notna()]
    traces = []
    if base is not None:
        cods = _list(pd.Series(list(base)).astype(int))
        traces.append({"type": "choropleth", "geojson": "sp", "locations": cods, "z": [0] * len(cods),
                       "scale": "base", "showscale": False, "hoverinfo": "skip"})
    tr = {"type": "choropleth", "geojson": "sp", "locations": _list(d["cod_mun"].astype(int)),
          "z": _list(d[col]), "text": list(d["nome"]), "hovertemplate": "%{text}: " + hover + "<extra></extra>",
          "colorbar": {"thickness": 10, "len": 0.8, "title": {"text": legenda, "side": "right"}}}
    if categorias:
        tr.update({"scale": "categorical", "zmin": -0.5, "zmax": len(categorias) - 0.5, "categorias": categorias,
                   "customdata": [categorias[int(v)] for v in d[col]]})
    else:
        tr.update({"scale": "sequential", "zmin": _num(d[col].min()), "zmax": _num(d[col].quantile(0.97))})
    return chart(title, traces + [tr] + (extras or []), subtitle=subtitle, height=520,
                 layout={"geo": {"fitbounds": "locations", "visible": False},
                         "margin": {"l": 0, "r": 0, "t": 4, "b": 0}})


def table(title: str, df: pd.DataFrame, cols: list[tuple[str, str, str]]) -> dict:
    """cols: (coluna, rótulo, formato: text|int|dec1|dec2|pct|brl)."""
    rows = df[[c for c, _, _ in cols]].replace([np.inf, -np.inf], np.nan)
    rows = rows.astype(object).where(rows.notna(), None)
    return {"title": title,
            "columns": [{"key": c, "label": lab, "fmt": f} for c, lab, f in cols],
            "rows": rows.to_dict("records")}


def bar_h(labels, values, *, slot=0, text=None, hover="%{y}: %{x}<extra></extra>",
          name=None, custom=None) -> dict:
    t = {"type": "bar", "orientation": "h", "y": list(labels), "x": [_num(v) for v in values],
         "colorSlot": slot, "hovertemplate": hover}
    if text is not None:
        t.update(text=list(text), textposition="outside", cliponaxis=False)
    if name:
        t["name"] = name
    if custom is not None:
        t["customdata"] = custom
    return t


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if math.isnan(f) or math.isinf(f) else f


def _list(s) -> list:
    return [_num(v) for v in s]


def bar_layout(n: int, **extra) -> dict:
    lay = {"yaxis": {"autorange": "reversed", "automargin": True},
           "xaxis": {"automargin": True}, "margin": {"l": 10, "r": 60}}
    lay.update(extra)
    return lay


def bar_height(n: int) -> int:
    return max(240, 28 * n + 70)


# ------------------------------------------------------------------- filtros --
def filtro(p: dict, *, alias="a", mun_col="mun_int", tem_cap=True, tem_carater=True):
    """Cláusula WHERE parametrizada para as tabelas agregadas + descrição."""
    where, args, desc = ["1=1"], [], []
    if p.get("ano"):
        where.append(f"{alias}.mes_inter LIKE ?")
        args.append(f"{p['ano']}-%")
        desc.append(str(p["ano"]))
    if p.get("drs"):
        where.append("m.drs_num = ?")
        args.append(int(p["drs"]))
        desc.append(nome_drs(p["drs"]))
    if tem_cap and p.get("cap_cid"):
        where.append(f"{alias}.cap_cid = ?")
        args.append(p["cap_cid"])
        desc.append("CID: " + nome_cap(p["cap_cid"]))
    if tem_carater and p.get("carater"):
        where.append(f"{alias}.carater = ?")
        args.append(p["carater"])
        desc.append(p["carater"])
    join = f"JOIN dim_municipio m ON m.cod_mun = {alias}.{mun_col}"
    return join, " AND ".join(where), tuple(args), desc


def n_anos(p: dict) -> int:
    return 1 if p.get("ano") else len(db.anos())


def periodo(p: dict) -> str:
    a = db.anos()
    return str(p["ano"]) if p.get("ano") else f"{a[0]}–{a[-1]}"


def nome_drs(num) -> str:
    d = db.drs()
    return d.loc[d["drs_num"] == int(num), "drs_nome"].iloc[0]


def nome_cap(cap) -> str:
    c = db.capitulos()
    return c.loc[c["cap_cod"] == cap, "cap_nome"].iloc[0]


def nome_mun(cod) -> str:
    m = db.municipios()
    return m.loc[m["cod_mun"] == int(cod), "nome"].iloc[0]


def pop_col(p: dict) -> str:
    return f"pop_{p['ano']}" if p.get("ano") else "(pop_2024 + pop_2025) / 2.0"


def _cods_regiao(p: dict) -> list:
    m = db.municipios()
    return list(m.loc[m["drs_num"] == int(p["drs"]), "cod_mun"] if p.get("drs") else m["cod_mun"])


def _ok(alertas: list) -> list:
    return [a for a in alertas if a]


def _regiao(p: dict) -> dict:
    """Indicadores de contexto do estado ou da DRS filtrada (base dos alertas)."""
    m = db.df("SELECT * FROM res_municipio")
    if p.get("drs"):
        m = m[m["drs_num"] == int(p["drs"])]
    na = len(db.anos())
    grandes = m[m["pop"] >= 5000]
    crit = (grandes["taxa_int_1k"].map(lambda v: A.nivel("taxa", v)) == "critico").sum()
    return {"onde": nome_drs(p["drs"]).split(" - ")[0] if p.get("drs") else "estado",
            "ocupacao": m["dias_occ"].sum() / na * 100 / (m["leitos_sus"].sum() * 365),
            "leitos_10k": m["leitos_sus"].sum() * 10000 / m["pop"].sum(),
            "pct_fora": m["fora_res"].sum() * 100 / m["int_res"].sum(),
            "pct_mun_criticos": crit * 100 / max(len(grandes), 1)}


def _alertas_regiao(p: dict, *chaves: str) -> list:
    r = _regiao(p)
    return [A.classificar(k, r[k], onde=r["onde"]) for k in chaves]


def _pico(mensal: pd.DataFrame) -> float:
    d = mensal.assign(k="x")[["k", "mes_inter", "n"]]
    return float((_indice(d, "k").iloc[0].max() - 1) * 100)


def _status_col(df: pd.DataFrame, chave: str, col: str, ref=None) -> pd.DataFrame:
    return df.assign(situacao=[A.nivel(chave, v, ref) for v in df[col]])


def _rotulo(alerta: dict | None, indicador: str) -> dict | None:
    if alerta:
        alerta["indicador"] = indicador
    return alerta


# ================================================================ builders ====
def visao_geral(p: dict) -> dict:
    join, where, args, desc = filtro(p)
    tot = db.df(f"""SELECT SUM(internacoes) n, SUM(dias_perm) d, SUM(valor_total) v,
                           SUM(obitos) o, SUM(CASE WHEN carater='Urgência' THEN internacoes END) u,
                           COUNT(DISTINCT cnes) h
                    FROM agg_mensal_hosp a {join} WHERE {where}""", args).iloc[0]
    mensal = db.df(f"""SELECT mes_inter, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                       WHERE {where} GROUP BY 1 ORDER BY 1""", args)
    caps = db.df(f"""SELECT c.cap_nome, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                     JOIN dim_cid_capitulo c ON c.cap_cod = a.cap_cid
                     WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", args)
    drs = db.df(f"""SELECT m.drs_nome, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                    WHERE {where} GROUP BY 1 ORDER BY 2 DESC""", args)
    pc = pop_col(p)
    pop = db.scalar(f"SELECT SUM({pc}) FROM dim_municipio m WHERE "
                    + ("m.drs_num = ?" if p.get("drs") else "1=1"),
                    (int(p["drs"]),) if p.get("drs") else ())
    na = n_anos(p)
    n = tot["n"]
    kpis = [
        kpi("Internações", fmt_compact(n), f"{periodo(p)} · {fmt_compact(n / na)}/ano"),
        kpi("Taxa de internação", fmt_dec(n / na * 1000 / pop, 1) + " /1.000 hab.",
            "por ano, pelo local de internação"),
        kpi("Valor pago", fmt_brl(tot["v"]), f"média {fmt_brl(tot['v'] / n)} por internação"),
        kpi("Permanência média", fmt_dec(tot["d"] / n, 1) + " dias"),
        kpi("Urgência", fmt_pct(tot["u"] * 100 / n, 0), "das internações"),
        kpi("Mortalidade hospitalar", fmt_pct(tot["o"] * 100 / n, 1)),
    ]
    charts = [
        chart("Internações por mês", [{
            "type": "scatter", "mode": "lines+markers", "x": [mes_label(x) for x in mensal["mes_inter"]],
            "y": _list(mensal["n"]), "colorSlot": 0, "fill": "tozeroy",
            "hovertemplate": "%{x}: %{y:,.0f} internações<extra></extra>"}],
              layout={"yaxis": {"rangemode": "tozero"}}, wide=True),
        chart("Principais causas (capítulo CID-10)", [bar_h(
            caps["cap_nome"], caps["n"], text=[fmt_compact(v) for v in caps["n"]],
            hover="%{y}: %{x:,.0f}<extra></extra>")],
              layout=bar_layout(len(caps)), height=bar_height(len(caps))),
        chart("Internações por DRS", [bar_h(
            drs["drs_nome"], drs["n"], text=[fmt_compact(v) for v in drs["n"]],
            hover="%{y}: %{x:,.0f}<extra></extra>")],
              layout=bar_layout(len(drs)), height=bar_height(len(drs))),
    ]
    top = caps.iloc[0]
    pico = mensal.loc[mensal["n"].idxmax()]
    insights = [
        f"{top['cap_nome']} é a principal causa, com {fmt_pct(top['n'] * 100 / n, 0)} das internações.",
        f"O mês com mais internações foi {mes_label(pico['mes_inter'])} ({fmt_int(pico['n'])}).",
        f"{fmt_pct(tot['u'] * 100 / n, 0)} das internações são de urgência — a maior parte da "
        "demanda hospitalar não é programada.",
    ]
    if len(drs) > 1:
        insights.append(f"{drs.iloc[0]['drs_nome']} concentra {fmt_pct(drs.iloc[0]['n'] * 100 / n, 0)} "
                        "das internações do estado.")
    al = _alertas_regiao(p, "ocupacao", "leitos_10k", "pct_mun_criticos")
    al.insert(1, A.classificar("pico_sazonal", _pico(mensal), onde="mês de pico"))
    if p.get("drs"):
        al += [A.classificar("taxa", n / na * 1000 / pop, onde="DRS"),
               A.classificar("permanencia", tot["d"] / n, onde="DRS"),
               A.classificar("mortalidade", tot["o"] * 100 / n, onde="DRS")]
    return {"alertas": _ok(al), "title": "Panorama das internações SUS", "subtitle": "Estado de São Paulo · SIH/SUS",
            "filtros": desc, "kpis": kpis, "charts": charts, "insights": insights,
            "tables": []}


def custos(p: dict) -> dict:
    join, where, args, desc = filtro(p, tem_cap=False)
    d = db.df(f"""SELECT c.cap_nome, SUM(valor_total) v, SUM(internacoes) n, SUM(dias_perm) dp,
                         SUM(uti_dias) uti
                  FROM agg_mensal_hosp a {join} JOIN dim_cid_capitulo c ON c.cap_cod = a.cap_cid
                  WHERE {where} GROUP BY 1 ORDER BY v DESC""", args)
    d = d[d["n"] > 0]
    d["medio"] = d["v"] / d["n"]
    d["pct"] = d["v"] * 100 / d["v"].sum()
    d["perm"] = d["dp"] / d["n"]
    top = d.head(12)
    medio = d.sort_values("medio", ascending=False).head(12)
    tot = d["v"].sum()
    kpis = [kpi("Valor total pago", fmt_brl(tot), periodo(p)),
            kpi("Valor médio por internação", fmt_brl(tot / d["n"].sum())),
            kpi("Maior gasto", top.iloc[0]["cap_nome"], fmt_pct(top.iloc[0]["pct"], 0) + " do total"),
            kpi("Internação mais cara (média)", medio.iloc[0]["cap_nome"],
                fmt_brl(medio.iloc[0]["medio"]) + " por internação")]
    charts = [
        chart("Valor total pago por causa", [bar_h(
            top["cap_nome"], top["v"], text=[fmt_brl(v) for v in top["v"]],
            hover="%{y}: R$ %{x:,.0f}<extra></extra>")],
              layout=bar_layout(len(top)), height=bar_height(len(top))),
        chart("Valor médio por internação", [bar_h(
            medio["cap_nome"], medio["medio"], slot=1, text=[fmt_brl(v) for v in medio["medio"]],
            hover="%{y}: R$ %{x:,.0f}<extra></extra>")],
              layout=bar_layout(len(medio)), height=bar_height(len(medio))),
    ]
    insights = [
        f"{top.iloc[0]['cap_nome']} e {top.iloc[1]['cap_nome']} somam "
        f"{fmt_pct(top.iloc[:2]['pct'].sum(), 0)} do valor pago.",
        f"{medio.iloc[0]['cap_nome']} tem o maior custo médio ({fmt_brl(medio.iloc[0]['medio'])}), "
        f"{fmt_dec(medio.iloc[0]['medio'] / (tot / d['n'].sum()), 1)}× a média geral.",
    ]
    al = [A.classificar("permanencia", d["dp"].sum() / d["n"].sum(), onde="geral")]
    al += _alertas_regiao(p, "ocupacao", "leitos_10k")
    return {"alertas": _ok(al), "title": "Causas de internação que mais custam ao SUS", "subtitle": "Valores pagos (SIH/SUS)",
            "filtros": desc, "kpis": kpis, "charts": charts, "insights": insights,
            "tables": [table("Custos por capítulo da CID-10", d,
                             [("cap_nome", "Capítulo", "text"), ("v", "Valor total", "brl"),
                              ("pct", "% do total", "pct"), ("n", "Internações", "int"),
                              ("medio", "Valor médio", "brl"), ("perm", "Permanência (dias)", "dec1")])]}


# ------------------------------------------------------------- sazonalidade --
def _indice(df: pd.DataFrame, chave: str) -> pd.DataFrame:
    d = df.copy()
    d["ano"] = d["mes_inter"].str[:4]
    d["mes"] = d["mes_inter"].str[5:7].astype(int)
    d["media"] = d.groupby([chave, "ano"])["n"].transform("mean")
    d["idx"] = d["n"] / d["media"]
    return d.groupby([chave, "mes"])["idx"].mean().unstack()


def sazonal_estado(p: dict) -> dict:
    join, where, args, desc = filtro({k: v for k, v in p.items() if k != "ano"})
    s = db.df(f"""SELECT mes_inter, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                  WHERE {where} GROUP BY 1 ORDER BY 1""", args)
    s["k"] = "x"
    idx = _indice(s, "k").iloc[0]
    from statsmodels.tsa.seasonal import STL
    stl = STL(s["n"].astype(float).values, period=12, robust=True).fit()
    x = [mes_label(m) for m in s["mes_inter"]]
    pico, vale = int(idx.idxmax()), int(idx.idxmin())
    amp = (idx.max() - idx.min()) * 100
    anos = sorted(s["mes_inter"].str[:4].unique())
    por_ano = [{"type": "scatter", "mode": "lines+markers", "name": a,
                "x": MESES, "y": _list(s[s["mes_inter"].str.startswith(a)]["n"]),
                "colorSlot": i, "hovertemplate": f"%{{x}}/{a}: %{{y:,.0f}}<extra></extra>"}
               for i, a in enumerate(anos)]
    dev = (idx - 1) * 100
    charts = [
        chart("Série mensal e tendência (STL)", [
            {"type": "scatter", "mode": "lines+markers", "name": "Internações", "x": x,
             "y": _list(s["n"]), "colorSlot": 0, "hovertemplate": "%{x}: %{y:,.0f}<extra></extra>"},
            {"type": "scatter", "mode": "lines", "name": "Tendência", "x": x,
             "y": _list(stl.trend), "colorRole": "muted", "line": {"dash": "dot"},
             "hovertemplate": "Tendência %{x}: %{y:,.0f}<extra></extra>"}], wide=True),
        chart("Índice sazonal: % acima ou abaixo da média do ano", [{
            "type": "bar", "x": MESES, "y": _list(dev.values), "colorByValue": "diverging",
            "text": [f"{signed(v, 0)}%" for v in dev.values], "textposition": "outside",
            "cliponaxis": False, "hovertemplate": "%{x}: %{y:+.1f}% vs. média<extra></extra>"}],
              layout={"yaxis": {"ticksuffix": "%", "zeroline": True}}),
        chart("Comparação entre anos", por_ano),
    ]
    insights = [
        f"Pico em {MESES_LONGOS[pico - 1]} ({signed(dev[pico], 0)}% vs. a média do ano) e vale em "
        f"{MESES_LONGOS[vale - 1]} ({signed(dev[vale], 0)}%).",
        f"Amplitude sazonal de {fmt_dec(amp, 0)} pontos percentuais entre o mês mais e o menos movimentado.",
        "No estado, dezembro a fevereiro têm menos internações eletivas (férias e fim de ano), "
        "e o outono concentra o pico das doenças respiratórias (abril a junho).",
    ]
    if len(anos) == 2:
        a0 = s[s["mes_inter"].str.startswith(anos[0])]["n"].sum()
        a1 = s[s["mes_inter"].str.startswith(anos[1])]["n"].sum()
        insights.append(f"Variação de {anos[0]} para {anos[1]}: {signed((a1 / a0 - 1) * 100, 1)}% nas internações.")
    al = [A.classificar("pico_sazonal", float(dev[pico]), onde=MESES_LONGOS[pico - 1])]
    al += _alertas_regiao(p, "ocupacao")
    return {"alertas": _ok(al), "title": "Como as internações variam ao longo do ano",
            "subtitle": "Série mensal, índice sazonal e decomposição STL",
            "filtros": desc, "charts": charts, "insights": insights, "tables": [],
            "kpis": [kpi("Mês de pico", MESES_LONGOS[pico - 1].capitalize(), f"{signed(dev[pico], 0)}% vs. média"),
                     kpi("Mês de vale", MESES_LONGOS[vale - 1].capitalize(), f"{signed(dev[vale], 0)}% vs. média"),
                     kpi("Amplitude sazonal", fmt_dec(amp, 0) + " p.p."),
                     kpi("Média mensal", fmt_compact(s["n"].mean()), "internações")],
            "nota": "Índice sazonal = internações do mês ÷ média mensal do ano, média dos anos. "
                    "Tendência pela decomposição STL (período 12)."}


def _heat(idx: pd.DataFrame, title: str, subtitle: str = "", height=None) -> dict:
    z = (idx.values - 1) * 100
    return chart(title, [{
        "type": "heatmap", "z": [[_num(v) for v in row] for row in z], "x": MESES,
        "y": list(idx.index), "scale": "diverging", "zmid": 0, "xgap": 2, "ygap": 2,
        "colorbar": {"ticksuffix": "%", "thickness": 10},
        "hovertemplate": "%{y} · %{x}: %{z:+.1f}% vs. média<extra></extra>"}],
                 subtitle=subtitle, layout={"yaxis": {"autorange": "reversed", "automargin": True}},
                 height=height or max(300, 24 * len(idx) + 90), wide=True)


def sazonal_drs(p: dict) -> dict:
    q = {k: v for k, v in p.items() if k not in ("ano", "drs")}
    join, where, args, desc = filtro(q)
    d = db.df(f"""SELECT m.drs_nome k, mes_inter, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                  WHERE {where} GROUP BY 1, 2""", args)
    idx = _indice(d, "k")
    idx = idx.loc[sorted(idx.index, key=lambda s: _romano(s))]
    amp = ((idx.max(axis=1) - idx.min(axis=1)) * 100).sort_values(ascending=False)
    picos = pd.DataFrame({"drs": idx.index, "pico": [MESES_LONGOS[int(m) - 1] for m in idx.idxmax(axis=1)],
                          "pico_pct": (idx.max(axis=1).values - 1) * 100,
                          "vale": [MESES_LONGOS[int(m) - 1] for m in idx.idxmin(axis=1)],
                          "vale_pct": (idx.min(axis=1).values - 1) * 100,
                          "amp": ((idx.max(axis=1) - idx.min(axis=1)) * 100).values})
    moda = picos["pico"].mode().iloc[0]
    charts = [
        _heat(idx, "Índice sazonal por DRS", "Cor: % acima (vermelho) ou abaixo (azul) da média mensal do ano"),
        chart("Amplitude sazonal por DRS (pico − vale)", [bar_h(
            amp.index, amp.values, text=[fmt_dec(v, 0) + " p.p." for v in amp.values],
            hover="%{y}: %{x:.1f} p.p.<extra></extra>")],
              layout=bar_layout(len(amp)), height=bar_height(len(amp))),
    ]
    insights = [
        f"O pico mais comum entre as DRS é {moda} ({(picos['pico'] == moda).sum()} de {len(picos)} DRS).",
        f"{amp.index[0]} tem a maior oscilação ({fmt_dec(amp.iloc[0], 0)} p.p.); "
        f"{amp.index[-1]} é a mais estável ({fmt_dec(amp.iloc[-1], 0)} p.p.).",
        "Fevereiro, dezembro e janeiro são os meses de menor demanda em praticamente todas as regiões.",
    ]
    top_pk = picos.sort_values("pico_pct", ascending=False).head(3)
    al = [A.classificar("pico_sazonal", r["pico_pct"], onde=f"{r['drs'].split(' - ')[0]} ({r['pico']})")
          for _, r in top_pk.iterrows()]
    return {"alertas": _ok(al), "title": "Sazonalidade das internações por DRS",
            "subtitle": "17 Departamentos Regionais de Saúde", "filtros": desc,
            "kpis": [kpi("Pico mais frequente", moda.capitalize()),
                     kpi("Maior amplitude", amp.index[0].split(" - ")[1], fmt_dec(amp.iloc[0], 0) + " p.p."),
                     kpi("Menor amplitude", amp.index[-1].split(" - ")[1], fmt_dec(amp.iloc[-1], 0) + " p.p.")],
            "charts": charts, "insights": insights,
            "tables": [table("Pico e vale por DRS", picos,
                             [("drs", "DRS", "text"), ("pico", "Mês de pico", "text"),
                              ("pico_pct", "Pico vs. média (%)", "dec1"), ("vale", "Mês de vale", "text"),
                              ("vale_pct", "Vale vs. média (%)", "dec1"), ("amp", "Amplitude (p.p.)", "dec1")])]}


def _romano(drs_nome: str) -> int:
    rom = drs_nome.split(" ")[1]
    vals = {"I": 1, "V": 5, "X": 10}
    tot = 0
    for i, ch in enumerate(rom):
        v = vals[ch]
        tot += -v if i + 1 < len(rom) and vals[rom[i + 1]] > v else v
    return tot


def sazonal_causas(p: dict) -> dict:
    q = {k: v for k, v in p.items() if k not in ("ano", "cap_cid")}
    join, where, args, desc = filtro(q, tem_cap=False)
    d = db.df(f"""SELECT c.cap_nome k, mes_inter, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                  JOIN dim_cid_capitulo c ON c.cap_cod = a.cap_cid
                  WHERE {where} AND a.cap_cid <> 'XXII' GROUP BY 1, 2""", args)
    vol = d.groupby("k")["n"].sum()
    d = d[d["k"].isin(vol[vol >= 2000].index)]
    idx = _indice(d, "k")
    amp = ((idx.max(axis=1) - idx.min(axis=1)) * 100).sort_values(ascending=False)
    idx = idx.loc[amp.index]
    top3 = amp.index[:3]
    linhas = [{"type": "scatter", "mode": "lines+markers", "name": k, "x": MESES,
               "y": _list((idx.loc[k] - 1) * 100), "colorSlot": i,
               "hovertemplate": f"{k} · %{{x}}: %{{y:+.1f}}%<extra></extra>"}
              for i, k in enumerate(top3)]
    charts = [
        _heat(idx, "Índice sazonal por causa (capítulo CID-10)", "Ordenado da causa mais para a menos sazonal"),
        chart("As 3 causas mais sazonais", linhas,
              subtitle="% acima ou abaixo da média mensal do ano",
              layout={"yaxis": {"ticksuffix": "%"}}),
        chart("Amplitude sazonal por causa", [bar_h(
            amp.index, amp.values, text=[fmt_dec(v, 0) + " p.p." for v in amp.values],
            hover="%{y}: %{x:.1f} p.p.<extra></extra>")],
              layout=bar_layout(len(amp)), height=bar_height(len(amp))),
    ]
    picos = {k: MESES_LONGOS[int(idx.loc[k].idxmax()) - 1] for k in top3}
    insights = [f"{k}: pico em {picos[k]} ({signed((idx.loc[k].max() - 1) * 100, 0)}%) e vale em "
                f"{MESES_LONGOS[int(idx.loc[k].idxmin()) - 1]} ({signed((idx.loc[k].min() - 1) * 100, 0)}%)."
                for k in top3]
    insights.append("Causas crônicas e obstétricas variam pouco ao longo do ano; doenças respiratórias e "
                    "infecciosas (como a dengue) concentram a sazonalidade.")
    al = [A.classificar("pico_sazonal", (idx.loc[k].max() - 1) * 100, onde=f"{k} ({picos[k]})") for k in top3]
    return {"alertas": _ok(al), "title": "Causas de internação com maior sazonalidade",
            "subtitle": "Índice sazonal por capítulo da CID-10", "filtros": desc,
            "kpis": [kpi("Causa mais sazonal", amp.index[0], fmt_dec(amp.iloc[0], 0) + " p.p. de amplitude"),
                     kpi("Causa mais estável", amp.index[-1], fmt_dec(amp.iloc[-1], 0) + " p.p.")],
            "charts": charts, "insights": insights, "tables": []}


def sazonal_cap_regiao(p: dict) -> dict:
    cap = p.get("cap_cid", "X")
    q = {k: v for k, v in p.items() if k not in ("ano", "drs", "cap_cid")}
    join, where, args, desc = filtro(q, tem_cap=False)
    d = db.df(f"""SELECT m.drs_nome k, mes_inter, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                  WHERE {where} AND a.cap_cid = ? GROUP BY 1, 2""", args + (cap,))
    todas = db.df(f"""SELECT 'Todas' k, mes_inter, SUM(internacoes) n FROM agg_mensal_hosp a {join}
                      WHERE {where} GROUP BY 2""", args)
    est = d.groupby("mes_inter", as_index=False)["n"].sum().assign(k="Estado")
    idx = _indice(d, "k")
    idx = idx.loc[sorted(idx.index, key=_romano)]
    i_est = _indice(est, "k").iloc[0]
    i_all = _indice(todas, "k").iloc[0]
    nome = nome_cap(cap)
    pico_mes = idx.idxmax(axis=1).astype(int)
    pk = pd.DataFrame({"drs": idx.index, "pico": [MESES_LONGOS[m - 1] for m in pico_mes],
                       "pico_pct": (idx.max(axis=1).values - 1) * 100,
                       "amp": ((idx.max(axis=1) - idx.min(axis=1)) * 100).values}).sort_values("pico_pct", ascending=False)
    charts = [
        chart(f"{nome} vs. todas as causas (estado)", [
            {"type": "scatter", "mode": "lines+markers", "name": nome, "x": MESES,
             "y": _list((i_est - 1) * 100), "colorSlot": 0,
             "hovertemplate": "%{x}: %{y:+.1f}%<extra>" + nome + "</extra>"},
            {"type": "scatter", "mode": "lines", "name": "Todas as causas", "x": MESES,
             "y": _list((i_all - 1) * 100), "colorRole": "muted",
             "hovertemplate": "%{x}: %{y:+.1f}%<extra>Todas</extra>"}],
              subtitle="% acima ou abaixo da média mensal do ano", layout={"yaxis": {"ticksuffix": "%"}}),
        chart("Intensidade do pico por DRS", [bar_h(
            pk["drs"], pk["pico_pct"], slot=1,
            text=[f"{signed(v, 0)}% em {m}" for v, m in zip(pk["pico_pct"], pk["pico"])],
            hover="%{y}: %{x:+.1f}%<extra></extra>")],
              layout=bar_layout(len(pk), xaxis={"ticksuffix": "%"}), height=bar_height(len(pk))),
        _heat(idx, f"Índice sazonal de {nome.lower()} por DRS"),
    ]
    pmes = MESES_LONGOS[int(i_est.idxmax()) - 1]
    insights = [
        f"No estado, {nome.lower()} atinge o pico em {pmes} ({signed((i_est.max() - 1) * 100, 0)}%), "
        f"contra {signed((i_all.max() - 1) * 100, 0)}% no pico de todas as causas.",
        f"{pk.iloc[0]['drs']} tem o pico mais intenso ({signed(pk.iloc[0]['pico_pct'], 0)}% em {pk.iloc[0]['pico']}); "
        f"{pk.iloc[-1]['drs']} o mais suave ({signed(pk.iloc[-1]['pico_pct'], 0)}%).",
        f"Mês de pico mais comum entre as DRS: {pk['pico'].mode().iloc[0]}.",
    ]
    al = [A.classificar("pico_sazonal", (i_est.max() - 1) * 100, onde=f"estado ({pmes})")]
    al += [A.classificar("pico_sazonal", r["pico_pct"], onde=f"{r['drs'].split(' - ')[0]} ({r['pico']})")
           for _, r in pk.head(2).iterrows()]
    return {"alertas": _ok(al), "title": f"Sazonalidade por DRS: {nome.lower()}",
            "subtitle": "Índice sazonal por DRS", "filtros": desc + [f"CID: {nome}"],
            "kpis": [kpi("Pico estadual", pmes.capitalize(), f"{signed((i_est.max() - 1) * 100, 0)}% vs. média"),
                     kpi("Vale estadual", MESES_LONGOS[int(i_est.idxmin()) - 1].capitalize(),
                         f"{signed((i_est.min() - 1) * 100, 0)}% vs. média"),
                     kpi("DRS com pico mais intenso", pk.iloc[0]["drs"].split(" - ")[1],
                         f"{signed(pk.iloc[0]['pico_pct'], 0)}%")],
            "charts": charts, "insights": insights,
            "tables": [table("Pico por DRS", pk, [("drs", "DRS", "text"), ("pico", "Mês de pico", "text"),
                                                  ("pico_pct", "Pico vs. média (%)", "dec1"),
                                                  ("amp", "Amplitude (p.p.)", "dec1")])],
            "nota": "Troque a causa digitando, por exemplo, \"sazonalidade da dengue entre as DRS\" "
                    "ou \"doenças circulatórias por região\"."}


# ---------------------------------------------------------------- rankings ---
def _mun_taxas(p: dict) -> pd.DataFrame:
    join, where, args, _ = filtro(p, alias="a", mun_col="mun_res")
    d = db.df(f"""SELECT a.mun_res cod_mun, m.nome, m.drs_nome, {pop_col(p)} pop,
                         SUM(internacoes) n, SUM(dias_perm) dp, SUM(valor_total) v,
                         SUM(internadas_fora) fora
                  FROM agg_mensal_res a {join} WHERE {where} GROUP BY 1""", args)
    na = n_anos(p)
    d["n_ano"] = d["n"] / na
    d["taxa"] = d["n_ano"] * 1000 / d["pop"]
    d["perm"] = d["dp"] / d["n"]
    d["medio"] = d["v"] / d["n"]
    d["pct_fora"] = d["fora"] * 100 / d["n"]
    return d


def ranking_municipios(p: dict) -> dict:
    top_n = p.get("top_n", 20)
    min_pop = 20000
    d = _mun_taxas(p)
    _, _, _, desc = filtro(p)
    taxa_est = d["n_ano"].sum() * 1000 / d["pop"].sum()
    ref = "da DRS" if p.get("drs") else "do estado"
    elig = d[d["pop"] >= min_pop].sort_values("taxa", ascending=False)
    top = elig.head(top_n)
    charts = [chart(f"Top {top_n}: internações por 1.000 habitantes/ano", [bar_h(
        top["nome"], top["taxa"], text=[fmt_dec(v, 1) for v in top["taxa"]],
        hover="%{y}: %{x:.1f} por 1.000 hab.<extra></extra>")],
        subtitle=f"Municípios com {fmt_int(min_pop)}+ habitantes · linha = média {ref} ({fmt_dec(taxa_est, 1)})",
        layout=bar_layout(len(top), shapes=[_vline(taxa_est)]), height=bar_height(len(top)))]
    charts.append(chart("Taxa de internação × população", [
        {"type": "scatter", "mode": "markers", "name": "Municípios", "x": _list(elig["pop"]),
         "y": _list(elig["taxa"]), "text": list(elig["nome"]), "colorRole": "muted",
         "hovertemplate": "%{text}<br>%{x:,.0f} hab. · %{y:.1f}/1.000<extra></extra>"},
        {"type": "scatter", "mode": "markers", "name": f"Top {top_n}", "x": _list(top["pop"]),
         "y": _list(top["taxa"]), "text": list(top["nome"]), "colorSlot": 0,
         "hovertemplate": "%{text}<br>%{x:,.0f} hab. · %{y:.1f}/1.000<extra></extra>"}],
        layout={"xaxis": {"type": "log", "title": {"text": "População (escala log)"}},
                "yaxis": {"title": {"text": "Internações/1.000 hab."}}}))
    charts.append(mapa_mun("Mapa: internações por 1.000 habitantes/ano", d, "taxa", "%{z:.1f} por 1.000 hab.",
                           subtitle="Todos os municípios, pelo local de residência", legenda="por 1.000"))
    insights = [
        f"{top.iloc[0]['nome']} lidera com {fmt_dec(top.iloc[0]['taxa'], 1)} internações por 1.000 hab./ano, "
        f"{fmt_dec(top.iloc[0]['taxa'] / taxa_est, 1)}× a média {ref}.",
        f"A taxa considera o município de residência do paciente, ou seja, mede a demanda da população, "
        f"não onde a internação aconteceu.",
        f"Mediana entre municípios com {fmt_int(min_pop)}+ hab.: {fmt_dec(elig['taxa'].median(), 1)} por 1.000.",
    ]
    elig = _status_col(elig, "taxa", "taxa")
    crit = int((elig["situacao"] == "critico").sum())
    al = [_rotulo(A.classificar("pct_mun_criticos", crit * 100 / max(len(elig), 1)),
                  f"Municípios com taxa crítica · {crit} de {len(elig)}"),
          A.classificar("taxa", top.iloc[0]["taxa"], onde=top.iloc[0]["nome"])]
    if p.get("drs"):
        al.insert(0, A.classificar("taxa", taxa_est, onde="DRS"))
    return {"alertas": _ok(al), "title": f"Os {top_n} municípios com mais internações por habitante",
            "subtitle": "Taxa anual por 1.000 habitantes (pelo município de residência)",
            "filtros": desc, "charts": charts, "insights": insights,
            "kpis": [kpi("Taxa " + ref, fmt_dec(taxa_est, 1), "internações/1.000 hab./ano"),
                     kpi("Maior taxa", top.iloc[0]["nome"], fmt_dec(top.iloc[0]["taxa"], 1) + "/1.000"),
                     kpi("Municípios avaliados", fmt_int(len(elig)), f"com {fmt_int(min_pop)}+ hab.")],
            "tables": [table("Ranking completo", elig.head(100),
                             [("nome", "Município", "text"), ("drs_nome", "DRS", "text"),
                              ("pop", "População", "int"), ("n_ano", "Internações/ano", "int"),
                              ("taxa", "Por 1.000 hab.", "dec1"), ("perm", "Permanência (dias)", "dec1"),
                              ("medio", "Valor médio", "brl"), ("pct_fora", "% internados fora", "pct"),
                              ("situacao", "Situação", "status")])]}


def _vline(x: float) -> dict:
    return {"type": "line", "x0": x, "x1": x, "y0": 0, "y1": 1, "yref": "paper",
            "role": "reference"}


def _hline(y: float) -> dict:
    return {"type": "line", "y0": y, "y1": y, "x0": 0, "x1": 1, "xref": "paper",
            "role": "reference"}


def _hospitais(p: dict) -> pd.DataFrame:
    join, where, args, _ = filtro(p)
    if p.get("municipios"):
        cods = [int(c) for c in p["municipios"]]
        where += f" AND a.mun_int IN ({','.join('?' * len(cods))})"
        args = args + tuple(cods)
    d = db.df(f"""SELECT a.cnes, COALESCE(e.nome, 'CNES ' || a.cnes) nome, m.nome municipio,
                         m.drs_nome, SUM(internacoes) n, SUM(dias_perm) dp, SUM(valor_total) v,
                         SUM(obitos) o, SUM(residentes_fora) fora
                  FROM agg_mensal_hosp a {join} LEFT JOIN dim_estabelecimento e ON e.cnes = a.cnes
                  WHERE {where} GROUP BY 1 HAVING n > 0""", args)
    na = n_anos(p)
    d["n_ano"] = d["n"] / na
    d["perm"] = d["dp"] / d["n"]
    d["medio"] = d["v"] / d["n"]
    d["mort"] = d["o"] * 100 / d["n"]
    d["pct_fora"] = d["fora"] * 100 / d["n"]
    h = db.df("SELECT cnes, leitos_sus, ocupacao_est FROM res_hospital")
    return d.merge(h, on="cnes", how="left")


def _desc_mun(p: dict, desc: list) -> list:
    if p.get("municipios"):
        desc = desc + [", ".join(nome_mun(c) for c in p["municipios"])]
    return desc


def _curto(nome: str, n=42) -> str:
    return nome if len(nome) <= n else nome[: n - 1] + "…"


def ranking_hospitais(p: dict) -> dict:
    top_n = p.get("top_n", 15)
    d = _hospitais(p).sort_values("n", ascending=False)
    _, _, _, desc = filtro(p)
    top = d.head(top_n)
    share = top["n"].sum() * 100 / d["n"].sum()
    charts = [chart(f"Top {top_n} hospitais por internações/ano", [bar_h(
        [_curto(f"{n} ({m})") for n, m in zip(top["nome"], top["municipio"])], top["n_ano"],
        text=[fmt_compact(v) for v in top["n_ano"]],
        hover="%{y}: %{x:,.0f} internações/ano<extra></extra>")],
        layout=bar_layout(len(top)), height=bar_height(len(top)), wide=True)]
    insights = [
        f"Os {top_n} maiores hospitais respondem por {fmt_pct(share, 0)} das internações "
        f"entre {fmt_int(len(d))} hospitais.",
        f"{top.iloc[0]['nome']} ({top.iloc[0]['municipio']}) lidera com "
        f"{fmt_int(top.iloc[0]['n_ano'])} internações/ano.",
    ]
    al = [A.classificar("ocupacao", r["ocupacao_est"], onde=_curto(r["nome"], 40))
          for _, r in top.head(3).iterrows()]
    return {"alertas": _ok(al), "title": "Hospitais que mais realizam internações", "subtitle": "Volume anual de internações SUS",
            "filtros": _desc_mun(p, desc), "charts": charts, "insights": insights,
            "kpis": [kpi("Hospitais com internações", fmt_int(len(d))),
                     kpi(f"Participação do top {top_n}", fmt_pct(share, 0)),
                     kpi("Maior volume", _curto(top.iloc[0]["nome"], 30), fmt_int(top.iloc[0]["n_ano"]) + "/ano")],
            "tables": [table("Hospitais", d.head(100),
                             [("nome", "Hospital", "text"), ("municipio", "Município", "text"),
                              ("n_ano", "Internações/ano", "int"), ("perm", "Permanência (dias)", "dec1"),
                              ("medio", "Valor médio", "brl"), ("mort", "Mortalidade (%)", "dec1"),
                              ("leitos_sus", "Leitos SUS", "int"), ("pct_fora", "% de outros municípios", "pct")])]}


def ranking_permanencia(p: dict) -> dict:
    top_n = p.get("top_n", 15)
    d = _hospitais(p)
    _, _, _, desc = filtro(p)
    min_n = 1000
    elig = d[d["n_ano"] >= min_n].sort_values("perm", ascending=False)
    top = elig.head(top_n)
    media = d["dp"].sum() / d["n"].sum()
    charts = [
        chart(f"Top {top_n}: maior permanência média", [bar_h(
            [_curto(f"{n} ({m})") for n, m in zip(top["nome"], top["municipio"])], top["perm"],
            text=[fmt_dec(v, 1) + " d" for v in top["perm"]],
            hover="%{y}: %{x:.1f} dias<extra></extra>")],
              subtitle=f"Hospitais com {fmt_int(min_n)}+ internações/ano · linha = média ({fmt_dec(media, 1)} dias)",
              layout=bar_layout(len(top), shapes=[_vline(media)]), height=bar_height(len(top)), wide=True),
        chart("Volume × permanência média", [
            {"type": "scatter", "mode": "markers", "name": "Hospitais", "x": _list(elig["n_ano"]),
             "y": _list(elig["perm"]), "text": list(elig["nome"]), "colorRole": "muted",
             "hovertemplate": "%{text}<br>%{x:,.0f}/ano · %{y:.1f} dias<extra></extra>"},
            {"type": "scatter", "mode": "markers", "name": f"Top {top_n}", "x": _list(top["n_ano"]),
             "y": _list(top["perm"]), "text": list(top["nome"]), "colorSlot": 0,
             "hovertemplate": "%{text}<br>%{x:,.0f}/ano · %{y:.1f} dias<extra></extra>"}],
              layout={"xaxis": {"type": "log", "title": {"text": "Internações/ano (log)"}},
                      "yaxis": {"title": {"text": "Permanência média (dias)"}}}, wide=True),
    ]
    insights = [
        f"{top.iloc[0]['nome']} tem a maior permanência ({fmt_dec(top.iloc[0]['perm'], 1)} dias), "
        f"{fmt_dec(top.iloc[0]['perm'] / media, 1)}× a média.",
        "Permanências longas costumam indicar hospitais especializados (psiquiatria, oncologia, "
        "reabilitação) ou pacientes mais graves, não necessariamente ineficiência.",
    ]
    crit = int((elig["perm"].map(lambda v: A.nivel("permanencia", v)) == "critico").sum())
    al = [A.classificar("permanencia", r["perm"], onde=_curto(r["nome"], 40)) for _, r in top.head(2).iterrows()]
    al.append(_rotulo(A.classificar("pct_hosp_criticos", crit * 100 / max(len(elig), 1)),
                      f"Hospitais com permanência crítica · {crit} de {len(elig)}"))
    return {"alertas": _ok(al), "title": "Hospitais com maior permanência média", "subtitle": "Dias de internação por paciente",
            "filtros": _desc_mun(p, desc), "charts": charts, "insights": insights,
            "kpis": [kpi("Permanência média geral", fmt_dec(media, 1) + " dias"),
                     kpi("Maior permanência", _curto(top.iloc[0]["nome"], 30), fmt_dec(top.iloc[0]["perm"], 1) + " dias"),
                     kpi("Hospitais avaliados", fmt_int(len(elig)), f"{fmt_int(min_n)}+ internações/ano")],
            "tables": [table("Hospitais por permanência", elig.head(100),
                             [("nome", "Hospital", "text"), ("municipio", "Município", "text"),
                              ("perm", "Permanência (dias)", "dec1"), ("n_ano", "Internações/ano", "int"),
                              ("medio", "Valor médio", "brl"), ("mort", "Mortalidade (%)", "dec1")])]}


def _perfil_mun(cod: int, p: dict) -> dict:
    q = {k: v for k, v in p.items() if k not in ("drs", "municipios")}
    join, where, args, _ = filtro(q, mun_col="mun_res")
    where += " AND a.mun_res = ?"
    args = args + (cod,)
    t = db.df(f"""SELECT SUM(internacoes) n, SUM(dias_perm) dp, SUM(valor_total) v, SUM(obitos) o,
                         SUM(internadas_fora) fora,
                         SUM(CASE WHEN carater='Urgência' THEN internacoes END) u,
                         SUM(CASE WHEN faixa_etaria IN ('60-74','75+') THEN internacoes END) ido
                  FROM agg_mensal_res a {join} WHERE {where}""", args).iloc[0]
    mensal = db.df(f"""SELECT mes_inter, SUM(internacoes) n FROM agg_mensal_res a {join}
                       WHERE {where} GROUP BY 1 ORDER BY 1""", args)
    caps = db.df(f"""SELECT c.cap_nome, SUM(internacoes) n FROM agg_mensal_res a {join}
                     JOIN dim_cid_capitulo c ON c.cap_cod = a.cap_cid WHERE {where}
                     GROUP BY 1 ORDER BY 2 DESC""", args)
    faixa = db.df(f"""SELECT faixa_etaria, SUM(internacoes) n FROM agg_mensal_res a {join}
                      WHERE {where} AND faixa_etaria IS NOT NULL GROUP BY 1""", args)
    r = db.df("SELECT * FROM res_municipio WHERE cod_mun = ?", (cod,)).iloc[0]
    pop = r[f"pop_{p['ano']}"] if p.get("ano") else r["pop"]
    na = n_anos(p)
    n = t["n"] or 0
    return {"cod": cod, "nome": r["nome"], "drs": r["drs_nome"], "regsaud": r["regsaud_nome"],
            "pop": pop, "n": n, "n_ano": n / na, "taxa": n / na * 1000 / pop,
            "perm": t["dp"] / n if n else None, "medio": t["v"] / n if n else None,
            "mort": t["o"] * 100 / n if n else None, "pct_fora": t["fora"] * 100 / n if n else None,
            "pct_urg": (t["u"] or 0) * 100 / n if n else None, "pct_idosos": (t["ido"] or 0) * 100 / n if n else None,
            "leitos_sus": r["leitos_sus"], "leitos_10k": r["leitos_sus_10k"], "ubs": r["ubs"],
            "ubs_10k": r["ubs_10k"], "hospitais": r["hospitais_sih"], "pct_atraidos": r["pct_atraidos"],
            "int_occ_ano": r["int_occ_ano"], "ocupacao": r["ocupacao_est"],
            "mensal": mensal, "caps": caps, "faixa": faixa}


FAIXAS = ["0-4", "5-14", "15-29", "30-44", "45-59", "60-74", "75+"]


def comparar_municipios(p: dict) -> dict:
    cods = (p.get("municipios") or [350950, 354340])[:3]
    if len(cods) < 2:
        cods = cods + [c for c in (355030, 350950) if c not in cods][:1]
    perf = [_perfil_mun(int(c), p) for c in cods]
    nomes = [x["nome"] for x in perf]
    _, _, _, desc = filtro({k: v for k, v in p.items() if k in ("ano",)})
    linhas = [{"type": "scatter", "mode": "lines+markers", "name": x["nome"],
               "x": [mes_label(m) for m in x["mensal"]["mes_inter"]],
               "y": _list(x["mensal"]["n"] * 1000 / x["pop"]), "colorSlot": i,
               "hovertemplate": "%{x}: %{y:.2f} por 1.000 hab.<extra>" + x["nome"] + "</extra>"}
              for i, x in enumerate(perf)]
    top_caps = (pd.concat([x["caps"].assign(pct=x["caps"]["n"] * 100 / x["n"]) for x in perf])
                  .groupby("cap_nome")["pct"].mean().sort_values(ascending=False).head(8).index)
    barras_cap = []
    for i, x in enumerate(perf):
        c = x["caps"].set_index("cap_nome")["n"].reindex(top_caps).fillna(0) * 100 / x["n"]
        barras_cap.append(bar_h(top_caps, c.values, slot=i, name=x["nome"],
                                hover="%{y}: %{x:.1f}%<extra>" + x["nome"] + "</extra>"))
    barras_faixa = []
    for i, x in enumerate(perf):
        f = x["faixa"].set_index("faixa_etaria")["n"].reindex(FAIXAS).fillna(0) * 100 / x["n"]
        barras_faixa.append({"type": "bar", "x": FAIXAS, "y": _list(f.values), "name": x["nome"],
                             "colorSlot": i, "hovertemplate": "%{x}: %{y:.1f}%<extra>" + x["nome"] + "</extra>"})
    charts = [
        chart("Internações por 1.000 habitantes, mês a mês", linhas, wide=True),
        chart("Perfil de causas (% das internações)", barras_cap,
              layout=bar_layout(8, barmode="group", xaxis={"ticksuffix": "%"}), height=420),
        chart("Faixa etária dos internados (%)", barras_faixa,
              layout={"barmode": "group", "yaxis": {"ticksuffix": "%"}}, height=420),
    ]
    ind = [("Região de Saúde", "regsaud", "text"), ("População", "pop", "int"),
           ("Internações/ano (residentes)", "n_ano", "int"), ("Internações por 1.000 hab.", "taxa", "dec1"),
           ("Permanência média (dias)", "perm", "dec1"), ("Valor médio por internação", "medio", "brl"),
           ("Mortalidade hospitalar (%)", "mort", "dec1"), ("% urgência", "pct_urg", "dec1"),
           ("% idosos (60+)", "pct_idosos", "dec1"), ("% internados fora do município", "pct_fora", "dec1"),
           ("Leitos SUS", "leitos_sus", "int"), ("Leitos SUS por 10 mil hab.", "leitos_10k", "dec1"),
           ("UBS", "ubs", "int"), ("UBS por 10 mil hab.", "ubs_10k", "dec2"),
           ("Internações realizadas no município/ano", "int_occ_ano", "int"),
           ("% pacientes de outros municípios", "pct_atraidos", "dec1")]
    rows = pd.DataFrame([{"indicador": lab, **{f"m{i}": _num(x[k]) if f != "text" else x[k]
                                               for i, x in enumerate(perf)}} for lab, k, f in ind])
    cols = [("indicador", "Indicador", "text")] + [(f"m{i}", n, "auto") for i, n in enumerate(nomes)]
    a, b = perf[0], perf[1]
    maior = a if a["taxa"] > b["taxa"] else b
    menor = b if maior is a else a
    insights = [
        f"{maior['nome']} interna {fmt_dec(maior['taxa'] / menor['taxa'], 1)}× mais por habitante que "
        f"{menor['nome']} ({fmt_dec(maior['taxa'], 1)} vs. {fmt_dec(menor['taxa'], 1)} por 1.000).",
        f"Leitos SUS por 10 mil hab.: {a['nome']} {fmt_dec(a['leitos_10k'], 1)} · {b['nome']} {fmt_dec(b['leitos_10k'], 1)}.",
        f"{a['nome']} recebe {fmt_pct(a['pct_atraidos'], 0)} de pacientes de fora; "
        f"{b['nome']}, {fmt_pct(b['pct_atraidos'], 0)}.",
    ]
    al = []
    for x in perf:
        al += [A.classificar("taxa", x["taxa"], onde=x["nome"]),
               A.classificar("leitos_10k", x["leitos_10k"], onde=x["nome"]),
               A.classificar("pct_fora", x["pct_fora"], onde=x["nome"])]
    return {"alertas": _ok(al), "title": "Comparação: " + " × ".join(nomes), "subtitle": "Indicadores pelo município de residência",
            "filtros": desc, "kpis": [kpi(x["nome"], fmt_dec(x["taxa"], 1) + " /1.000",
                                          f"{fmt_int(x['n_ano'])} internações/ano · {x['drs'].split(' - ')[0]}")
                                      for x in perf],
            "charts": charts, "insights": insights,
            "tables": [{**table("Indicadores lado a lado", rows, cols)}],
            "nota": "Digite outros nomes para comparar, por exemplo: \"compare Santos e Guarujá\"."}


def perfil_municipio(p: dict) -> dict:
    cod = int((p.get("municipios") or [355220])[0])
    x = _perfil_mun(cod, p)
    _, _, _, desc = filtro({k: v for k, v in p.items() if k in ("ano",)})
    hosp = _hospitais({**{k: v for k, v in p.items() if k in ("ano",)}, "municipios": [cod]}) \
        .sort_values("n", ascending=False).head(8)
    q = {k: v for k, v in p.items() if k in ("ano",)}
    join, where, args, _ = filtro(q, mun_col="mun_int")
    destinos = db.df(f"""SELECT m.nome, COUNT(*) n FROM fato_internacao a {join}
                         WHERE {where} AND a.mun_res = ? AND a.mun_int <> a.mun_res AND a.conta_internacao = 1
                         GROUP BY 1 ORDER BY 2 DESC LIMIT 8""", args + (cod,))
    caps = x["caps"].head(10)
    charts = [
        chart("Internações de residentes por mês", [{
            "type": "scatter", "mode": "lines+markers", "x": [mes_label(m) for m in x["mensal"]["mes_inter"]],
            "y": _list(x["mensal"]["n"]), "colorSlot": 0, "fill": "tozeroy",
            "hovertemplate": "%{x}: %{y:,.0f}<extra></extra>"}], layout={"yaxis": {"rangemode": "tozero"}}, wide=True),
        chart("Principais causas", [bar_h(caps["cap_nome"], caps["n"], text=[fmt_int(v) for v in caps["n"]],
                                          hover="%{y}: %{x:,.0f}<extra></extra>")],
              layout=bar_layout(len(caps)), height=bar_height(len(caps))),
    ]
    if len(hosp):
        charts.append(chart("Hospitais do município (internações/ano)", [bar_h(
            [_curto(n, 36) for n in hosp["nome"]], hosp["n_ano"], slot=2,
            text=[fmt_int(v) for v in hosp["n_ano"]], hover="%{y}: %{x:,.0f}/ano<extra></extra>")],
            layout=bar_layout(len(hosp)), height=bar_height(len(hosp))))
    if len(destinos):
        charts.append(chart("Para onde vão os residentes internados fora", [bar_h(
            destinos["nome"], destinos["n"], slot=1, text=[fmt_int(v) for v in destinos["n"]],
            hover="%{y}: %{x:,.0f} internações<extra></extra>")],
            layout=bar_layout(len(destinos)), height=bar_height(len(destinos))))
    taxa_est = db.scalar("SELECT SUM(int_res_ano) * 1000 / SUM(pop) FROM res_municipio")
    insights = [
        f"Taxa de {fmt_dec(x['taxa'], 1)} internações por 1.000 hab./ano "
        f"({'acima' if x['taxa'] > taxa_est else 'abaixo'} da média estadual de {fmt_dec(taxa_est, 1)}).",
        f"{fmt_pct(x['pct_fora'], 0)} dos residentes internados foram atendidos em outro município.",
        f"Principal causa: {caps.iloc[0]['cap_nome']} ({fmt_pct(caps.iloc[0]['n'] * 100 / x['n'], 0)}).",
    ]
    al = [A.classificar("taxa", x["taxa"]), A.classificar("permanencia", x["perm"]),
          A.classificar("mortalidade", x["mort"]), A.classificar("pct_fora", x["pct_fora"]),
          A.classificar("leitos_10k", x["leitos_10k"])]
    if x["leitos_sus"] and x["leitos_sus"] >= 10:
        al.append(A.classificar("ocupacao", x["ocupacao"]))
    return {"alertas": _ok(al), "title": f"Panorama de {x['nome']}", "subtitle": f"{x['drs']} · Região de Saúde {x['regsaud']}",
            "filtros": desc,
            "kpis": [kpi("População", fmt_compact(x["pop"])),
                     kpi("Internações/ano", fmt_compact(x["n_ano"]), "de residentes"),
                     kpi("Por 1.000 hab.", fmt_dec(x["taxa"], 1), f"estado: {fmt_dec(taxa_est, 1)}"),
                     kpi("Permanência média", fmt_dec(x["perm"], 1) + " dias"),
                     kpi("Leitos SUS", fmt_int(x["leitos_sus"]), fmt_dec(x["leitos_10k"], 1) + " por 10 mil hab."),
                     kpi("UBS", fmt_int(x["ubs"]), fmt_dec(x["ubs_10k"], 2) + " por 10 mil hab.")],
            "charts": charts, "insights": insights, "tables": [],
            "nota": "Digite \"mostre o panorama de <município>\" para ver outra cidade."}


def polos_atracao(p: dict) -> dict:
    top_n = p.get("top_n", 20)
    m = db.df("SELECT * FROM res_municipio WHERE int_occ > 0")
    if p.get("drs"):
        m = m[m["drs_num"] == int(p["drs"])]
    _, _, _, desc = filtro({k: v for k, v in p.items() if k == "drs"})
    m["atraidos_ano"] = m["atraidos"] / len(db.anos())
    top = m.sort_values("atraidos_ano", ascending=False).head(top_n)
    charts = [
        chart(f"Top {top_n}: internações de pacientes de outros municípios (por ano)", [bar_h(
            top["nome"], top["atraidos_ano"],
            text=[f"{fmt_compact(v)} · {fmt_pct(pc, 0)}" for v, pc in zip(top["atraidos_ano"], top["pct_atraidos"])],
            hover="%{y}: %{x:,.0f}/ano<extra></extra>")],
              subtitle="Rótulo: volume anual · % do total de internações do município",
              layout=bar_layout(len(top)), height=bar_height(len(top))),
        mapa_mun("Mapa dos polos (bolha = pacientes de outros municípios por ano)", m, "pct_atraidos",
                 "%{z:.0f}% das internações são de pacientes de fora", legenda="% de fora",
                 subtitle="Cor: % das internações do município feitas por pacientes de outras cidades",
                 base=_cods_regiao(p), extras=[{
                     "type": "scattergeo", "mode": "markers", "lon": _list(top["lon"]), "lat": _list(top["lat"]),
                     "text": list(top["nome"]), "customdata": _list(top["atraidos_ano"]), "colorSlot": 0,
                     "marker": {"size": _list(np.sqrt(top["atraidos_ano"]) / np.sqrt(top["atraidos_ano"].max()) * 34 + 6),
                                "opacity": 0.75},
                     "hovertemplate": "%{text}: %{customdata:,.0f} pacientes de fora/ano<extra></extra>"}]),
    ]
    insights = [
        f"{top.iloc[0]['nome']} recebe {fmt_int(top.iloc[0]['atraidos_ano'])} internações/ano de pacientes "
        f"de outros municípios ({fmt_pct(top.iloc[0]['pct_atraidos'], 0)} do seu total).",
        f"Os {top_n} polos concentram {fmt_pct(top['atraidos'].sum() * 100 / m['atraidos'].sum(), 0)} "
        "de todo o fluxo intermunicipal.",
        "Polos regionais (sedes de DRS com hospitais de referência) atendem a demanda de municípios "
        "pequenos sem estrutura hospitalar.",
    ]
    al = [A.classificar("ocupacao", r["ocupacao_est"], onde=r["nome"]) for _, r in top.head(3).iterrows()]
    al += _alertas_regiao(p, "pct_fora")
    return {"alertas": _ok(al), "title": "Polos que recebem pacientes de outras cidades", "subtitle": "Fluxo intermunicipal de internações",
            "filtros": desc, "charts": charts, "insights": insights,
            "kpis": [kpi("Maior polo", top.iloc[0]["nome"], fmt_compact(top.iloc[0]["atraidos_ano"]) + " pacientes/ano"),
                     kpi("Internações fora do município de residência",
                         fmt_pct(m["atraidos"].sum() * 100 / m["int_occ"].sum(), 0), "de todas as internações")],
            "tables": [table("Saldo de fluxo por município", top,
                             [("nome", "Município", "text"), ("drs_nome", "DRS", "text"),
                              ("atraidos_ano", "Pacientes de fora/ano", "int"),
                              ("pct_atraidos", "% do total", "pct"),
                              ("saldo_fluxo", "Saldo (recebe − envia)/ano", "int"),
                              ("leitos_sus", "Leitos SUS", "int")])]}


# -------------------------------------------------------------- capacidade ---
def capacidade_municipios(p: dict) -> dict:
    top_n = p.get("top_n", 20)
    m = db.df("SELECT * FROM res_municipio")
    if p.get("drs"):
        m = m[m["drs_num"] == int(p["drs"])]
    _, _, _, desc = filtro({k: v for k, v in p.items() if k == "drs"})
    elig = m[(m["leitos_sus"] >= 20) & (m["pop"] >= 20000)].sort_values("int_por_leito", ascending=False)
    top = elig.head(top_n)
    est = m["int_occ_ano"].sum() / m["leitos_sus"].sum()
    ref = "da DRS" if p.get("drs") else "do estado"
    charts = [
        chart(f"Top {top_n}: internações por leito SUS/ano", [bar_h(
            top["nome"], top["int_por_leito"], text=[fmt_dec(v, 0) for v in top["int_por_leito"]],
            hover="%{y}: %{x:.0f} internações por leito/ano<extra></extra>")],
              subtitle=f"Municípios com 20.000+ hab. e 20+ leitos SUS · linha = média {ref} ({fmt_dec(est, 0)})",
              layout=bar_layout(len(top), shapes=[_vline(est)]), height=bar_height(len(top))),
        chart("Leitos SUS × internações realizadas por ano", [
            {"type": "scatter", "mode": "markers", "name": "Municípios", "x": _list(elig["leitos_sus"]),
             "y": _list(elig["int_occ_ano"]), "text": list(elig["nome"]), "colorRole": "muted",
             "hovertemplate": "%{text}<br>%{x:,.0f} leitos · %{y:,.0f}/ano<extra></extra>"},
            {"type": "scatter", "mode": "markers", "name": f"Top {top_n}", "x": _list(top["leitos_sus"]),
             "y": _list(top["int_occ_ano"]), "text": list(top["nome"]), "colorSlot": 0,
             "hovertemplate": "%{text}<br>%{x:,.0f} leitos · %{y:,.0f}/ano<extra></extra>"}],
              layout={"xaxis": {"type": "log", "title": {"text": "Leitos SUS (log)"}},
                      "yaxis": {"type": "log", "title": {"text": "Internações/ano (log)"}}}),
        mapa_mun("Mapa: internações por leito SUS/ano", m[m["leitos_sus"] > 0], "int_por_leito",
                 "%{z:.0f} internações por leito/ano", legenda="por leito",
                 subtitle="Municípios sem leito SUS aparecem em cinza", base=_cods_regiao(p)),
    ]
    insights = [
        f"{top.iloc[0]['nome']} tem {fmt_dec(top.iloc[0]['int_por_leito'], 0)} internações por leito SUS/ano, "
        f"{fmt_dec(top.iloc[0]['int_por_leito'] / est, 1)}× a média {ref} — giro de leito muito alto.",
        f"Média {ref}: {fmt_dec(m['leitos_sus'].sum() * 10000 / m['pop'].sum(), 1)} leitos SUS por 10 mil hab.",
        "Giro alto pode indicar sobrecarga ou perfil de internações curtas (ex.: maternidades e cirurgias "
        "de baixa complexidade); compare com a permanência média na tabela.",
    ]
    elig = _status_col(elig, "int_por_leito", "int_por_leito")
    crit = int((elig["situacao"] == "critico").sum())
    al = [A.classificar("int_por_leito", top.iloc[0]["int_por_leito"], onde=top.iloc[0]["nome"]),
          _rotulo(A.classificar("pct_mun_criticos", crit * 100 / max(len(elig), 1)),
                  f"Municípios com giro de leito crítico · {crit} de {len(elig)}")]
    al += _alertas_regiao(p, "ocupacao", "leitos_10k")
    return {"alertas": _ok(al), "title": "Municípios com mais internações por leito SUS", "subtitle": "Pressão sobre a estrutura hospitalar",
            "filtros": desc, "charts": charts, "insights": insights,
            "kpis": [kpi("Internações por leito/ano", fmt_dec(est, 0), "média " + ref),
                     kpi("Leitos SUS", fmt_compact(m["leitos_sus"].sum()), "média mensal (CNES)"),
                     kpi("Ocupação estimada", fmt_pct(m["dias_occ"].sum() / len(db.anos()) * 100 / (m["leitos_sus"].sum() * 365), 0),
                         ref)],
            "tables": [table("Capacidade por município", elig.head(100),
                             [("nome", "Município", "text"), ("drs_nome", "DRS", "text"),
                              ("leitos_sus", "Leitos SUS", "int"), ("leitos_sus_10k", "Leitos/10 mil hab.", "dec1"),
                              ("int_occ_ano", "Internações/ano", "int"), ("int_por_leito", "Internações/leito", "dec1"),
                              ("perm_media_occ", "Permanência (dias)", "dec1"), ("ocupacao_est", "Ocupação est. (%)", "dec1"),
                              ("situacao", "Situação", "status")])],
            "nota": "Ocupação estimada = dias de permanência ÷ (leitos SUS × 365). Aproximação: nem todo leito "
                    "SUS atende pacientes do SIH e a permanência é contada no mês de internação."}


def ocupacao_hospitais(p: dict) -> dict:
    top_n = p.get("top_n", 20)
    h = db.df("SELECT * FROM res_hospital WHERE leitos_sus >= 30 AND ocupacao_est IS NOT NULL")
    if p.get("drs"):
        h = h[h["drs_nome"] == nome_drs(p["drs"])]
    if p.get("municipios"):
        h = h[h["cod_mun"].isin([int(c) for c in p["municipios"]])]
    _, _, _, desc = filtro({k: v for k, v in p.items() if k == "drs"})
    h = h.sort_values("ocupacao_est", ascending=False)
    top = h.head(top_n)
    acima = (h["ocupacao_est"] >= 85).sum()
    charts = [
        chart(f"Top {top_n}: ocupação estimada dos leitos SUS", [bar_h(
            [_curto(f"{n} ({m})") for n, m in zip(top["nome"], top["municipio"])], top["ocupacao_est"],
            text=[fmt_pct(v, 0) for v in top["ocupacao_est"]],
            hover="%{y}: %{x:.0f}%<extra></extra>")],
              subtitle="Hospitais com 30+ leitos SUS · linha = 85%, referência usual de ocupação alta",
              layout=bar_layout(len(top), shapes=[_vline(85)], xaxis={"ticksuffix": "%"}),
              height=bar_height(len(top)), wide=True),
        chart("Leitos SUS × ocupação estimada", [{
            "type": "scatter", "mode": "markers", "x": _list(h["leitos_sus"]), "y": _list(h["ocupacao_est"]),
            "text": list(h["nome"]), "colorSlot": 0,
            "hovertemplate": "%{text}<br>%{x:,.0f} leitos · %{y:.0f}%<extra></extra>"}],
              layout={"xaxis": {"type": "log", "title": {"text": "Leitos SUS (log)"}},
                      "yaxis": {"ticksuffix": "%", "title": {"text": "Ocupação estimada"}},
                      "shapes": [_hline(85)]}, wide=True),
    ]
    insights = [
        f"{acima} de {len(h)} hospitais ({fmt_pct(acima * 100 / len(h), 0)}) têm ocupação estimada acima de 85%.",
        f"Mediana de ocupação: {fmt_pct(h['ocupacao_est'].median(), 0)}.",
        "Valores acima de 100% indicam que o hospital usa leitos não-SUS ou extras, ou cadastro de leitos "
        "desatualizado no CNES.",
    ]
    h = _status_col(h, "ocupacao", "ocupacao_est")
    al = [_rotulo(A.classificar("pct_hosp_criticos", acima * 100 / max(len(h), 1)),
                  f"Hospitais com ocupação crítica (>85%) · {acima} de {len(h)}"),
          A.classificar("ocupacao", h["ocupacao_est"].median(), onde="mediana dos hospitais"),
          A.classificar("ocupacao", top.iloc[0]["ocupacao_est"], onde=_curto(top.iloc[0]["nome"], 40))]
    return {"alertas": _ok(al), "title": "Hospitais com maior ocupação estimada", "subtitle": "Dias de permanência ÷ capacidade de leitos SUS",
            "filtros": _desc_mun(p, desc), "charts": charts, "insights": insights,
            "kpis": [kpi("Acima de 85%", fmt_int(acima), f"de {fmt_int(len(h))} hospitais"),
                     kpi("Ocupação mediana", fmt_pct(h["ocupacao_est"].median(), 0))],
            "tables": [table("Ocupação por hospital", h.head(100),
                             [("nome", "Hospital", "text"), ("municipio", "Município", "text"),
                              ("leitos_sus", "Leitos SUS", "int"), ("leitos_uti_sus", "Leitos UTI SUS", "int"),
                              ("internacoes_ano", "Internações/ano", "int"), ("perm_media", "Permanência (dias)", "dec1"),
                              ("ocupacao_est", "Ocupação est. (%)", "dec1"), ("situacao", "Situação", "status"),
                              ("telefone", "Telefone", "text")])],
            "nota": "Estimativa a partir do SIH (dias de permanência) e do CNES-LT (leitos SUS médios no período)."}


def capacidade_drs(p: dict) -> dict:
    m = db.df("SELECT * FROM res_municipio")
    g = m.groupby("drs_nome").agg(pop=("pop", "sum"), leitos=("leitos_sus", "sum"), ubs=("ubs", "sum"),
                                  int_res=("int_res_ano", "sum"), int_occ=("int_occ_ano", "sum"),
                                  dias=("dias_occ", "sum"), uti=("leitos_uti_sus", "sum"),
                                  hosp=("hospitais", "sum")).reset_index()
    na = len(db.anos())
    g["leitos_10k"] = g["leitos"] * 10000 / g["pop"]
    g["uti_10k"] = g["uti"] * 10000 / g["pop"]
    g["ubs_10k"] = g["ubs"] * 10000 / g["pop"]
    g["taxa"] = g["int_res"] * 1000 / g["pop"]
    g["ocup"] = g["dias"] / na * 100 / (g["leitos"] * 365)
    g["perm"] = g["dias"] / na / g["int_occ"]
    g["cobertura"] = g["int_occ"] * 100 / g["int_res"]
    g = g.sort_values("drs_nome", key=lambda s: s.map(_romano))
    mens = db.df("""SELECT mes_inter, SUM(dias_perm) d, SUM(leitos_sus) l FROM res_capacidade_drs_mensal
                    GROUP BY 1 ORDER BY 1""")
    mens["ocup"] = mens["d"] * 100 / (mens["l"] * pd.to_datetime(mens["mes_inter"] + "-01").dt.days_in_month)
    l10 = g.sort_values("leitos_10k", ascending=False)
    oc = g.sort_values("ocup", ascending=False)
    est_l10 = g["leitos"].sum() * 10000 / g["pop"].sum()
    charts = [
        chart("Leitos SUS por 10 mil habitantes", [bar_h(
            l10["drs_nome"], l10["leitos_10k"], text=[fmt_dec(v, 1) for v in l10["leitos_10k"]],
            hover="%{y}: %{x:.1f}<extra></extra>")],
              subtitle=f"Linha = estado ({fmt_dec(est_l10, 1)})",
              layout=bar_layout(len(g), shapes=[_vline(est_l10)]), height=bar_height(len(g))),
        chart("Ocupação estimada dos leitos SUS", [bar_h(
            oc["drs_nome"], oc["ocup"], slot=1, text=[fmt_pct(v, 0) for v in oc["ocup"]],
            hover="%{y}: %{x:.0f}%<extra></extra>")],
              layout=bar_layout(len(g), xaxis={"ticksuffix": "%"}), height=bar_height(len(g))),
        chart("Ocupação estimada mês a mês (estado)", [{
            "type": "scatter", "mode": "lines+markers", "x": [mes_label(x) for x in mens["mes_inter"]],
            "y": _list(mens["ocup"]), "colorSlot": 0,
            "hovertemplate": "%{x}: %{y:.1f}%<extra></extra>"}],
              layout={"yaxis": {"ticksuffix": "%"}}, wide=True),
    ]
    insights = [
        f"{l10.iloc[0]['drs_nome']} tem a maior oferta ({fmt_dec(l10.iloc[0]['leitos_10k'], 1)} leitos SUS/10 mil hab.); "
        f"{l10.iloc[-1]['drs_nome']} a menor ({fmt_dec(l10.iloc[-1]['leitos_10k'], 1)}).",
        f"{oc.iloc[0]['drs_nome']} tem a maior ocupação estimada ({fmt_pct(oc.iloc[0]['ocup'], 0)}).",
        "Cobertura > 100% (tabela) = a DRS interna mais pacientes do que gera: recebe gente de outras regiões.",
    ]
    g = _status_col(g, "ocupacao", "ocup")
    al = _alertas_regiao({}, "ocupacao", "leitos_10k")
    al += [A.classificar("ocupacao", oc.iloc[0]["ocup"], onde=oc.iloc[0]["drs_nome"].split(" - ")[0]),
           A.classificar("leitos_10k", l10.iloc[-1]["leitos_10k"], onde=l10.iloc[-1]["drs_nome"].split(" - ")[0])]
    return {"alertas": _ok(al), "title": "Estrutura hospitalar por DRS", "subtitle": "Leitos, UBS, ocupação e cobertura", "filtros": [],
            "kpis": [kpi("Leitos SUS/10 mil hab.", fmt_dec(est_l10, 1), "estado"),
                     kpi("Leitos de UTI SUS/10 mil hab.", fmt_dec(g["uti"].sum() * 10000 / g["pop"].sum(), 2)),
                     kpi("UBS/10 mil hab.", fmt_dec(g["ubs"].sum() * 10000 / g["pop"].sum(), 2)),
                     kpi("Ocupação estimada", fmt_pct(g["dias"].sum() / na * 100 / (g["leitos"].sum() * 365), 0))],
            "charts": charts, "insights": insights,
            "tables": [table("Indicadores por DRS", g,
                             [("drs_nome", "DRS", "text"), ("pop", "População", "int"),
                              ("leitos", "Leitos SUS", "int"), ("leitos_10k", "Leitos/10 mil", "dec1"),
                              ("uti_10k", "UTI/10 mil", "dec2"), ("ubs_10k", "UBS/10 mil", "dec2"),
                              ("taxa", "Internações/1.000 hab.", "dec1"), ("perm", "Permanência (dias)", "dec1"),
                              ("ocup", "Ocupação est. (%)", "dec1"), ("cobertura", "Cobertura (%)", "dec1"),
                              ("situacao", "Situação", "status")])]}


# ------------------------------------------------------- padrões e fatores ---
def ubs_internacoes(p: dict) -> dict:
    m = db.df("SELECT * FROM res_municipio WHERE pop >= 5000 AND int_res > 0")
    if p.get("drs"):
        m = m[m["drs_num"] == int(p["drs"])]
    _, _, _, desc = filtro({k: v for k, v in p.items() if k == "drs"})
    from scipy.stats import spearmanr
    rho, pval = spearmanr(m["ubs_10k"], m["taxa_int_1k"])
    m["faixa_ubs"] = pd.qcut(m["ubs_10k"], 5, labels=["Q1 (menor)", "Q2", "Q3", "Q4", "Q5 (maior)"])
    q = m.groupby("faixa_ubs", observed=True).agg(
        taxa=("taxa_int_1k", "median"), ubs=("ubs_10k", "median"), n=("cod_mun", "count"),
        pop=("pop", "median"), fora=("pct_fora", "median")).reset_index()
    b, a = np.polyfit(m["ubs_10k"], m["taxa_int_1k"], 1)
    xs = np.linspace(m["ubs_10k"].min(), m["ubs_10k"].quantile(0.99), 20)
    charts = [
        chart("UBS por 10 mil hab. × internações por 1.000 hab.", [
            {"type": "scatter", "mode": "markers", "name": "Municípios", "x": _list(m["ubs_10k"]),
             "y": _list(m["taxa_int_1k"]), "text": list(m["nome"]), "colorSlot": 0,
             "hovertemplate": "%{text}<br>%{x:.2f} UBS/10 mil · %{y:.1f}/1.000<extra></extra>"},
            {"type": "scatter", "mode": "lines", "name": "Tendência linear", "x": _list(xs),
             "y": _list(a + b * xs), "colorRole": "muted", "hoverinfo": "skip"}],
              subtitle=f"Municípios com 5.000+ hab. · Spearman ρ = {fmt_dec(rho, 2)}",
              layout={"xaxis": {"title": {"text": "UBS por 10 mil hab."}},
                      "yaxis": {"title": {"text": "Internações/1.000 hab."}}}, wide=True),
        chart("Taxa de internação mediana por quintil de cobertura de UBS", [{
            "type": "bar", "x": list(q["faixa_ubs"].astype(str)), "y": _list(q["taxa"]), "colorSlot": 0,
            "text": [fmt_dec(v, 1) for v in q["taxa"]], "textposition": "outside", "cliponaxis": False,
            "hovertemplate": "%{x}: %{y:.1f}/1.000<extra></extra>"}]),
        chart("Porte (população mediana) por quintil de UBS", [{
            "type": "bar", "x": list(q["faixa_ubs"].astype(str)), "y": _list(q["pop"]), "colorSlot": 1,
            "text": [fmt_compact(v) for v in q["pop"]], "textposition": "outside", "cliponaxis": False,
            "hovertemplate": "%{x}: %{y:,.0f} hab.<extra></extra>"}]),
        mapa_mun("Mapa: UBS por 10 mil habitantes", m, "ubs_10k", "%{z:.1f} UBS por 10 mil hab.", legenda="UBS/10 mil",
                 subtitle="Municípios com 5.000+ hab.; os menores aparecem em cinza", base=_cods_regiao(p)),
    ]
    sentido = "maior" if rho > 0 else "menor"
    insights = [
        f"Correlação {'positiva' if rho > 0 else 'negativa'} (ρ = {fmt_dec(rho, 2)}): municípios com mais UBS por "
        f"habitante tendem a ter taxa de internação {sentido}.",
        "Atenção ao porte: municípios pequenos têm mais UBS por habitante (escala mínima) e também população "
        "mais idosa — fatores que confundem a relação. Veja \"Quais fatores estão associados ao aumento da demanda?\" "
        "para o efeito controlado.",
        f"Quintil com mais UBS: taxa mediana {fmt_dec(q.iloc[-1]['taxa'], 1)} vs. {fmt_dec(q.iloc[0]['taxa'], 1)} "
        "no quintil com menos.",
    ]
    al = _alertas_regiao(p, "pct_mun_criticos", "pct_fora", "leitos_10k")
    return {"alertas": _ok(al), "title": "UBS por habitante e internações", "subtitle": "Atenção primária × demanda hospitalar",
            "filtros": desc, "charts": charts, "insights": insights,
            "kpis": [kpi("Correlação (Spearman)", fmt_dec(rho, 2), "p < 0,001" if pval < 0.001 else f"p = {fmt_dec(pval, 3)}"),
                     kpi("Municípios", fmt_int(len(m)), "com 5.000+ hab."),
                     kpi("UBS no estado", fmt_int(db.scalar("SELECT COUNT(*) FROM dim_estabelecimento WHERE grupo='UBS'")),
                         "cadastro CNES (API)")],
            "tables": [table("Quintis de cobertura de UBS", q,
                             [("faixa_ubs", "Quintil", "text"), ("ubs", "UBS/10 mil (mediana)", "dec2"),
                              ("taxa", "Internações/1.000 (mediana)", "dec1"), ("pop", "População mediana", "int"),
                              ("fora", "% internados fora (mediana)", "dec1"), ("n", "Municípios", "int")])]}


def clusters(p: dict) -> dict:
    c = db.df("SELECT * FROM res_cluster_municipio")
    perf = db.df("SELECT * FROM res_cluster_perfil ORDER BY cluster")
    meta = db.df("SELECT * FROM res_cluster_meta").iloc[0]
    feats = ["taxa_int_1k", "perm_media", "valor_medio", "pct_urgencia", "pct_idosos", "pct_fora",
             "leitos_sus_10k", "ubs_10k", "log_pop", "amplitude_sazonal"]
    labels = ["Internações/1.000", "Permanência", "Valor médio", "% urgência", "% idosos",
              "% internados fora", "Leitos SUS/10 mil", "UBS/10 mil", "Porte (log pop.)", "Amplitude sazonal"]
    z = perf[feats].sub(c[feats].mean()).div(c[feats].std())
    nomes = [f"Grupo {int(k)}" for k in perf["cluster"]]
    simbolos = ["circle", "square", "diamond", "triangle-up"]
    pontos = []
    for i, row in perf.iterrows():
        g = c[c["cluster"] == row["cluster"]]
        base = {"type": "scatter", "mode": "markers", "name": f"Grupo {int(row['cluster'])}",
                "text": list(g["nome"]), "colorSlot": i, "marker": {"symbol": simbolos[i % 4]}}
        pontos.append({**base, "x": _list(g["pc1"]), "y": _list(g["pc2"]),
                       "hovertemplate": "%{text}<extra>Grupo " + str(int(row["cluster"])) + "</extra>"})
    charts = [
        chart("Municípios no espaço das duas componentes principais (PCA)", pontos,
              subtitle=f"PC1 explica {fmt_pct(meta['pc1_var'] * 100, 0)} e PC2 {fmt_pct(meta['pc2_var'] * 100, 0)} da variância",
              layout={"xaxis": {"title": {"text": "PC1"}}, "yaxis": {"title": {"text": "PC2"}}}),
        mapa_mun("Onde ficam os grupos", c.assign(idx=c["cluster"].map({k: i for i, k in enumerate(perf["cluster"])})),
                 "idx", "%{customdata}", categorias=nomes),
        chart("Perfil de cada grupo (desvio em relação à média dos municípios)", [{
            "type": "heatmap", "z": [[_num(v) for v in row] for row in z.values.T], "x": nomes, "y": labels,
            "scale": "diverging", "zmid": 0, "xgap": 2, "ygap": 2, "colorbar": {"thickness": 10, "title": {"text": "z"}},
            "hovertemplate": "%{y} · %{x}: %{z:+.2f} desvios-padrão<extra></extra>"}],
              layout={"yaxis": {"autorange": "reversed", "automargin": True}}, height=420, wide=True),
    ]
    insights = [f"Grupo {int(r['cluster'])} ({int(r['n_municipios'])} municípios, {fmt_compact(r['populacao'])} hab.): "
                f"{r['nome']} — taxa média de {fmt_dec(r['taxa_int_1k'], 1)} internações/1.000 hab."
                for _, r in perf.iterrows()]
    al = []
    for _, r in perf.iterrows():
        g = f"Grupo {int(r['cluster'])}"
        al += [A.classificar("taxa", r["taxa_int_1k"], onde=g), A.classificar("pct_fora", r["pct_fora"], onde=g),
               A.classificar("leitos_10k", r["leitos_sus_10k"], onde=g)]
    return {"alertas": _ok(al), "title": "Grupos de municípios com perfis de demanda parecidos",
            "subtitle": f"K-means com {int(meta['k'])} grupos sobre 10 indicadores padronizados", "filtros": [],
            "kpis": [kpi(f"Grupo {int(r['cluster'])}", f"{int(r['n_municipios'])} municípios", r["nome"])
                     for _, r in perf.iterrows()],
            "charts": charts, "insights": insights,
            "tables": [table("Municípios e grupos", c.sort_values(["cluster", "pop"], ascending=[True, False]),
                             [("nome", "Município", "text"), ("drs_nome", "DRS", "text"), ("cluster", "Grupo", "int"),
                              ("pop", "População", "int"), ("taxa_int_1k", "Internações/1.000", "dec1"),
                              ("perm_media", "Permanência", "dec1"), ("pct_fora", "% internados fora", "dec1"),
                              ("leitos_sus_10k", "Leitos/10 mil", "dec1"), ("ubs_10k", "UBS/10 mil", "dec2")])],
            "nota": f"Variáveis: {meta['features']}. Padronizadas (z-score) após winsorização 1–99%. "
                    f"k escolhido pela silhueta ({fmt_dec(meta['silhueta'], 2)})."}


def fatores(p: dict) -> dict:
    f = db.df("SELECT * FROM res_fatores").sort_values("coef")
    r2, n = f["r2"].iloc[0], int(f["n"].iloc[0])
    sig = f[f["p_coef"] < 0.05].sort_values("coef", ascending=False)
    fs = f.sort_values("spearman")
    charts = [
        chart("Efeito de cada fator na taxa de internação (regressão)", [{
            "type": "bar", "orientation": "h", "y": list(f["rotulo"]), "x": _list(f["coef"]),
            "colorByValue": "diverging",
            "error_x": {"type": "data", "symmetric": False, "array": _list(f["ci_high"] - f["coef"]),
                        "arrayminus": _list(f["coef"] - f["ci_low"])},
            "customdata": _list(f["p_coef"]),
            "hovertemplate": "%{y}: %{x:+.2f} DP (p = %{customdata:.3f})<extra></extra>"}],
              subtitle="Coeficientes padronizados com IC 95%: quanto a taxa muda (em desvios-padrão) "
                       "quando o fator sobe 1 desvio-padrão, mantidos os demais constantes",
              layout={"yaxis": {"automargin": True}, "xaxis": {"zeroline": True}},
              height=bar_height(len(f)), wide=True),
        chart("Correlação simples (Spearman) com a taxa de internação", [{
            "type": "bar", "orientation": "h", "y": list(fs["rotulo"]), "x": _list(fs["spearman"]),
            "colorByValue": "diverging", "text": [("+" if v > 0 else "−") + fmt_dec(abs(v), 2) for v in fs["spearman"]],
            "textposition": "outside", "cliponaxis": False,
            "hovertemplate": "%{y}: ρ = %{x:+.2f}<extra></extra>"}],
              layout={"yaxis": {"automargin": True}, "xaxis": {"range": [-1, 1], "zeroline": True}},
              height=bar_height(len(fs)), wide=True),
    ]
    insights = []
    for _, r in sig.iterrows():
        insights.append(f"{r['rotulo']}: associado a taxa de internação {'maior' if r['coef'] > 0 else 'menor'} "
                        f"({'+' if r['coef'] > 0 else '−'}{fmt_dec(abs(r['coef']), 2)} DP, p = {fmt_dec(r['p_coef'], 3)}).")
    insights.append(f"O modelo explica {fmt_pct(r2 * 100, 0)} da variação da taxa entre {n} municípios "
                    "(5.000+ hab.). É uma associação: não prova causa.")
    insights.append("Hipótese: a associação positiva com leitos e UBS pode indicar demanda reprimida onde "
                    "há pouca estrutura (a população interna menos quando o acesso é difícil).")
    al = _alertas_regiao({}, "pct_mun_criticos", "leitos_10k", "ocupacao")
    return {"alertas": _ok(al), "title": "Fatores associados ao aumento da demanda",
            "subtitle": "Taxa de internação por 1.000 hab. (município de residência)", "filtros": [],
            "kpis": [kpi("R² do modelo", fmt_dec(r2, 2), "regressão ponderada pela população"),
                     kpi("Municípios", fmt_int(n), "com 5.000+ hab."),
                     kpi("Fator significativo mais forte",
                         sig.iloc[sig["coef"].abs().argmax()]["rotulo"] if len(sig) else "nenhum",
                         (("+" if sig.iloc[sig["coef"].abs().argmax()]["coef"] > 0 else "−")
                          + fmt_dec(abs(sig.iloc[sig["coef"].abs().argmax()]["coef"]), 2) + " DP (p < 0,05)")
                         if len(sig) else "")],
            "charts": charts, "insights": insights,
            "tables": [table("Coeficientes e correlações", f.sort_values("coef", key=abs, ascending=False),
                             [("rotulo", "Fator", "text"), ("coef", "Coef. padronizado", "dec2"),
                              ("ci_low", "IC 95% inf.", "dec2"), ("ci_high", "IC 95% sup.", "dec2"),
                              ("p_coef", "p-valor", "dec3"), ("spearman", "Spearman ρ", "dec2")])],
            "nota": "Regressão linear ponderada (WLS, peso = √população) com erros robustos HC3 e variáveis "
                    "padronizadas. Dados: SIH/SUS (internações), CNES (leitos, UBS), IBGE (população)."}


BUILDERS: dict[str, Callable[[dict], dict]] = {
    "visao_geral": visao_geral, "custos": custos,
    "sazonal_estado": sazonal_estado, "sazonal_drs": sazonal_drs, "sazonal_causas": sazonal_causas,
    "sazonal_cap_regiao": sazonal_cap_regiao,
    "ranking_municipios": ranking_municipios, "ranking_hospitais": ranking_hospitais,
    "ranking_permanencia": ranking_permanencia, "comparar_municipios": comparar_municipios,
    "perfil_municipio": perfil_municipio, "polos_atracao": polos_atracao,
    "capacidade_municipios": capacidade_municipios, "ocupacao_hospitais": ocupacao_hospitais,
    "capacidade_drs": capacidade_drs,
    "ubs_internacoes": ubs_internacoes, "clusters": clusters, "fatores": fatores,
}


@lru_cache(maxsize=256)
def _montar(question_id: str, chave: str) -> dict:
    """Dashboard sem a query (que depende do texto da pergunta). Fica em cache: não alterar."""
    out = BUILDERS[question_id](json.loads(chave))
    out.setdefault("alertas", [])
    out["status_geral"] = A.pior(out["alertas"])
    out["relevancia"] = R.secao(question_id, out["alertas"])
    out["seguintes"] = [{"id": i, "texto": POR_ID[i].texto} for i in SEGUINTES[question_id]]
    out.setdefault("nota", "")
    out.setdefault("tables", [])
    return out


def build(question_id: str, params: dict, pergunta: str | None = None) -> dict:
    chave = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return {**_montar(question_id, chave), "sql": oracle_sql(question_id, params, pergunta)}
