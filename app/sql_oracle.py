"""Query SQL equivalente (dialeto Oracle) de cada dashboard.

SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.

O app roda em SQLite, mas o modelo relacional é o mesmo do projeto entregue
(tabelas fato_internacao, agg_mensal_hosp, agg_mensal_res, fato_leitos,
dim_municipio, dim_estabelecimento, dim_cid_capitulo — DDL em sql/oracle_schema.sql).
Cada função devolve as queries que alimentam os blocos do dashboard, com os
filtros da pergunta já aplicados. Os valores dos filtros entram como literais
validados (inteiros e códigos do catálogo); texto livre do usuário nunca entra no SQL.
"""
from __future__ import annotations

import re
from typing import Callable

from app.questions import POR_ID

CARATER_OK = {"Eletivo", "Urgência"}
POP_MEDIA = "(m.pop_2024 + m.pop_2025) / 2"


# ------------------------------------------------------------------ filtros --
def _limpa(p: dict) -> dict:
    """Mantém só valores seguros para virar literal SQL."""
    out = {}
    if str(p.get("ano", "")).isdigit():
        out["ano"] = int(p["ano"])
    if str(p.get("drs", "")).isdigit():
        out["drs"] = int(p["drs"])
    if re.fullmatch(r"[IVX]{1,5}", str(p.get("cap_cid", ""))):
        out["cap_cid"] = p["cap_cid"]
    if p.get("carater") in CARATER_OK:
        out["carater"] = p["carater"]
    mun = [int(c) for c in p.get("municipios", []) if str(c).isdigit()]
    if mun:
        out["municipios"] = mun
    out["top_n"] = max(3, min(50, int(p.get("top_n") or 0))) if str(p.get("top_n", "")).isdigit() else None
    return out


def _preds(p: dict, *, alias="a", ano=True, drs=True, cap=True, carater=True) -> list[str]:
    w = []
    if ano and p.get("ano"):
        w.append(f"SUBSTR({alias}.mes_inter, 1, 4) = '{p['ano']}'")
    if drs and p.get("drs"):
        w.append(f"m.drs_num = {p['drs']}")
    if cap and p.get("cap_cid"):
        w.append(f"{alias}.cap_cid = '{p['cap_cid']}'")
    if carater and p.get("carater"):
        w.append(f"{alias}.carater = '{p['carater']}'")
    return w


def _where(preds: list[str], indent: str = "") -> str:
    if not preds:
        return ""
    return f"\n{indent}WHERE " + f"\n{indent}  AND ".join(preds)


def _anos(p: dict) -> int:
    return 1 if p.get("ano") else 2


def _pop(p: dict) -> str:
    return f"m.pop_{p['ano']}" if p.get("ano") else POP_MEDIA


def _bloco(titulo: str, sql: str) -> dict:
    return {"titulo": titulo, "sql": sql.strip() + ";"}


def _leitos_cte(chave: str = "cnes") -> str:
    """Média mensal de leitos SUS no período (fato_leitos tem uma linha por competência)."""
    return f"""leitos AS (
    SELECT {chave}, AVG(sus) AS leitos_sus, AVG(uti) AS leitos_uti_sus
    FROM (SELECT {chave}, competencia,
                 SUM(qt_sus) AS sus,
                 SUM(CASE WHEN tp_leito LIKE 'Complementar%' THEN qt_sus ELSE 0 END) AS uti
          FROM fato_leitos
          GROUP BY {chave}, competencia)
    GROUP BY {chave}
)"""


def _status(expr: str, a: float, b: float, maior_pior: bool = True) -> str:
    if maior_pior:
        return (f"CASE WHEN {expr} > {b} THEN 'Crítico' WHEN {expr} > {a} THEN 'Alerta' "
                f"ELSE 'Aceitável' END")
    return (f"CASE WHEN {expr} < {b} THEN 'Crítico' WHEN {expr} < {a} THEN 'Alerta' "
            f"ELSE 'Aceitável' END")


