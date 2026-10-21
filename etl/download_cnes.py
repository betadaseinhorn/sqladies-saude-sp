"""Baixa da API de Dados Abertos do Ministério da Saúde o cadastro CNES
(hospitais, UBS e unidades de urgência de SP) e guarda cada página como JSON bruto.

Uso:  python -m etl.download_cnes
A API devolve no máximo 20 registros por página. O script retoma de onde parou:
páginas já salvas não são baixadas de novo.
"""
from __future__ import annotations

import json
import time

import requests

from etl.config import CNES_API, CNES_PAGE, RAW_CNES, TIPOS_CNES, UF_CODE


def get_page(session: requests.Session, tipo: int, offset: int) -> list[dict]:
    params = {"codigo_uf": UF_CODE, "codigo_tipo_unidade": tipo,
              "limit": CNES_PAGE, "offset": offset}
    for attempt in range(1, 6):
        try:
            r = session.get(CNES_API, params=params, timeout=60)
            r.raise_for_status()
            return r.json()["estabelecimentos"]
        except Exception as exc:  # noqa: BLE001
            print(f"  erro tipo={tipo} offset={offset} (tentativa {attempt}): {exc}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"falha na API do CNES: tipo={tipo} offset={offset}")


def download_tipo(session: requests.Session, tipo: int) -> int:
    folder = RAW_CNES / f"tipo_{tipo:02d}"
    folder.mkdir(exist_ok=True)
    done = folder / "_completo"
    if done.exists():
        return sum(len(json.loads(p.read_text(encoding="utf-8")))
                   for p in folder.glob("page_*.json"))
    total, offset = 0, 0
    while True:
        dest = folder / f"page_{offset:06d}.json"
        if dest.exists():
            rows = json.loads(dest.read_text(encoding="utf-8"))
        else:
            rows = get_page(session, tipo, offset)
            dest.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        total += len(rows)
        if len(rows) < CNES_PAGE:
            break
        offset += CNES_PAGE
    done.touch()
    return total


def main() -> None:
    with requests.Session() as s:
        for tipo, nome in TIPOS_CNES.items():
            n = download_tipo(s, tipo)
            print(f"tipo {tipo:02d} {nome}: {n} estabelecimentos")


if __name__ == "__main__":
    main()
