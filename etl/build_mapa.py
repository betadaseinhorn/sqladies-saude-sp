"""Baixa a malha dos municípios de SP (IBGE) e grava static/vendor/sp_municipios.geojson.

O arquivo fica no repositório para o mapa funcionar offline. Cada feição recebe
`id` = código IBGE de 6 dígitos (o mesmo `cod_mun` do banco) e os polígonos são
arredondados a 3 casas decimais (~100 m), suficiente para um mapa estadual, e orientados
no sentido que o Plotly espera (anel externo horário).

Uso:  python -m etl.build_mapa
"""
from __future__ import annotations

import gzip
import json
import urllib.request
from pathlib import Path

from etl.config import UF_CODE

URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
       "?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima")
DEST = Path(__file__).resolve().parents[1] / "static" / "vendor" / "sp_municipios.geojson"


def _arredonda(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 3), round(coords[1], 3)]
    return [_arredonda(c) for c in coords]


def _area(anel) -> float:
    """Área com sinal (fórmula do laço): positiva quando o anel gira no sentido anti-horário."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anel, anel[1:])) / 2


def _orienta(poligono):
    """O Plotly (d3-geo) espera o anel externo no sentido horário e os buracos no anti-horário,
    o contrário do padrão GeoJSON do IBGE. Sem isso, cada município vira "o mundo menos o município"."""
    return [anel if (_area(anel) < 0) == (i == 0) else anel[::-1] for i, anel in enumerate(poligono)]


def main() -> None:
    with urllib.request.urlopen(URL.format(uf=UF_CODE), timeout=120) as r:
        dados = r.read()
    if dados[:2] == bytes([0x1F, 0x8B]):  # a API do IBGE responde compactado (gzip)
        dados = gzip.decompress(dados)
    geo = json.loads(dados)
    feicoes = []
    for f in geo["features"]:
        cod = int(str(f["properties"]["codarea"])[:6])
        g = f["geometry"]
        coords = _arredonda(g["coordinates"])
        coords = _orienta(coords) if g["type"] == "Polygon" else [_orienta(pol) for pol in coords]
        feicoes.append({"type": "Feature", "id": cod, "properties": {},
                        "geometry": {"type": g["type"], "coordinates": coords}})
    DEST.write_text(json.dumps({"type": "FeatureCollection", "features": feicoes}, separators=(",", ":")),
                    encoding="utf-8")
    print(f"{len(feicoes)} municípios → {DEST} ({DEST.stat().st_size / 1e3:,.0f} KB)")


if __name__ == "__main__":
    main()
