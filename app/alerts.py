"""Sistema de alertas: classifica indicadores em Aceitável / Alerta / Crítico.

SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.

As regras ficam em REGRAS e podem ser ajustadas sem mexer nos dashboards:
- "abs": compara o valor com limites fixos (ex.: ocupação 75% / 85%);
- "rel": compara o valor com uma referência (média do estado ou da DRS),
  usando limites em múltiplos da referência (ex.: 1,2× / 1,5×).
`maior_pior=False` inverte o sentido (ex.: leitos por habitante: quanto menos, pior).
"""
from __future__ import annotations

from functools import lru_cache

from app import db

NIVEIS = ("aceitavel", "alerta", "critico")
ROTULOS = {"aceitavel": "Aceitável", "alerta": "Alerta", "critico": "Crítico"}

REGRAS: dict[str, dict] = {
    "ocupacao": {"indicador": "Ocupação estimada de leitos SUS", "tipo": "abs", "limites": (75, 85),
                 "unidade": "%", "base": "Aceitável abaixo de 75%; crítico acima de 85%"},
    "taxa": {"indicador": "Taxa de internação por 1.000 hab.", "tipo": "rel", "limites": (1.10, 1.30),
             "unidade": "", "ref_nome": "mediana dos municípios",
             "base": "Até 10% acima da mediana dos municípios: aceitável; mais de 30%: crítico"},
    "permanencia": {"indicador": "Permanência média", "tipo": "rel", "limites": (1.2, 1.5),
                    "unidade": " dias", "base": "Até 1,2× a média estadual: aceitável; acima de 1,5×: crítico"},
    "mortalidade": {"indicador": "Mortalidade hospitalar", "tipo": "rel", "limites": (1.1, 1.3),
                    "unidade": "%", "base": "Até 1,1× a média estadual: aceitável; acima de 1,3×: crítico"},
    "int_por_leito": {"indicador": "Internações por leito SUS/ano", "tipo": "rel", "limites": (1.3, 1.6),
                      "unidade": "", "base": "Até 1,3× a média estadual: aceitável; acima de 1,6×: crítico"},
    "pct_fora": {"indicador": "Residentes internados fora do município", "tipo": "abs", "limites": (30, 60),
                 "unidade": "%", "base": "Até 30%: aceitável; acima de 60%: crítico (dependência regional)"},
    "pico_sazonal": {"indicador": "Pico sazonal", "tipo": "abs", "limites": (10, 25),
                     "unidade": "%", "base": "Pico até 10% acima da média: aceitável; acima de 25%: crítico"},
    "leitos_10k": {"indicador": "Leitos SUS por 10 mil hab.", "tipo": "abs", "limites": (15, 10),
                   "maior_pior": False, "unidade": "",
                   "base": "15 ou mais: aceitável; menos de 10: crítico"},
    "pct_hosp_criticos": {"indicador": "Hospitais com ocupação crítica (>85%)", "tipo": "abs",
                          "limites": (10, 25), "unidade": "%",
                          "base": "Até 10% dos hospitais: aceitável; acima de 25%: crítico"},
    "pct_mun_criticos": {"indicador": "Municípios com taxa de internação crítica", "tipo": "abs",
                         "limites": (10, 20), "unidade": "%",
                         "base": "Até 10% dos municípios: aceitável; acima de 20%: crítico"},
}


def _dec(v: float, casas: int = 1) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


@lru_cache(maxsize=1)
def referencias() -> dict[str, float]:
    """Referências estaduais das regras relativas.

    Taxa de internação: mediana dos municípios com 5 mil+ hab. (a média ponderada
    pela população é puxada pela capital e não serve para comparar municípios).
    Demais: médias do estado.
    """
    r = db.df("""SELECT SUM(dias_occ) * 1.0 / SUM(int_occ) AS permanencia,
                        SUM(obitos_res) * 100.0 / SUM(int_res) AS mortalidade,
                        SUM(int_occ_ano) / SUM(leitos_sus) AS int_por_leito,
                        SUM(leitos_sus) * 10000.0 / SUM(pop) AS leitos_10k
                 FROM res_municipio""").iloc[0]
    n_anos = len(db.anos())
    ocup = db.scalar("SELECT SUM(dias_occ) FROM res_municipio") / n_anos * 100 / (
        db.scalar("SELECT SUM(leitos_sus) FROM res_municipio") * 365)
    taxa = db.df("SELECT taxa_int_1k FROM res_municipio WHERE pop >= 5000")["taxa_int_1k"].median()
    return {**{k: float(v) for k, v in r.items()}, "ocupacao": float(ocup), "taxa": float(taxa)}


def nivel(chave: str, valor, ref: float | None = None) -> str | None:
    """Só o nível (para colunas de tabela). None quando não há valor."""
    if valor is None or valor != valor:
        return None
    regra = REGRAS[chave]
    x = float(valor)
    if regra["tipo"] == "rel":
        ref = ref if ref is not None else referencias()[chave]
        if not ref:
            return None
        x = x / ref
    a, b = regra["limites"]
    if regra.get("maior_pior", True):
        return "aceitavel" if x <= a else ("alerta" if x <= b else "critico")
    return "aceitavel" if x >= a else ("alerta" if x >= b else "critico")


def classificar(chave: str, valor, *, ref: float | None = None, onde: str = "",
                ref_nome: str | None = None) -> dict | None:
    """Alerta completo para o painel "Situação"."""
    nv = nivel(chave, valor, ref)
    if nv is None:
        return None
    regra = REGRAS[chave]
    un = regra["unidade"]
    casas = 0 if un == "%" and chave in ("ocupacao", "pct_fora", "pct_hosp_criticos", "pct_mun_criticos") else 1
    valor_txt = (("+" if valor > 0 else "") if chave == "pico_sazonal" else "") + _dec(valor, casas) + un
    if regra["tipo"] == "rel":
        ref = ref if ref is not None else referencias()[chave]
        ref_nome = ref_nome or regra.get("ref_nome", "média do estado")
        explic = f"{_dec(valor / ref, 2)}× a {ref_nome} ({_dec(ref, 1)}{un})"
    else:
        explic = regra["base"]
    indicador = regra["indicador"] + (f" · {onde}" if onde else "")
    return {"chave": chave, "nivel": nv, "rotulo": ROTULOS[nv], "indicador": indicador, "valor": valor_txt,
            "referencia": regra["base"], "explicacao": explic}


def pior(alertas: list[dict]) -> str:
    if not alertas:
        return "aceitavel"
    return max((a["nivel"] for a in alertas), key=NIVEIS.index)
