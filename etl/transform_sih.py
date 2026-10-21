"""Converte os arquivos RD (.dbc) do SIH/SUS em Parquet limpo, um por competência.

Uso:  python -m etl.transform_sih
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from etl.config import PROCESSED, RAW_SIH, REF
from etl.dbc import read_dbc

OUT = PROCESSED / "sih"
OUT.mkdir(parents=True, exist_ok=True)

COLS = ["ANO_CMPT", "MES_CMPT", "N_AIH", "IDENT", "CNES", "MUNIC_RES", "MUNIC_MOV",
        "SEXO", "COD_IDADE", "IDADE", "DIAG_PRINC", "CAR_INT", "DIAS_PERM",
        "VAL_TOT", "VAL_UTI", "UTI_MES_TO", "MORTE", "DT_INTER", "DT_SAIDA",
        "PROC_REA", "ESPEC"]

FAIXAS = [(0, 4, "0-4"), (5, 14, "5-14"), (15, 29, "15-29"), (30, 44, "30-44"),
          (45, 59, "45-59"), (60, 74, "60-74"), (75, 200, "75+")]


def _capitulos() -> tuple[list[str], list[str], list[str]]:
    cid = pd.read_csv(REF / "cid_capitulos.csv", dtype=str)
    return cid["inicio"].tolist(), cid["fim"].tolist(), cid["cap_cod"].tolist()


def cid_capitulo(diag: pd.Series) -> pd.Series:
    inicio, fim, cods = _capitulos()
    d3 = diag.str[:3].str.upper()
    out = pd.Series(pd.NA, index=diag.index, dtype="object")
    for a, b, c in zip(inicio, fim, cods):
        out[(d3 >= a) & (d3 <= b) & out.isna()] = c
    return out


def idade_anos(cod: pd.Series, idade: pd.Series) -> pd.Series:
    n = pd.to_numeric(idade, errors="coerce")
    # COD_IDADE: 2=dias, 3=meses, 4=anos, 5=anos acima de 100
    return np.select([cod == "4", cod == "5", cod.isin(["2", "3"])],
                     [n, n + 100, 0], default=np.nan)


def transform(path) -> str:
    dest = OUT / (path.stem + ".parquet")
    if dest.exists():
        return f"já existe {dest.name}"
    raw = read_dbc(path, COLS)
    df = pd.DataFrame({
        "competencia": (raw["ANO_CMPT"] + raw["MES_CMPT"]).astype(int),
        "n_aih": raw["N_AIH"],
        "ident": pd.to_numeric(raw["IDENT"], errors="coerce").astype("Int8"),
        "cnes": pd.to_numeric(raw["CNES"], errors="coerce").astype("Int64"),
        "mun_res": pd.to_numeric(raw["MUNIC_RES"], errors="coerce").astype("Int64"),
        "mun_int": pd.to_numeric(raw["MUNIC_MOV"], errors="coerce").astype("Int64"),
        "sexo": raw["SEXO"].map({"1": "M", "3": "F", "2": "F"}),
        "diag_princ": raw["DIAG_PRINC"],
        "carater": np.where(raw["CAR_INT"] == "01", "Eletivo", "Urgência"),
        "dias_perm": pd.to_numeric(raw["DIAS_PERM"], errors="coerce").fillna(0).astype("int32"),
        "uti_dias": pd.to_numeric(raw["UTI_MES_TO"], errors="coerce").fillna(0).astype("int32"),
        "valor_total": pd.to_numeric(raw["VAL_TOT"], errors="coerce").fillna(0.0),
        "valor_uti": pd.to_numeric(raw["VAL_UTI"], errors="coerce").fillna(0.0),
        "morte": pd.to_numeric(raw["MORTE"], errors="coerce").fillna(0).astype("int8"),
        "proc_rea": raw["PROC_REA"],
        "espec": raw["ESPEC"],
    })
    df["idade"] = idade_anos(raw["COD_IDADE"], raw["IDADE"])
    df["faixa_etaria"] = pd.cut(df["idade"], bins=[-1] + [f[1] for f in FAIXAS],
                                labels=[f[2] for f in FAIXAS]).astype("object")
    df["cap_cid"] = cid_capitulo(df["diag_princ"])
    dt = pd.to_datetime(raw["DT_INTER"], format="%Y%m%d", errors="coerce")
    df["dt_inter"] = dt.dt.strftime("%Y-%m-%d")
    df["mes_inter"] = dt.dt.strftime("%Y-%m")
    df["dt_saida"] = pd.to_datetime(raw["DT_SAIDA"], format="%Y%m%d",
                                    errors="coerce").dt.strftime("%Y-%m-%d")
    df.to_parquet(dest, index=False)
    return f"ok {dest.name}: {len(df):,} AIHs"


def main() -> None:
    files = sorted(RAW_SIH.glob("RD*.dbc"))
    with ProcessPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(transform, files):
            print(msg)


if __name__ == "__main__":
    main()