def _sazonal(chave: str, p: dict, *, extra_where: list[str] | None = None, joins: str = "") -> str:
    """Índice sazonal: internações do mês ÷ média mensal do ano, média dos anos."""
    preds = _preds(p, ano=False) + (extra_where or [])
    return f"""
WITH mensal AS (
    SELECT {chave} AS chave,
           SUBSTR(a.mes_inter, 1, 4)            AS ano,
           TO_NUMBER(SUBSTR(a.mes_inter, 6, 2)) AS mes,
           SUM(a.internacoes)                   AS internacoes
    FROM agg_mensal_hosp a
    JOIN dim_municipio m ON m.cod_mun = a.mun_int{joins}{_where(preds, '    ')}
    GROUP BY {chave}, SUBSTR(a.mes_inter, 1, 4), TO_NUMBER(SUBSTR(a.mes_inter, 6, 2))
),
indice AS (
    SELECT chave, mes,
           internacoes / AVG(internacoes) OVER (PARTITION BY chave, ano) AS indice
    FROM mensal
)
SELECT chave,
       mes,
       ROUND(100 * (AVG(indice) - 1), 1) AS pct_vs_media_do_ano,
       {_status('100 * (AVG(indice) - 1)', 10, 25)} AS situacao
FROM indice
GROUP BY chave, mes
ORDER BY chave, mes"""


# ---------------------------------------------------------------- queries ----
def visao_geral(p):
    w = _preds(p)
    base = "FROM agg_mensal_hosp a\nJOIN dim_municipio m ON m.cod_mun = a.mun_int"
    return [
        _bloco("Indicadores (KPIs)", f"""
SELECT SUM(a.internacoes)                                              AS internacoes,
       ROUND(SUM(a.internacoes) / {_anos(p)})                                   AS internacoes_por_ano,
       ROUND(SUM(a.valor_total), 2)                                    AS valor_pago,
       ROUND(SUM(a.valor_total) / NULLIF(SUM(a.internacoes), 0), 2)   AS valor_medio,
       ROUND(SUM(a.dias_perm) / NULLIF(SUM(a.internacoes), 0), 2)     AS permanencia_media,
       ROUND(100 * SUM(CASE WHEN a.carater = 'Urgência' THEN a.internacoes ELSE 0 END)
                 / NULLIF(SUM(a.internacoes), 0), 1)                   AS pct_urgencia,
       ROUND(100 * SUM(a.obitos) / NULLIF(SUM(a.internacoes), 0), 2)  AS mortalidade_pct
{base}{_where(w)}"""),
        _bloco("Internações por mês", f"""
SELECT a.mes_inter, SUM(a.internacoes) AS internacoes
{base}{_where(w)}
GROUP BY a.mes_inter
ORDER BY a.mes_inter"""),
        _bloco("Principais causas (CID-10)", f"""
SELECT c.cap_nome,
       SUM(a.internacoes) AS internacoes,
       ROUND(100 * RATIO_TO_REPORT(SUM(a.internacoes)) OVER (), 1) AS pct_do_total
{base}
JOIN dim_cid_capitulo c ON c.cap_cod = a.cap_cid{_where(w)}
GROUP BY c.cap_nome
ORDER BY internacoes DESC
FETCH FIRST 10 ROWS ONLY"""),
        _bloco("Internações por DRS", f"""
SELECT m.drs_nome,
       SUM(a.internacoes) AS internacoes,
       ROUND(100 * RATIO_TO_REPORT(SUM(a.internacoes)) OVER (), 1) AS pct_do_total
{base}{_where(w)}
GROUP BY m.drs_nome
ORDER BY internacoes DESC"""),
    ]


