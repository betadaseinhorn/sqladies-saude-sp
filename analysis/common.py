"""Utilidades compartilhadas pelas análises."""
from __future__ import annotations

import sqlite3

import pandas as pd

from etl.config import DB_PATH, YEARS

N_ANOS = len(YEARS)
POP_COL = f"pop_{YEARS[-1]}"


def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def query(con: sqlite3.Connection, sql: str, params=()) -> pd.DataFrame:
    return pd.read_sql(sql, con, params=params)


def save(con: sqlite3.Connection, name: str, df: pd.DataFrame) -> None:
    df.to_sql(name, con, if_exists="replace", index=False)
    print(f"  {name}: {len(df):,} linhas")


def municipios(con: sqlite3.Connection) -> pd.DataFrame:
    df = query(con, "SELECT * FROM dim_municipio")
    df["pop"] = df[[f"pop_{y}" for y in YEARS]].mean(axis=1)
    return df
