"""Configurações compartilhadas do pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_SIH = RAW / "sih"
RAW_LT = RAW / "lt"
RAW_CNES = RAW / "cnes"
RAW_TERR = RAW / "territorio"
PROCESSED = DATA / "processed"
REF = DATA / "ref"
DB_PATH = DATA / "sqladies.db"

UF = "SP"
UF_CODE = 35
YEARS = (2024, 2025)
MONTHS = [(y, m) for y in YEARS for m in range(1, 13)]
# Competências seguintes baixadas só para captar AIHs apresentadas com atraso
# (internações de fim de 2025 cobradas em 2026). A análise usa a data de internação.
SIH_EXTRA_MONTHS = [(2026, 1), (2026, 2), (2026, 3)]
PERIOD_START, PERIOD_END = "2024-01", "2025-12"

FTP = "ftp://ftp.datasus.gov.br"
SIH_URL = FTP + "/dissemin/publicos/SIHSUS/200801_/Dados/RD{uf}{yy:02d}{mm:02d}.dbc"
LT_URL = FTP + "/dissemin/publicos/CNES/200508_/Dados/LT/LT{uf}{yy:02d}{mm:02d}.dbc"
TERR_URL = FTP + "/territorio/tabelas/2025/10-base_territorial_out25.zip"
SIDRA_POP_URL = ("https://apisidra.ibge.gov.br/values/t/6579/n6/in%20n3%20{uf}"
                 "/v/9324/p/{year}")

CNES_API = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
CNES_PAGE = 20  # limite máximo aceito pela API

# Tipos de unidade do CNES usados no projeto
TIPOS_HOSPITAL = {5: "Hospital geral", 7: "Hospital especializado",
                  15: "Unidade mista", 62: "Hospital dia"}
TIPOS_UBS = {1: "Posto de saúde", 2: "Centro de saúde / UBS"}
TIPOS_URGENCIA = {20: "Pronto-socorro geral", 21: "Pronto-socorro especializado",
                  73: "Pronto atendimento (UPA)"}
TIPOS_CNES = {**TIPOS_HOSPITAL, **TIPOS_UBS, **TIPOS_URGENCIA}

for _p in (RAW_SIH, RAW_LT, RAW_CNES, RAW_TERR, PROCESSED, REF):
    _p.mkdir(parents=True, exist_ok=True)
