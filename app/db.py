"""Acesso somente leitura ao banco SQLite."""
from __future__ import annotations

import sqlite3
import threading
from functools import lru_cache

import pandas as pd

from etl.config import DB_PATH

_local = threading.local()


def conn() -> sqlite3.Connection:
    """Uma conexão por thread, aberta em modo somente leitura."""
    c = getattr(_local, "con", None)
    if c is None:
        uri = DB_PATH.resolve().as_uri() + "?mode=ro"
        c = sqlite3.connect(uri, uri=True, check_same_thread=False)
        _local.con = c
    return c


def df(sql: str, params: dict | tuple = ()) -> pd.DataFrame:
    """Executa uma consulta parametrizada (nunca concatene valores do usuário no SQL)."""
    return pd.read_sql(sql, conn(), params=params)


def scalar(sql: str, params: dict | tuple = ()):
    return conn().execute(sql, params).fetchone()[0]


@lru_cache(maxsize=1)
def municipios() -> pd.DataFrame:
    return df("SELECT cod_mun, nome, drs_num, drs_nome, regsaud_nome, rras_nome, "
              "pop_2024, pop_2025 FROM dim_municipio ORDER BY nome")


@lru_cache(maxsize=1)
def drs() -> pd.DataFrame:
    return df("SELECT DISTINCT drs_num, drs_nome FROM dim_municipio ORDER BY drs_num")


@lru_cache(maxsize=1)
def capitulos() -> pd.DataFrame:
    return df("SELECT cap_num, cap_cod, cap_nome FROM dim_cid_capitulo ORDER BY cap_num")


@lru_cache(maxsize=1)
def anos() -> list[int]:
    d = df("SELECT DISTINCT substr(mes_inter, 1, 4) AS ano FROM agg_mensal_hosp ORDER BY 1")
    return [int(a) for a in d["ano"]]