def custos(p):
    w = _preds(p, cap=False)
    return [_bloco("Valor pago por causa (CID-10)", f"""
SELECT c.cap_nome,
       ROUND(SUM(a.valor_total), 2)                                   AS valor_total,
       ROUND(100 * RATIO_TO_REPORT(SUM(a.valor_total)) OVER (), 1)    AS pct_do_total,
       SUM(a.internacoes)                                             AS internacoes,
       ROUND(SUM(a.valor_total) / NULLIF(SUM(a.internacoes), 0), 2)  AS valor_medio,
       ROUND(SUM(a.dias_perm) / NULLIF(SUM(a.internacoes), 0), 1)    AS permanencia_media
FROM agg_mensal_hosp a
JOIN dim_municipio m    ON m.cod_mun  = a.mun_int
JOIN dim_cid_capitulo c ON c.cap_cod  = a.cap_cid{_where(w)}
GROUP BY c.cap_nome
ORDER BY valor_total DESC""")]


def sazonal_estado(p):
    w = _preds(p, ano=False)
    return [
        _bloco("Série mensal", f"""
SELECT a.mes_inter, SUM(a.internacoes) AS internacoes
FROM agg_mensal_hosp a
JOIN dim_municipio m ON m.cod_mun = a.mun_int{_where(w)}
GROUP BY a.mes_inter
ORDER BY a.mes_inter
-- tendência (decomposição STL) calculada em Python (statsmodels)"""),
        _bloco("Índice sazonal por mês", _sazonal("'Estado de SP'", p)),
    ]


def sazonal_drs(p):
    q = {k: v for k, v in p.items() if k != "drs"}
    return [_bloco("Índice sazonal por DRS", _sazonal("m.drs_nome", q))]


def sazonal_causas(p):
    q = {k: v for k, v in p.items() if k != "cap_cid"}
    return [_bloco("Índice sazonal por capítulo da CID-10",
                   _sazonal("c.cap_nome", q, extra_where=["a.cap_cid <> 'XXII'"],
                            joins="\n    JOIN dim_cid_capitulo c ON c.cap_cod = a.cap_cid"))]


def sazonal_cap_regiao(p):
    cap = p.get("cap_cid", "X")
    q = {k: v for k, v in p.items() if k not in ("drs", "cap_cid")}
    return [
        _bloco(f"Índice sazonal da causa {cap} no estado",
               _sazonal("'Estado de SP'", q, extra_where=[f"a.cap_cid = '{cap}'"])),
        _bloco(f"Índice sazonal da causa {cap} por DRS",
               _sazonal("m.drs_nome", q, extra_where=[f"a.cap_cid = '{cap}'"])),
    ]


def _taxa_municipios(p, *, min_pop: int, top_n: int | None, extra: str = "") -> str:
    w = _preds(p)
    top = f"\nFETCH FIRST {top_n} ROWS ONLY" if top_n else ""
    return f"""
WITH residentes AS (
    SELECT a.mun_res,
           SUM(a.internacoes)     AS internacoes,
           SUM(a.dias_perm)       AS dias_perm,
           SUM(a.valor_total)     AS valor_total,
           SUM(a.internadas_fora) AS internadas_fora
    FROM agg_mensal_res a
    JOIN dim_municipio m ON m.cod_mun = a.mun_res{_where(w, '    ')}
    GROUP BY a.mun_res
),
taxas AS (
    SELECT m.nome, m.drs_nome,
           {_pop(p)}                                   AS populacao,
           r.internacoes / {_anos(p)}                             AS internacoes_ano,
           r.internacoes / {_anos(p)} * 1000 / ({_pop(p)})          AS taxa_1k,
           r.dias_perm / NULLIF(r.internacoes, 0)        AS permanencia,
           r.valor_total / NULLIF(r.internacoes, 0)      AS valor_medio,
           100 * r.internadas_fora / NULLIF(r.internacoes, 0) AS pct_internados_fora
    FROM residentes r
    JOIN dim_municipio m ON m.cod_mun = r.mun_res
),
referencia AS (  -- mediana dos municípios com 5 mil+ hab.
    SELECT MEDIAN(taxa_1k) AS mediana FROM taxas WHERE populacao >= 5000
)
SELECT t.nome, t.drs_nome,
       ROUND(t.populacao)           AS populacao,
       ROUND(t.internacoes_ano)     AS internacoes_ano,
       ROUND(t.taxa_1k, 1)          AS taxa_por_1000_hab,
       ROUND(t.permanencia, 1)      AS permanencia_media,
       ROUND(t.valor_medio, 2)      AS valor_medio,
       ROUND(t.pct_internados_fora, 1) AS pct_internados_fora,
       {_status('t.taxa_1k / r.mediana', 1.1, 1.3)} AS situacao
FROM taxas t CROSS JOIN referencia r
WHERE t.populacao >= {min_pop}{extra}
ORDER BY t.taxa_1k DESC{top}"""


