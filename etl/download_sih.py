"""Baixa do FTP do DATASUS os arquivos do SIH (RD), leitos do CNES (LT),
a base territorial e a população estimada do IBGE (SIDRA).

Uso:  python -m etl.download_sih
Arquivos já baixados são ignorados, então o script pode ser reexecutado.
"""
from __future__ import annotations

import json
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

from etl.config import (LT_URL, MONTHS, RAW_LT, RAW_SIH, RAW_TERR, REF,
                        SIDRA_POP_URL, SIH_EXTRA_MONTHS, SIH_URL, TERR_URL, UF,
                        UF_CODE, YEARS)


def fetch(url: str, dest, retries: int = 4) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
            print(f"ok   {dest.name}")
            return
        except Exception as exc:  # noqa: BLE001 - FTP do DATASUS é instável
            print(f"erro {dest.name} (tentativa {attempt}): {exc}")
            time.sleep(5 * attempt)
    raise RuntimeError(f"falha ao baixar {url}")


def main() -> None:
    jobs = []
    for y, m in MONTHS:
        yy = y % 100
        jobs.append((SIH_URL.format(uf=UF, yy=yy, mm=m), RAW_SIH / f"RD{UF}{yy:02d}{m:02d}.dbc"))
        jobs.append((LT_URL.format(uf=UF, yy=yy, mm=m), RAW_LT / f"LT{UF}{yy:02d}{m:02d}.dbc"))
    for y, m in SIH_EXTRA_MONTHS:
        yy = y % 100
        jobs.append((SIH_URL.format(uf=UF, yy=yy, mm=m), RAW_SIH / f"RD{UF}{yy:02d}{m:02d}.dbc"))
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: fetch(*j), jobs))

    # Base territorial (DRS, regiões de saúde, RRAS, coordenadas)
    zpath = RAW_TERR / "base_territorial.zip"
    fetch(TERR_URL, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(RAW_TERR / "base")

    # População estimada por município
    for year in YEARS:
        dest = REF / f"populacao_{year}.json"
        if not dest.exists():
            with urllib.request.urlopen(SIDRA_POP_URL.format(uf=UF_CODE, year=year), timeout=120) as r:
                rows = json.load(r)
            dest.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            print(f"ok   {dest.name} ({len(rows) - 1} municípios)")


if __name__ == "__main__":
    main()
