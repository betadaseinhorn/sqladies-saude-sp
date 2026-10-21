"""Cria o banco SQLite (data/sqladies.db) a partir dos arquivos processados.

Tabelas:
  dim_municipio, dim_cid_capitulo, dim_estabelecimento, cnes_raw (JSON bruto),
  fato_internacao (1 linha por AIH), fato_leitos,
  agg_mensal_hosp (mês × hospital × capítulo CID × caráter),
  agg_mensal_res  (mês × município de residência × capítulo CID × caráter × faixa etária)

Uso:  python -m etl.build_db
"""
from __future__ import annotations

import sqlite3
import time

import pandas as pd

from etl.config import DB_PATH, PERIOD_END, PERIOD_START, PROCESSED, REF, UF_CODE

SCHEMA = """
CREATE TABLE dim_municipio (
    cod_mun INTEGER PRIMARY KEY, nome TEXT, drs_num INTEGER, drs_nome TEXT,
    regsaud_cod TEXT, regsaud_nome TEXT, rras_cod TEXT, rras_nome TEXT,
    lat REAL, lon REAL, area_km2 REAL, capital INTEGER, pop_2024 INTEGER, pop_2025 INTEGER
);
CREATE TABLE dim_cid_capitulo (
    cap_num INTEGER, cap_cod TEXT PRIMARY KEY, inicio TEXT, fim TEXT, cap_nome TEXT
);
CREATE TABLE dim_estabelecimento (
    cnes INTEGER PRIMARY KEY, nome TEXT, razao_social TEXT, tipo_cod INTEGER,
    tipo_desc TEXT, grupo TEXT, cod_mun INTEGER REFERENCES dim_municipio(cod_mun),
    gestao TEXT, esfera TEXT, natureza_juridica TEXT, telefone TEXT, email TEXT,
    cep TEXT, endereco TEXT, numero TEXT, bairro TEXT, lat REAL, lon REAL,
    atende_sus_amb TEXT, centro_cirurgico INTEGER, centro_obstetrico INTEGER,
    centro_neonatal INTEGER, atend_hospitalar INTEGER, data_atualizacao TEXT,
    atributos_json TEXT CHECK (json_valid(atributos_json))
);
CREATE TABLE cnes_raw (
    cnes INTEGER PRIMARY KEY, tipo_cod INTEGER, json TEXT CHECK (json_valid(json))
);
CREATE TABLE fato_internacao (
    competencia INTEGER, n_aih TEXT, ident INTEGER, conta_internacao INTEGER,
    cnes INTEGER, mun_res INTEGER, mun_int INTEGER, sexo TEXT, idade REAL,
    faixa_etaria TEXT, diag_princ TEXT, cap_cid TEXT, carater TEXT,
    dt_inter TEXT, mes_inter TEXT, dt_saida TEXT, dias_perm INTEGER, uti_dias INTEGER,
    valor_total REAL, valor_uti REAL, morte INTEGER, proc_rea TEXT, espec TEXT
);
CREATE TABLE fato_leitos (
    competencia INTEGER, cnes INTEGER, cod_mun INTEGER, tipo_unidade_cod INTEGER,
    tp_leito TEXT, cod_leito TEXT, qt_exist INTEGER, qt_sus INTEGER
);
"""

AGG_SQL = """
CREATE TABLE agg_mensal_hosp AS
SELECT mes_inter, cnes, mun_int, cap_cid, carater,
       SUM(conta_internacao)                         AS internacoes,
       COUNT(*)                                      AS aihs,
       SUM(dias_perm * conta_internacao)             AS dias_perm,
       SUM(valor_total)                              AS valor_total,
       SUM(morte * conta_internacao)                 AS obitos,
       SUM(uti_dias)                                 AS uti_dias,
       SUM(conta_internacao * (idade >= 60))         AS idosos,
       SUM(conta_internacao * (mun_res <> mun_int))  AS residentes_fora
FROM fato_internacao
GROUP BY 1, 2, 3, 4, 5;

CREATE TABLE agg_mensal_res AS
SELECT mes_inter, mun_res, cap_cid, carater, faixa_etaria,
       SUM(conta_internacao)                         AS internacoes,
       SUM(dias_perm * conta_internacao)             AS dias_perm,
       SUM(valor_total)                              AS valor_total,
       SUM(morte * conta_internacao)                 AS obitos,
       SUM(conta_internacao * (mun_res <> mun_int))  AS internadas_fora
FROM fato_internacao
WHERE mun_res BETWEEN {uf}0000 AND {uf}9999
GROUP BY 1, 2, 3, 4, 5;
""".format(uf=UF_CODE)