def ranking_municipios(p):
    return [_bloco("Ranking de municípios por taxa de internação",
                   _taxa_municipios(p, min_pop=20000, top_n=p.get("top_n") or 20))]


def _hospitais(p, *, ordem: str, top_n: int, having: str = "") -> str:
    w = _preds(p)
    if p.get("municipios"):
        w.append(f"a.mun_int IN ({', '.join(map(str, p['municipios']))})")
    return f"""
WITH {_leitos_cte()}
SELECT a.cnes,
       NVL(MAX(e.nome), 'CNES ' || a.cnes)                              AS hospital,
       MAX(m.nome)                                                       AS municipio,
       MAX(JSON_VALUE(e.atributos_json, '$.descricao_turno_atendimento')) AS turno_atendimento,
       ROUND(SUM(a.internacoes) / {_anos(p)})                                     AS internacoes_ano,
       ROUND(SUM(a.dias_perm) / NULLIF(SUM(a.internacoes), 0), 1)       AS permanencia_media,
       ROUND(SUM(a.valor_total) / NULLIF(SUM(a.internacoes), 0), 2)     AS valor_medio,
       ROUND(100 * SUM(a.obitos) / NULLIF(SUM(a.internacoes), 0), 2)    AS mortalidade_pct,
       ROUND(MAX(l.leitos_sus))                                          AS leitos_sus
FROM agg_mensal_hosp a
JOIN dim_municipio m            ON m.cod_mun = a.mun_int
LEFT JOIN dim_estabelecimento e ON e.cnes    = a.cnes
LEFT JOIN leitos l              ON l.cnes    = a.cnes{_where(w)}
GROUP BY a.cnes{having}
ORDER BY {ordem} DESC
FETCH FIRST {top_n} ROWS ONLY"""


def ranking_hospitais(p):
    return [_bloco("Hospitais por volume de internações",
                   _hospitais(p, ordem="internacoes_ano", top_n=p.get("top_n") or 15))]


def ranking_permanencia(p):
    return [_bloco("Hospitais por permanência média (1.000+ internações/ano)",
                   _hospitais(p, ordem="permanencia_media", top_n=p.get("top_n") or 15,
                              having=f"\nHAVING SUM(a.internacoes) / {_anos(p)} >= 1000"))]


