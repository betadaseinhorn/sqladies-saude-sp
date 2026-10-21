"""Roda todas as análises e grava as tabelas res_* no banco.

Uso:  python -m analysis.run_all
"""
from analysis import capacity, clustering, ranking, seasonality
from analysis.common import connect


def main() -> None:
    con = connect()
    print("sazonalidade")
    seasonality.run(con)
    print("rankings e indicadores")
    mun = ranking.run(con)
    print("capacidade")
    capacity.run(con)
    print("agrupamentos e fatores")
    clustering.run(con, mun)
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
