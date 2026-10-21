"""Monta as tabelas de referência em data/ref/:

- municipios_sp.csv: código IBGE (6 dígitos), nome, DRS, Região de Saúde, RRAS,
  coordenadas, área e população estimada (IBGE) de 2024 e 2025.
- cid_capitulos.csv: capítulos da CID-10.

Uso:  python -m etl.build_ref
"""
from __future__ import annotations

import json

import pandas as pd

from etl.config import RAW_TERR, REF, UF_CODE, YEARS

BASE = RAW_TERR / "base"

# Os 17 Departamentos Regionais de Saúde (DRS) usam numeração romana oficial.
# Na base territorial do DATASUS eles aparecem como "divisão administrativa" 3501..3517.
DRS_ROMANO = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI",
              "XII", "XIII", "XIV", "XV", "XVI", "XVII"]

CID_CAPITULOS = [
    ("I", "A00", "B99", "Infecciosas e parasitárias"),
    ("II", "C00", "D48", "Neoplasias"),
    ("III", "D50", "D89", "Sangue e imunidade"),
    ("IV", "E00", "E90", "Endócrinas e metabólicas"),
    ("V", "F00", "F99", "Transtornos mentais"),
    ("VI", "G00", "G99", "Sistema nervoso"),
    ("VII", "H00", "H59", "Olho e anexos"),
    ("VIII", "H60", "H95", "Ouvido"),
    ("IX", "I00", "I99", "Aparelho circulatório"),
    ("X", "J00", "J99", "Aparelho respiratório"),
    ("XI", "K00", "K93", "Aparelho digestivo"),
    ("XII", "L00", "L99", "Pele e subcutâneo"),
    ("XIII", "M00", "M99", "Osteomuscular"),
    ("XIV", "N00", "N99", "Aparelho geniturinário"),
    ("XV", "O00", "O99", "Gravidez, parto e puerpério"),
    ("XVI", "P00", "P96", "Afecções perinatais"),
    ("XVII", "Q00", "Q99", "Malformações congênitas"),
    ("XVIII", "R00", "R99", "Sintomas e achados anormais"),
    ("XIX", "S00", "T98", "Lesões e envenenamentos"),
    ("XX", "V01", "Y98", "Causas externas"),
    ("XXI", "Z00", "Z99", "Contatos com serviços de saúde"),
    ("XXII", "U00", "U99", "Códigos especiais"),
]


def read_csv(name: str) -> pd.DataFrame:
    """Os CSVs do DATASUS misturam separadores (; ou ,) e encodings (UTF-8 ou Latin-1)."""
    path = BASE / f"{name}.csv"
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        enc = "latin-1"
    first = text.splitlines()[0]
    sep = ";" if first.count(";") >= first.count(",") else ","
    has_header = first.strip('"').startswith(("CO_", "REGSAUD"))
    return pd.read_csv(path, sep=sep, encoding=enc, dtype=str,
                       header=0 if has_header else None)


def load_populacao() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        rows = json.loads((REF / f"populacao_{year}.json").read_text(encoding="utf-8"))[1:]
        df = pd.DataFrame(rows)[["D1C", "D1N", "V"]]
        df.columns = ["cod7", "nome", f"pop_{year}"]
        df[f"pop_{year}"] = pd.to_numeric(df[f"pop_{year}"], errors="coerce")
        frames.append(df.set_index("cod7"))
    pop = frames[0]
    for df in frames[1:]:
        pop = pop.join(df.drop(columns="nome"))
    pop = pop.reset_index()
    pop["cod_mun"] = pop["cod7"].str[:6].astype(int)
    pop["nome"] = pop["nome"].str.replace(r"\s+-\s+SP$", "", regex=True)
    return pop.drop(columns="cod7")