def _perfil(p, cods: list[int]) -> list[dict]:
    lista = ", ".join(map(str, cods))
    w = _preds(p, drs=False) + [f"a.mun_res IN ({lista})"]
    return [
        _bloco("Indicadores por município (residentes)", f"""
SELECT m.nome,
       ROUND({_pop(p)})                                                       AS populacao,
       ROUND(SUM(a.internacoes) / {_anos(p)})                                        AS internacoes_ano,
       ROUND(SUM(a.internacoes) / {_anos(p)} * 1000 / ({_pop(p)}), 1)                  AS taxa_por_1000_hab,
       ROUND(SUM(a.dias_perm) / NULLIF(SUM(a.internacoes), 0), 1)            AS permanencia_media,
       ROUND(100 * SUM(a.obitos) / NULLIF(SUM(a.internacoes), 0), 2)         AS mortalidade_pct,
       ROUND(100 * SUM(a.internadas_fora) / NULLIF(SUM(a.internacoes), 0), 1) AS pct_internados_fora,
       ROUND(100 * SUM(CASE WHEN a.faixa_etaria IN ('60-74', '75+') THEN a.internacoes ELSE 0 END)
                 / NULLIF(SUM(a.internacoes), 0), 1)                         AS pct_idosos
FROM agg_mensal_res a
JOIN dim_municipio m ON m.cod_mun = a.mun_res{_where(w)}
GROUP BY m.nome, {_pop(p)}"""),
        _bloco("Estrutura: leitos SUS e UBS por 10 mil hab.", f"""
WITH {_leitos_cte('cod_mun')},
ubs AS (
    SELECT cod_mun, COUNT(*) AS ubs
    FROM dim_estabelecimento
    WHERE grupo = 'UBS'
    GROUP BY cod_mun
)
SELECT m.nome,
       ROUND(l.leitos_sus)                                         AS leitos_sus,
       ROUND(l.leitos_sus * 10000 / ({POP_MEDIA}), 1)              AS leitos_sus_10k,
       {_status(f'l.leitos_sus * 10000 / ({POP_MEDIA})', 15, 10, maior_pior=False)} AS situacao_leitos,
       NVL(u.ubs, 0)                                               AS ubs,
       ROUND(NVL(u.ubs, 0) * 10000 / ({POP_MEDIA}), 2)             AS ubs_10k
FROM dim_municipio m
LEFT JOIN leitos l ON l.cod_mun = m.cod_mun
LEFT JOIN ubs u    ON u.cod_mun = m.cod_mun
WHERE m.cod_mun IN ({lista})"""),
        _bloco("Internações por mês (por 1.000 hab.)", f"""
SELECT m.nome, a.mes_inter,
       ROUND(SUM(a.internacoes) * 1000 / ({_pop(p)}), 2) AS internacoes_por_1000_hab
FROM agg_mensal_res a
JOIN dim_municipio m ON m.cod_mun = a.mun_res{_where(w)}
GROUP BY m.nome, a.mes_inter, {_pop(p)}
ORDER BY m.nome, a.mes_inter"""),
    ]


def comparar_municipios(p):
    cods = (p.get("municipios") or [350950, 354340])[:3]
    if len(cods) < 2:
        cods = cods + [c for c in (355030, 350950) if c not in cods][:1]
    return _perfil(p, cods)


def perfil_municipio(p):
    cod = (p.get("municipios") or [355220])[0]
    w = _preds(p, drs=False, cap=False, carater=False)
    return _perfil(p, [cod]) + [_bloco("Para onde vão os residentes internados fora", f"""
SELECT m.nome AS municipio_de_internacao, COUNT(*) AS internacoes
FROM fato_internacao a
JOIN dim_municipio m ON m.cod_mun = a.mun_int{_where(w + [f'a.mun_res = {cod}', 'a.mun_int <> a.mun_res', 'a.conta_internacao = 1'])}
GROUP BY m.nome
ORDER BY internacoes DESC
FETCH FIRST 8 ROWS ONLY""")]


def polos_atracao(p):
    w = _preds(p, cap=False, carater=False)
    return [_bloco("Municípios que mais recebem pacientes de outras cidades", f"""
WITH {_leitos_cte('cod_mun')}
SELECT m.nome, m.drs_nome,
       ROUND(SUM(a.residentes_fora) / {_anos(p)})                                AS pacientes_de_fora_ano,
       ROUND(100 * SUM(a.residentes_fora) / NULLIF(SUM(a.internacoes), 0), 1) AS pct_do_total,
       ROUND(MAX(l.leitos_sus))                                         AS leitos_sus,
       ROUND(100 * SUM(a.dias_perm) / {_anos(p)} / (MAX(l.leitos_sus) * 365), 1)  AS ocupacao_estimada_pct
FROM agg_mensal_hosp a
JOIN dim_municipio m ON m.cod_mun = a.mun_int
LEFT JOIN leitos l   ON l.cod_mun = a.mun_int{_where(w)}
GROUP BY m.nome, m.drs_nome
ORDER BY pacientes_de_fora_ano DESC
FETCH FIRST {p.get('top_n') or 20} ROWS ONLY""")]


