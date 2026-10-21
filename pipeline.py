"""SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.

Roda o pipeline completo: download → transformação → banco → análises.

Uso:  python pipeline.py            (tudo; etapas já feitas são puladas pelos scripts)
      python pipeline.py --sem-download
Leva de 10 a 20 minutos na primeira vez (cerca de 550 MB de download do DATASUS).
"""
import argparse
import time

from etl import build_db, build_ref, download_cnes, download_sih, transform_cnes, transform_sih
from analysis import run_all


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-download", action="store_true", help="usa os arquivos já baixados")
    args = ap.parse_args()
    etapas = [] if args.sem_download else [("Download SIH/LT/IBGE", download_sih.main),
                                           ("Download CNES (API)", download_cnes.main)]
    etapas += [("Referências", build_ref.main), ("Transformação SIH", transform_sih.main),
               ("Transformação CNES", transform_cnes.main), ("Banco SQLite", build_db.main),
               ("Análises", run_all.main)]
    for nome, fn in etapas:
        t = time.time()
        print(f"\n=== {nome} ===")
        fn()
        print(f"--- {nome}: {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
