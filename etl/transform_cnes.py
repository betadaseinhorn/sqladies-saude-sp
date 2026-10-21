"""Normaliza o JSON da API do CNES e os arquivos de leitos (LT).

- dim_estabelecimento: colunas fixas + `atributos_json` com os campos que variam
  entre estabelecimentos (só os não nulos de cada registro), preservando a
  natureza semiestruturada da fonte.
- cnes_raw: o registro JSON original, sem alteração.
- fato_leitos: leitos existentes e SUS por estabelecimento, tipo e competência.

Uso:  python -m etl.transform_cnes
"""
from __future__ import annotations

import json

import pandas as pd

from etl.config import (PROCESSED, RAW_CNES, RAW_LT, TIPOS_CNES, TIPOS_HOSPITAL,
                        TIPOS_UBS, TIPOS_URGENCIA)
from etl.dbc import read_dbc

# campo da API -> coluna da dimensão
CORE = {
    "codigo_cnes": "cnes",
    "nome_fantasia": "nome",
    "nome_razao_social": "razao_social",
    "codigo_tipo_unidade": "tipo_cod",
    "codigo_municipio": "cod_mun",
    "tipo_gestao": "gestao",
    "descricao_esfera_administrativa": "esfera",
    "descricao_natureza_juridica_estabelecimento": "natureza_juridica",
    "numero_telefone_estabelecimento": "telefone",
    "endereco_email_estabelecimento": "email",
    "codigo_cep_estabelecimento": "cep",
    "endereco_estabelecimento": "endereco",
    "numero_estabelecimento": "numero",
    "bairro_estabelecimento": "bairro",
    "latitude_estabelecimento_decimo_grau": "lat",
    "longitude_estabelecimento_decimo_grau": "lon",
    "estabelecimento_faz_atendimento_ambulatorial_sus": "atende_sus_amb",
    "estabelecimento_possui_centro_cirurgico": "centro_cirurgico",
    "estabelecimento_possui_centro_obstetrico": "centro_obstetrico",
    "estabelecimento_possui_centro_neonatal": "centro_neonatal",
    "estabelecimento_possui_atendimento_hospitalar": "atend_hospitalar",
    "data_atualizacao": "data_atualizacao",
}

TP_LEITO = {"1": "Cirúrgico", "2": "Clínico", "3": "Complementar (UTI/UCI)",
            "4": "Obstétrico", "5": "Pediátrico", "6": "Outras especialidades",
            "7": "Hospital dia"}


def grupo(tipo: int) -> str:
    if tipo in TIPOS_HOSPITAL:
        return "Hospital"
    if tipo in TIPOS_UBS:
        return "UBS"
    if tipo in TIPOS_URGENCIA:
        return "Urgência"
    return "Outro"


def load_cnes_json() -> tuple[pd.DataFrame, pd.DataFrame]:
    records = []
    for page in sorted(RAW_CNES.glob("tipo_*/page_*.json")):
        records.extend(json.loads(page.read_text(encoding="utf-8")))
    raw = pd.DataFrame({
        "cnes": [r["codigo_cnes"] for r in records],
        "tipo_cod": [r["codigo_tipo_unidade"] for r in records],
        "json": [json.dumps(r, ensure_ascii=False) for r in records],
    }).drop_duplicates("cnes")

    flat = pd.json_normalize(records)
    dim = flat[list(CORE)].rename(columns=CORE)
    extras = [c for c in flat.columns if c not in CORE]
    dim["atributos_json"] = [
        json.dumps({k: v for k, v in row.items() if v is not None and v == v},
                   ensure_ascii=False)
        for row in flat[extras].to_dict("records")
    ]
    dim["tipo_desc"] = dim["tipo_cod"].map(TIPOS_CNES)
    dim["grupo"] = dim["tipo_cod"].map(grupo)
    dim["nome"] = dim["nome"].fillna(dim["razao_social"]).str.strip().str.title()
    dim = dim.drop_duplicates("cnes")
    return dim, raw


def load_leitos() -> pd.DataFrame:
    frames = []
    for path in sorted(RAW_LT.glob("LT*.dbc")):
        df = read_dbc(path, ["CNES", "CODUFMUN", "TP_LEITO", "CODLEITO", "QT_EXIST",
                             "QT_SUS", "COMPETEN", "TP_UNID"])
        frames.append(df)
    lt = pd.concat(frames, ignore_index=True)
    return pd.DataFrame({
        "competencia": lt["COMPETEN"].astype(int),
        "cnes": lt["CNES"].astype(int),
        "cod_mun": lt["CODUFMUN"].astype(int),
        "tipo_unidade_cod": pd.to_numeric(lt["TP_UNID"], errors="coerce").astype("Int64"),
        "tp_leito": lt["TP_LEITO"].map(TP_LEITO).fillna("Outros"),
        "cod_leito": lt["CODLEITO"],
        "qt_exist": pd.to_numeric(lt["QT_EXIST"], errors="coerce").fillna(0).astype(int),
        "qt_sus": pd.to_numeric(lt["QT_SUS"], errors="coerce").fillna(0).astype(int),
    })


def main() -> None:
    dim, raw = load_cnes_json()
    dim.to_parquet(PROCESSED / "dim_estabelecimento.parquet", index=False)
    raw.to_parquet(PROCESSED / "cnes_raw.parquet", index=False)
    print(f"dim_estabelecimento: {len(dim):,} registros "
          f"({dim['grupo'].value_counts().to_dict()})")
    leitos = load_leitos()
    leitos.to_parquet(PROCESSED / "fato_leitos.parquet", index=False)
    print(f"fato_leitos: {len(leitos):,} linhas, {leitos['cnes'].nunique():,} estabelecimentos")


if __name__ == "__main__":
    main()