def capacidade_municipios(p):
    drs = f"\n    WHERE m.drs_num = {p['drs']}" if p.get("drs") else ""
    return [_bloco("Internações por leito SUS e ocupação estimada", f"""
WITH {_leitos_cte('cod_mun')},
uso AS (
    SELECT a.mun_int AS cod_mun,
           SUM(a.internacoes) / 2 AS internacoes_ano,
           SUM(a.dias_perm)   / 2 AS dias_ano
    FROM agg_mensal_hosp a
    GROUP BY a.mun_int
),
base AS (
    SELECT m.nome, m.drs_nome, {POP_MEDIA} AS populacao, l.leitos_sus,
           u.internacoes_ano, u.dias_ano,
           u.internacoes_ano / NULLIF(l.leitos_sus, 0)       AS int_por_leito,
           100 * u.dias_ano / NULLIF(l.leitos_sus * 365, 0)  AS ocupacao_pct
    FROM dim_municipio m
    JOIN uso u    ON u.cod_mun = m.cod_mun
    JOIN leitos l ON l.cod_mun = m.cod_mun{drs}
),
referencia AS (
    SELECT SUM(internacoes_ano) / SUM(leitos_sus) AS media_estado FROM base
)
SELECT b.nome, b.drs_nome,
       ROUND(b.leitos_sus)                        AS leitos_sus,
       ROUND(b.leitos_sus * 10000 / b.populacao, 1) AS leitos_sus_10k,
       ROUND(b.internacoes_ano)                   AS internacoes_ano,
       ROUND(b.int_por_leito, 1)                  AS internacoes_por_leito,
       ROUND(b.ocupacao_pct, 1)                   AS ocupacao_estimada_pct,
       {_status('b.int_por_leito / r.media_estado', 1.3, 1.6)} AS situacao
FROM base b CROSS JOIN referencia r
WHERE b.leitos_sus >= 20 AND b.populacao >= 20000
ORDER BY b.int_por_leito DESC
FETCH FIRST {p.get('top_n') or 20} ROWS ONLY""")]


def ocupacao_hospitais(p):
    w = ["l.leitos_sus >= 30"]
    if p.get("drs"):
        w.append(f"m.drs_num = {p['drs']}")
    if p.get("municipios"):
        w.append(f"u.mun_int IN ({', '.join(map(str, p['municipios']))})")
    return [_bloco("Ocupação estimada dos leitos SUS por hospital", f"""
WITH {_leitos_cte()},
uso AS (
    SELECT cnes, MAX(mun_int) AS mun_int,
           SUM(dias_perm) / 2 AS dias_ano, SUM(internacoes) / 2 AS internacoes_ano
    FROM agg_mensal_hosp
    GROUP BY cnes
),
ocupacao AS (
    SELECT NVL(e.nome, 'CNES ' || u.cnes) AS hospital, m.nome AS municipio,
           e.telefone, l.leitos_sus, l.leitos_uti_sus, u.internacoes_ano,
           100 * u.dias_ano / (l.leitos_sus * 365) AS ocupacao_pct
    FROM uso u
    JOIN leitos l                   ON l.cnes    = u.cnes
    JOIN dim_municipio m            ON m.cod_mun = u.mun_int
    LEFT JOIN dim_estabelecimento e ON e.cnes    = u.cnes{_where(w, '    ')}
)
SELECT hospital, municipio,
       ROUND(leitos_sus)      AS leitos_sus,
       ROUND(leitos_uti_sus)  AS leitos_uti_sus,
       ROUND(internacoes_ano) AS internacoes_ano,
       ROUND(ocupacao_pct, 1) AS ocupacao_estimada_pct,
       {_status('ocupacao_pct', 75, 85)} AS situacao,
       telefone
FROM ocupacao
ORDER BY ocupacao_pct DESC
FETCH FIRST {p.get('top_n') or 20} ROWS ONLY""")]