INDEXES = """
CREATE INDEX ix_fi_mes ON fato_internacao(mes_inter);
CREATE INDEX ix_fi_mun_int ON fato_internacao(mun_int);
CREATE INDEX ix_fi_mun_res ON fato_internacao(mun_res);
CREATE INDEX ix_fi_cnes ON fato_internacao(cnes);
CREATE INDEX ix_fi_cap ON fato_internacao(cap_cid);
CREATE INDEX ix_ah_mes ON agg_mensal_hosp(mes_inter);
CREATE INDEX ix_ah_cnes ON agg_mensal_hosp(cnes);
CREATE INDEX ix_ah_mun ON agg_mensal_hosp(mun_int);
CREATE INDEX ix_ar_mes ON agg_mensal_res(mes_inter);
CREATE INDEX ix_ar_mun ON agg_mensal_res(mun_res);
CREATE INDEX ix_lt_cnes ON fato_leitos(cnes, competencia);
CREATE INDEX ix_lt_mun ON fato_leitos(cod_mun);
CREATE INDEX ix_est_mun ON dim_estabelecimento(cod_mun, grupo);
"""


def load_internacoes() -> pd.DataFrame:
    df = pd.concat([pd.read_parquet(p) for p in sorted((PROCESSED / "sih").glob("*.parquet"))],
                   ignore_index=True)
    n0 = len(df)
    df = df[(df["mes_inter"] >= PERIOD_START) & (df["mes_inter"] <= PERIOD_END)]
    df = df[df["mun_int"].between(UF_CODE * 10000, UF_CODE * 10000 + 9999)]
    # Uma internação = AIH normal (IDENT=1). AIHs de longa permanência (IDENT=5) somam
    # valores e diárias, mas não contam como nova internação. Reapresentações da mesma
    # AIH em competências diferentes contam uma vez só (fica a mais recente).
    df = df.sort_values("competencia")
    principal = (df["ident"] == 1) & ~df.duplicated(["n_aih", "ident"], keep="last")
    df["conta_internacao"] = principal.astype("int8")
    print(f"fato_internacao: {len(df):,} AIHs de {n0:,} lidas "
          f"({int(df['conta_internacao'].sum()):,} internações)")
    return df


def main() -> None:
    t0 = time.time()
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)

    def insert(table: str, df: pd.DataFrame) -> None:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        df = df[cols].astype(object).where(df[cols].notna(), None)
        con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})",
                        df.itertuples(index=False, name=None))
        con.commit()
        print(f"  {table}: {len(df):,} linhas")

    insert("dim_municipio", pd.read_csv(REF / "municipios_sp.csv"))
    insert("dim_cid_capitulo", pd.read_csv(REF / "cid_capitulos.csv"))
    insert("dim_estabelecimento", pd.read_parquet(PROCESSED / "dim_estabelecimento.parquet"))
    insert("cnes_raw", pd.read_parquet(PROCESSED / "cnes_raw.parquet"))
    insert("fato_leitos", pd.read_parquet(PROCESSED / "fato_leitos.parquet"))
    insert("fato_internacao", load_internacoes())

    con.executescript(AGG_SQL)
    con.executescript(INDEXES)
    con.execute("ANALYZE")
    con.commit()

    # Cobertura: hospitais do SIH presentes no cadastro vindo da API
    cov = con.execute("""
        SELECT COUNT(*), SUM(e.cnes IS NOT NULL)
        FROM (SELECT DISTINCT cnes FROM agg_mensal_hosp) h
        LEFT JOIN dim_estabelecimento e USING (cnes)""").fetchone()
    print(f"hospitais no SIH: {cov[0]}, com cadastro CNES via API: {cov[1]}")
    con.close()
    print(f"banco criado em {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.0f} MB) "
          f"em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
