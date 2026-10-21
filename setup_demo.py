"""SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.

Instala o banco pronto da demonstração (data/sqladies.db) sem precisar rodar o
pipeline: baixa o arquivo publicado no GitHub Release, confere o SHA-256 e extrai.
Usa só a biblioteca padrão, então pode rodar antes do `pip install`.

Uso:
    python setup_demo.py                 # baixa do GitHub Release
    python setup_demo.py --zip CAMINHO   # instala a partir de um sqladies.db.zip local (ex.: pendrive)
    python setup_demo.py --force         # substitui um banco já existente
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

URL = ("https://github.com/betadaseinhorn/sqladies-saude-sp/releases/download/"
       "v1.0-dados/sqladies.db.zip")
SHA256 = "9e87d8fab737ff74f2797ca3cccbd464b7e818bbdd927a88364363617acc48b7"

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "sqladies.db"
ZIP_TMP = ROOT / "data" / "sqladies.db.zip.part"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def baixar(url: str, dest: Path, tentativas: int = 4) -> None:
    for t in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                feito, inicio = 0, time.time()
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    feito += len(chunk)
                    if total:
                        pct = feito * 100 / total
                        vel = feito / 1e6 / max(time.time() - inicio, 0.1)
                        print(f"\r  baixando: {pct:5.1f}%  ({feito / 1e6:,.0f} de {total / 1e6:,.0f} MB, "
                              f"{vel:,.1f} MB/s)", end="", flush=True)
            print()
            return
        except Exception as exc:  # noqa: BLE001 - rede instável: tenta de novo
            print(f"\n  falha no download (tentativa {t}/{tentativas}): {exc}")
            time.sleep(3 * t)
    sys.exit("Não foi possível baixar o banco. Verifique a internet ou use --zip com o arquivo do pendrive.")


def instalar(zip_path: Path) -> None:
    print("  conferindo integridade (SHA-256)...")
    if sha256(zip_path) != SHA256:
        sys.exit("Arquivo corrompido ou diferente do publicado (SHA-256 não confere). Baixe de novo.")
    print("  extraindo...")
    with zipfile.ZipFile(zip_path) as z:
        if z.namelist() != ["sqladies.db"]:
            sys.exit("Conteúdo inesperado no zip.")
        tmp = DB.with_suffix(".db.part")
        with z.open("sqladies.db") as src, open(tmp, "wb") as dst:
            while chunk := src.read(1 << 20):
                dst.write(chunk)
    tmp.replace(DB)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", type=Path, help="sqladies.db.zip local (em vez de baixar)")
    ap.add_argument("--force", action="store_true", help="substitui o banco existente")
    args = ap.parse_args()

    if DB.exists() and not args.force:
        print(f"O banco já existe em {DB} ({DB.stat().st_size / 1e6:,.0f} MB). Use --force para substituir.")
        return
    DB.parent.mkdir(parents=True, exist_ok=True)
    if args.zip:
        print(f"Instalando o banco a partir de {args.zip}")
        instalar(args.zip)
    else:
        print(f"Baixando o banco da demonstração (~290 MB) de:\n  {URL}")
        baixar(URL, ZIP_TMP)
        try:
            instalar(ZIP_TMP)
        finally:
            ZIP_TMP.unlink(missing_ok=True)
    print(f"Pronto! Banco instalado em {DB} ({DB.stat().st_size / 1e6:,.0f} MB).")
    print("Agora rode:  uvicorn app.main:app   e abra http://localhost:8000")


if __name__ == "__main__":
    main()