def capacidade_drs(p):
    return [_bloco("Estrutura hospitalar por DRS", f"""
WITH {_leitos_cte('cod_mun')},
uso AS (
    SELECT mun_int AS cod_mun, SUM(internacoes) / 2 AS internacoes_ano, SUM(dias_perm) / 2 AS dias_ano
    FROM agg_mensal_hosp GROUP BY mun_int
),
residentes AS (
    SELECT mun_res AS cod_mun, SUM(internacoes) / 2 AS internacoes_ano
    FROM agg_mensal_res GROUP BY mun_res
),
ubs AS (
    SELECT cod_mun, COUNT(*) AS ubs FROM dim_estabelecimento WHERE grupo = 'UBS' GROUP BY cod_mun
),
drs AS (
    SELECT m.drs_num, m.drs_nome,
           SUM({POP_MEDIA})             AS populacao,
           SUM(NVL(l.leitos_sus, 0))     AS leitos_sus,
           SUM(NVL(l.leitos_uti_sus, 0)) AS leitos_uti_sus,
           SUM(NVL(b.ubs, 0))            AS ubs,
           SUM(NVL(u.internacoes_ano, 0)) AS internacoes_realizadas,
           SUM(NVL(r.internacoes_ano, 0)) AS internacoes_residentes,
           SUM(NVL(u.dias_ano, 0))        AS dias_ano
    FROM dim_municipio m
    LEFT JOIN leitos l     ON l.cod_mun = m.cod_mun
    LEFT JOIN uso u        ON u.cod_mun = m.cod_mun
    LEFT JOIN residentes r ON r.cod_mun = m.cod_mun
    LEFT JOIN ubs b        ON b.cod_mun = m.cod_mun
    GROUP BY m.drs_num, m.drs_nome
)
SELECT drs_nome,
       ROUND(populacao)                                   AS populacao,
       ROUND(leitos_sus)                                  AS leitos_sus,
       ROUND(leitos_sus * 10000 / populacao, 1)           AS leitos_sus_10k,
       ROUND(leitos_uti_sus * 10000 / populacao, 2)       AS uti_sus_10k,
       ROUND(ubs * 10000 / populacao, 2)                  AS ubs_10k,
       ROUND(internacoes_residentes * 1000 / populacao, 1) AS internacoes_por_1000_hab,
       ROUND(100 * dias_ano / (leitos_sus * 365), 1)      AS ocupacao_estimada_pct,
       {_status('100 * dias_ano / (leitos_sus * 365)', 75, 85)} AS situacao,
       ROUND(100 * internacoes_realizadas / internacoes_residentes, 1) AS cobertura_pct
FROM drs
ORDER BY drs_num""")]


def ubs_internacoes(p):
    drs = f"\n      AND m.drs_num = {p['drs']}" if p.get("drs") else ""
    base = f"""
WITH ubs AS (
    SELECT cod_mun, COUNT(*) AS ubs FROM dim_estabelecimento WHERE grupo = 'UBS' GROUP BY cod_mun
),
residentes AS (
    SELECT mun_res AS cod_mun, SUM(internacoes) / 2 AS internacoes_ano
    FROM agg_mensal_res GROUP BY mun_res
),
municipios AS (
    SELECT m.nome, {POP_MEDIA} AS populacao,
           NVL(u.ubs, 0) * 10000 / ({POP_MEDIA})        AS ubs_10k,
           r.internacoes_ano * 1000 / ({POP_MEDIA})     AS taxa_1k
    FROM dim_municipio m
    JOIN residentes r ON r.cod_mun = m.cod_mun
    LEFT JOIN ubs u   ON u.cod_mun = m.cod_mun
    WHERE {POP_MEDIA} >= 5000{drs}
)"""
    return [
        _bloco("Correlação UBS × internações (Spearman, função nativa CORR_S)", base + """
SELECT ROUND(CORR_S(ubs_10k, taxa_1k), 3) AS spearman_rho,
       ROUND(CORR(ubs_10k, taxa_1k), 3)   AS pearson_r,
       COUNT(*)                           AS municipios
FROM municipios"""),
        _bloco("Taxa mediana por quintil de cobertura de UBS", base + """,
quintis AS (
    SELECT municipios.*, NTILE(5) OVER (ORDER BY ubs_10k) AS quintil FROM municipios
)
SELECT quintil,
       ROUND(MEDIAN(ubs_10k), 2)   AS ubs_10k_mediana,
       ROUND(MEDIAN(taxa_1k), 1)   AS taxa_1k_mediana,
       ROUND(MEDIAN(populacao))    AS populacao_mediana,
       COUNT(*)                    AS municipios
FROM quintis
GROUP BY quintil
ORDER BY quintil"""),
    ]


