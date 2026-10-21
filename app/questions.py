"""Catálogo de perguntas pré-definidas.

As perguntas saíram da análise exploratória (analysis/eda.ipynb). Cada uma tem
palavras-chave usadas pelo matcher e um builder em app/dashboards.py com o mesmo id.
Parâmetros opcionais (município, DRS, ano, capítulo da CID, top N) são extraídos
do texto digitado pelo usuário.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Question:
    id: str
    texto: str
    categoria: str
    keywords: tuple[str, ...]
    exemplo_params: dict = field(default_factory=dict)


CATEGORIAS = ("Visão geral", "Sazonalidade", "Rankings e comparações", "Capacidade",
              "Padrões e fatores")

CATALOGO: list[Question] = [
    Question("visao_geral", "Qual o panorama geral das internações SUS no estado?",
             "Visão geral", ("panorama", "geral", "resumo", "visao", "estado", "total",
                             "quantas internacoes", "overview")),
    Question("custos", "Quais causas de internação mais custam ao SUS?",
             "Visão geral", ("custo", "custa", "custam", "gasto", "quanto", "valor", "caro", "dinheiro", "pago",
                             "valores pagos")),

    Question("sazonal_estado", "Como as internações variam ao longo dos meses?",
             "Sazonalidade", ("sazonal", "sazonalidade", "meses", "quais meses", "mes", "mensal", "epoca do ano",
                              "ao longo do ano", "tendencia", "variam", "serie")),
    Question("sazonal_drs", "Em quais meses as internações aumentam em cada DRS?",
             "Sazonalidade", ("cada drs", "por drs", "regioes", "regional", "aumentam",
                              "pico", "cada regiao")),
    Question("sazonal_causas", "Quais causas de internação têm maior sazonalidade?",
             "Sazonalidade", ("causas", "doencas", "capitulo", "cid", "sazonalidade",
                              "sazonais", "diagnostico")),
    Question("sazonal_cap_regiao",
             "Como a sazonalidade das doenças respiratórias varia entre as DRS?",
             "Sazonalidade", ("respiratorias", "respiratoria", "varia entre", "inverno",
                              "outono", "estacao", "dengue", "infecciosas", "doencas"),
             {"cap_cid": "X"}),

    Question("ranking_municipios",
             "Quais os 20 municípios com mais internações por habitante?",
             "Rankings e comparações", ("municipios", "ranking", "por habitante", "taxa",
                                        "mais internacoes", "top", "maiores", "cidades")),
    Question("ranking_hospitais", "Quais hospitais realizam mais internações?",
             "Rankings e comparações", ("hospitais", "hospital", "ranking", "realizam",
                                        "mais internacoes", "volume", "maiores")),
    Question("ranking_permanencia", "Quais hospitais têm maior permanência média?",
             "Rankings e comparações", ("permanencia", "tempo de internacao", "dias",
                                        "hospitais", "media", "demora")),
    Question("comparar_municipios", "Compare as internações de Campinas e Ribeirão Preto",
             "Rankings e comparações", ("compare", "comparar", "comparacao", "versus", "vs",
                                        "entre", "diferenca"),
             {"municipios": [350950, 354340]}),
    Question("perfil_municipio", "Mostre o panorama de internações de Sorocaba",
             "Rankings e comparações", ("mostre", "panorama de", "perfil", "situacao",
                                        "como esta", "dados de"),
             {"municipios": [355220]}),
    Question("polos_atracao", "Quais municípios recebem mais pacientes de outras cidades?",
             "Rankings e comparações", ("recebem", "outras cidades", "atraem", "polo", "regionais", "onde ficam",
                                        "fluxo", "pacientes de fora", "referencia")),

    Question("capacidade_municipios",
             "Quais municípios têm mais internações por leito SUS?",
             "Capacidade", ("leito", "leitos", "capacidade", "sobrecarga", "sobrecarregados",
                            "por leito")),
    Question("ocupacao_hospitais", "Quais hospitais têm a maior ocupação estimada de leitos?",
             "Capacidade", ("ocupacao", "lotados", "taxa de ocupacao", "hospitais", "leitos")),
    Question("capacidade_drs",
             "Como a estrutura hospitalar se distribui entre as DRS?",
             "Capacidade", ("estrutura", "distribui", "infraestrutura", "drs", "por regiao", "leitos",
                            "capacidade", "regioes", "regiao")),

    Question("ubs_internacoes", "Qual a relação entre UBS por habitante e internações?",
             "Padrões e fatores", ("ubs", "atencao basica", "atencao primaria", "relacao",
                                   "posto", "unidade basica")),
    Question("clusters", "Quais grupos de municípios têm perfis de demanda parecidos?",
             "Padrões e fatores", ("grupos", "cluster", "agrupamento", "perfis", "segmentacao",
                                   "parecidos", "semelhantes", "padroes")),
    Question("fatores", "Quais fatores estão associados ao aumento da demanda?",
             "Padrões e fatores", ("fatores", "associados", "aumento", "demanda", "explica",
                                   "influencia", "causa", "correlacao", "regressao")),
]

POR_ID = {q.id: q for q in CATALOGO}