def build_municipios() -> pd.DataFrame:
    mun = read_csv("tb_municip")
    mun = mun[(mun["CO_UF"] == str(UF_CODE)) & (mun["CO_STATUS"] == "ATIVO")]
    mun = pd.DataFrame({
        "cod_mun": mun["CO_MUNICIP"].astype(int),
        "lat": pd.to_numeric(mun["NU_LATITUD"].str.replace(",", "."), errors="coerce"),
        "lon": pd.to_numeric(mun["NU_LONGIT"].str.replace(",", "."), errors="coerce"),
        "area_km2": pd.to_numeric(mun["NU_AREA"].str.replace(",", "."), errors="coerce"),
        "capital": (mun["IN_CAPITAL"] == "S").astype(int),
    })

    # DRS
    rl = read_csv("rl_municip_divadm")
    rl.columns = ["cod_mun", "drs_cod"]
    tb = read_csv("tb_divadm").iloc[:, [0, 2]]
    tb.columns = ["drs_cod", "drs_base"]
    drs = rl.merge(tb, on="drs_cod")
    drs = drs[drs["drs_cod"].str.match(r"^35(0[1-9]|1[0-7])$")]
    drs["drs_num"] = drs["drs_cod"].str[2:].astype(int)
    drs["drs_nome"] = ("DRS " + drs["drs_num"].map(lambda n: DRS_ROMANO[n - 1])
                       + " - " + drs["drs_base"])
    drs["cod_mun"] = drs["cod_mun"].astype(int)

    # Região de Saúde (CIR)
    rl = read_csv("rl_municip_regsaud")
    rl.columns = ["cod_mun", "regsaud_cod"]
    tb = read_csv("tb_regsaud")[["REGSAUD", "DS_NOME"]]
    tb.columns = ["regsaud_cod", "regsaud_nome"]
    tb["regsaud_nome"] = tb["regsaud_nome"].str.replace(r"\s+-\s+SP$", "", regex=True)
    reg = rl.merge(tb, on="regsaud_cod")
    reg["cod_mun"] = reg["cod_mun"].astype(int)

    # RRAS (macrorregião de saúde em SP)
    rl = read_csv("rl_municip_macsaud")
    rl.columns = ["cod_mun", "rras_cod"]
    tb = read_csv("tb_macsaud")[["CO_MACSAUD", "DS_NOME"]]
    tb.columns = ["rras_cod", "rras_nome"]
    rras = rl.merge(tb, on="rras_cod")
    rras = rras[rras["rras_nome"].str.startswith("RRAS")]
    rras["cod_mun"] = rras["cod_mun"].astype(int)
    rras["rras_nome"] = rras["rras_nome"].str.replace("RRAS", "RRAS ", regex=False)

    pop = load_populacao()
    out = (pop.merge(mun, on="cod_mun", how="left")
              .merge(drs[["cod_mun", "drs_num", "drs_nome"]], on="cod_mun", how="left")
              .merge(reg, on="cod_mun", how="left")
              .merge(rras, on="cod_mun", how="left"))
    cols = ["cod_mun", "nome", "drs_num", "drs_nome", "regsaud_cod", "regsaud_nome",
            "rras_cod", "rras_nome", "lat", "lon", "area_km2", "capital"] + \
           [f"pop_{y}" for y in YEARS]
    return out[cols].sort_values("cod_mun")


def main() -> None:
    mun = build_municipios()
    missing = mun[mun[["drs_nome", "regsaud_nome", "rras_nome"]].isna().any(axis=1)]
    if len(missing):
        print("Atenção: municípios sem divisão regional:\n", missing[["cod_mun", "nome"]])
    mun.to_csv(REF / "municipios_sp.csv", index=False, encoding="utf-8")
    print(f"municipios_sp.csv: {len(mun)} municípios, "
          f"{mun['drs_nome'].nunique()} DRS, {mun['regsaud_nome'].nunique()} regiões de saúde, "
          f"{mun['rras_nome'].nunique()} RRAS")

    cid = pd.DataFrame(CID_CAPITULOS, columns=["cap_cod", "inicio", "fim", "cap_nome"])
    cid.insert(0, "cap_num", range(1, len(cid) + 1))
    cid.to_csv(REF / "cid_capitulos.csv", index=False, encoding="utf-8")
    print(f"cid_capitulos.csv: {len(cid)} capítulos")


if __name__ == "__main__":
    main()