def clusters(p):
    return [
        _bloco("Extração dos indicadores por município (entrada do K-means)", """
-- tabela res_municipio: indicadores por município gerados pelo pipeline
-- modelagem estatística executada em Python (scikit-learn): padronização, K-means e PCA
SELECT cod_mun, nome, drs_nome, pop,
       taxa_int_1k, perm_media, valor_medio, pct_urgencia, pct_idosos,
       pct_fora, leitos_sus_10k, ubs_10k, LOG(10, pop) AS log_pop
FROM res_municipio
WHERE int_res > 0"""),
        _bloco("Perfil médio de cada grupo", """
SELECT c.cluster AS grupo,
       COUNT(*)                         AS municipios,
       ROUND(SUM(c.pop))                AS populacao,
       ROUND(AVG(c.taxa_int_1k), 1)     AS taxa_1k,
       ROUND(AVG(c.pct_fora), 1)        AS pct_internados_fora,
       ROUND(AVG(c.leitos_sus_10k), 1)  AS leitos_sus_10k,
       ROUND(AVG(c.ubs_10k), 2)         AS ubs_10k
FROM res_cluster_municipio c
GROUP BY c.cluster
ORDER BY c.cluster"""),
    ]


def fatores(p):
    fat = ["pct_idosos", "leitos_sus_10k", "ubs_10k", "pct_fora", "pct_urgencia", "pct_resp"]
    corr = ",\n       ".join(f"ROUND(CORR_S({f}, taxa_int_1k), 3) AS rho_{f}" for f in fat)
    return [
        _bloco("Correlação de Spearman de cada fator com a taxa de internação", f"""
-- regressão ponderada (WLS, erros HC3) executada em Python (statsmodels)
SELECT {corr},
       COUNT(*) AS municipios
FROM res_municipio
WHERE pop >= 5000 AND int_res > 0"""),
        _bloco("Coeficientes da regressão (resultado gravado pelo pipeline)", """
SELECT rotulo AS fator,
       ROUND(coef, 3)     AS coef_padronizado,
       ROUND(ci_low, 3)   AS ic95_inf,
       ROUND(ci_high, 3)  AS ic95_sup,
       ROUND(p_coef, 4)   AS p_valor,
       CASE WHEN p_coef < 0.05 THEN 'Significativo' ELSE 'Não significativo' END AS significancia
FROM res_fatores
ORDER BY ABS(coef) DESC"""),
    ]


QUERIES: dict[str, Callable[[dict], list[dict]]] = {
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

CABECALHO = ("-- SQLadies · adaptação demonstrativa do projeto entregue à Oracle\n"
             "-- Pergunta: {pergunta}\n"
             "-- Bloco: {titulo}\n")


def oracle_sql(question_id: str, params: dict, pergunta: str | None = None) -> list[dict]:
    p = _limpa(params)
    blocos = QUERIES[question_id](p)
    # texto do usuário vai só no comentário, em uma linha (quebras de linha removidas)
    pergunta = " ".join((pergunta or POR_ID[question_id].texto).split())[:200]
    return [{"titulo": b["titulo"],
             "sql": CABECALHO.format(pergunta=pergunta, titulo=b["titulo"]) + b["sql"]}
            for b in blocos]
