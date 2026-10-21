"""Seção "Por que essa pergunta importa" de cada dashboard.

SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.

POR_QUE traz, por pergunta do catálogo, por que ela é relevante para a gestão do
SUS-SP e ações gerais ligadas ao tema. ACOES_ALERTA liga cada regra de
app/alerts.py a uma ação de melhoria: `secao()` usa os alertas já calculados no
dashboard, então as recomendações mudam com a pergunta e com os filtros.
"""
from __future__ import annotations

from app.alerts import NIVEIS

POR_QUE: dict[str, dict] = {
    "visao_geral": {
        "importancia": "É o ponto de partida do gestor: mostra o tamanho da demanda hospitalar, quanto ela custa e "
                       "onde se concentra. Sem essa visão, decisões sobre leitos, orçamento e regionalização são "
                       "tomadas no escuro.",
        "acoes": ["Acompanhar estes indicadores mensalmente num painel da Secretaria, com metas por DRS.",
                  "Usar as principais causas para priorizar linhas de cuidado (ex.: gestante, cardiovascular, "
                  "respiratória)."]},
    "custos": {
        "importancia": "O orçamento do SUS é limitado: saber quais causas consomem mais recursos (e se o custo vem "
                       "do volume ou do valor por internação) mostra onde a prevenção e a eficiência dão mais retorno.",
        "acoes": ["Para causas caras por volume, investir em prevenção e acompanhamento na atenção primária.",
                  "Para causas caras por internação, revisar protocolos, uso de UTI e tempo de permanência.",
                  "Negociar contratualização por desempenho com os hospitais que mais faturam nessas causas."]},
    "sazonal_estado": {
        "importancia": "A demanda não é constante ao longo do ano. Conhecer os meses de pico permite antecipar "
                       "escalas de profissionais, leitos de retaguarda e compras de insumos, em vez de reagir à "
                       "lotação quando ela já aconteceu.",
        "acoes": ["Montar um plano de contingência sazonal com gatilhos (ex.: ocupação acima de 85%) para abrir "
                  "leitos extras.",
                  "Programar cirurgias eletivas para os meses de menor demanda."]},
    "sazonal_drs": {
        "importancia": "O pico não acontece no mesmo mês em todo o estado. Saber quando cada DRS fica mais pressionada "
                       "permite remanejar recursos entre regiões, em vez de reforçar todas ao mesmo tempo.",
        "acoes": ["Escalonar o reforço de leitos e equipes conforme o calendário de pico de cada DRS.",
                  "Pactuar entre DRS vizinhas o apoio mútuo nos meses em que os picos não coincidem."]},
    "sazonal_causas": {
        "importancia": "Causas sazonais (respiratórias, infecciosas) são em boa parte evitáveis com ações de "
                       "prevenção feitas na hora certa. Elas também explicam a maior parte da sobrecarga dos meses "
                       "de pico.",
        "acoes": ["Concentrar campanhas de vacinação (gripe, VSR, COVID) antes do pico das respiratórias.",
                  "Intensificar o combate ao Aedes aegypti antes da alta das infecciosas (dengue)."]},
    "sazonal_cap_regiao": {
        "importancia": "Uma mesma doença tem intensidade e calendário diferentes em cada região. Isso define onde e "
                       "quando as ações de prevenção e os leitos específicos (ex.: pediátricos no inverno) fazem "
                       "mais diferença.",
        "acoes": ["Direcionar campanhas e leitos sazonais primeiro às DRS com pico mais intenso.",
                  "Ajustar o calendário de cada ação ao mês de pico da região, não à média do estado."]},
    "ranking_municipios": {
        "importancia": "Taxas de internação muito acima das demais costumam indicar falhas na atenção primária, "
                       "população mais vulnerável ou excesso de internações evitáveis. São os municípios onde "
                       "intervir traz mais benefício.",
        "acoes": ["Analisar nesses municípios as internações por condições sensíveis à atenção primária (ICSAP).",
                  "Ampliar cobertura da Estratégia Saúde da Família e o acompanhamento de crônicos.",
                  "Conferir se a taxa alta não vem de pacientes de fora atendidos como residentes (qualidade do "
                  "cadastro)."]},
    "ranking_hospitais": {
        "importancia": "Poucos hospitais concentram grande parte das internações. Eles são estratégicos: qualquer "
                       "falha neles (lotação, falta de insumo, greve) afeta toda a rede regional.",
        "acoes": ["Priorizar esses hospitais em contratos de metas, auditoria e planos de contingência.",
                  "Fortalecer hospitais de menor porte da região para desafogar os maiores."]},
    "ranking_permanencia": {
        "importancia": "Permanência longa ocupa leitos que poderiam atender outros pacientes e aumenta o risco de "
                       "infecção hospitalar. Pode refletir casos complexos, mas também atraso em exames, alta ou "
                       "transferência.",
        "acoes": ["Implantar ou fortalecer o Núcleo Interno de Regulação (NIR) e a gestão de leitos.",
                  "Auditar internações longas para separar complexidade clínica de atrasos evitáveis.",
                  "Ampliar atenção domiciliar e leitos de cuidados prolongados para desospitalizar."]},
    "comparar_municipios": {
        "importancia": "Comparar municípios parecidos mostra se uma diferença é problema local ou padrão regional, e "
                       "ajuda a identificar boas práticas que podem ser copiadas.",
        "acoes": ["Usar o município com melhores indicadores como referência (benchmarking) para o outro.",
                  "Investigar a origem das diferenças: estrutura, perfil da população ou fluxo de pacientes."]},
    "perfil_municipio": {
        "importancia": "Reúne num só lugar o que o gestor municipal precisa para planejar: quanto a população interna, "
                       "por quê, onde e com que resultado. É a base para o plano municipal de saúde.",
        "acoes": ["Levar estes indicadores ao plano municipal de saúde e à Comissão Intergestores Regional (CIR).",
                  "Priorizar as principais causas de internação nas ações da atenção primária do município."]},
    "polos_atracao": {
        "importancia": "Os polos atendem pacientes de outras cidades e por isso carregam custo e lotação que não são "
                       "só seus. O fluxo mostra onde a rede local é insuficiente e quem financia o atendimento de quem.",
        "acoes": ["Revisar a Programação Pactuada e Integrada (PPI) para que os recursos acompanhem os pacientes.",
                  "Fortalecer a resolutividade dos municípios de origem nas internações de média complexidade.",
                  "Organizar transporte sanitário e regulação (CROSS) entre os municípios e o polo."]},
    "capacidade_municipios": {
        "importancia": "Muitas internações por leito indicam estrutura no limite: pouca folga para picos, mais "
                       "espera e risco de altas precoces. Mostra onde faltam leitos em relação à demanda.",
        "acoes": ["Avaliar ampliação ou habilitação de leitos SUS onde a pressão é maior.",
                  "Melhorar o giro de leitos (alta planejada, NIR) antes de expandir a estrutura."]},
    "ocupacao_hospitais": {
        "importancia": "Acima de 85% de ocupação, hospitais passam a ter fila no pronto-socorro, cancelamento de "
                       "cirurgias e mais risco ao paciente. Identificar esses hospitais orienta a regulação de vagas.",
        "acoes": ["Redirecionar casos pela regulação estadual (CROSS) para hospitais com folga na mesma região.",
                  "Abrir leitos de retaguarda (clínicos e de cuidados prolongados) para liberar os leitos agudos."]},
    "capacidade_drs": {
        "importancia": "A distribuição de leitos e UBS entre as DRS mostra desigualdades regionais na oferta. É a "
                       "informação usada para decidir onde investir em novas unidades.",
        "acoes": ["Priorizar investimentos nas DRS com menos leitos e UBS por habitante.",
                  "Usar os indicadores no Plano Diretor de Regionalização (PDR) do estado."]},
    "ubs_internacoes": {
        "importancia": "Uma atenção primária forte deveria evitar parte das internações. Ver como UBS e internações se "
                       "relacionam ajuda a avaliar se a rede básica está cumprindo esse papel.",
        "acoes": ["Expandir a cobertura de UBS e equipes de Saúde da Família onde ela é baixa.",
                  "Medir a resolutividade das UBS (ICSAP), não só a quantidade de unidades."]},
    "clusters": {
        "importancia": "Municípios diferentes precisam de políticas diferentes. Agrupar os que têm perfil parecido "
                       "permite desenhar uma estratégia por grupo, em vez de uma política única para 645 municípios.",
        "acoes": ["Definir uma estratégia por grupo (ex.: regionalização para os que internam fora; atenção "
                  "primária para os de taxa alta).",
                  "Usar os grupos para escolher municípios-piloto e comparar resultados entre pares."]},
    "fatores": {
        "importancia": "Antes de investir, é preciso entender o que está associado à demanda: necessidade da "
                       "população (ex.: idosos) ou oferta de serviços (leitos, UBS). Sem isso, mais estrutura pode só "
                       "revelar demanda reprimida.",
        "acoes": ["Planejar a rede considerando o envelhecimento da população nos municípios com mais idosos.",
                  "Tratar os resultados como associação, não causa: validar com estudos locais antes de decidir."]},
}

ACOES_ALERTA: dict[str, str] = {
    "ocupacao": "Ocupação alta: abrir leitos de retaguarda, melhorar o giro de leitos e regular casos pela CROSS para "
                "hospitais com folga.",
    "taxa": "Taxa de internação alta: investigar internações por condições sensíveis à atenção primária e reforçar "
            "o acompanhamento de crônicos (hipertensão, diabetes, gestantes).",
    "permanencia": "Permanência longa: auditar os casos longos, agilizar exames e altas e ampliar atenção "
                   "domiciliar para desospitalizar.",
    "mortalidade": "Mortalidade acima da média: revisar óbitos em comissão, conferir protocolos assistenciais e a "
                   "gravidade dos casos recebidos.",
    "int_por_leito": "Muitas internações por leito: avaliar ampliação de leitos SUS ou regionalizar parte da demanda.",
    "pct_fora": "Muitos residentes internados fora: pactuar a referência regional (PPI), garantir transporte "
                "sanitário e ampliar a resolutividade local.",
    "pico_sazonal": "Pico sazonal forte: antecipar vacinação e campanhas e abrir leitos sazonais antes do mês de "
                    "pico.",
    "leitos_10k": "Poucos leitos por habitante: priorizar a região na expansão ou habilitação de leitos SUS.",
    "pct_hosp_criticos": "Muitos hospitais lotados: redistribuir a demanda entre hospitais e criar uma central de "
                         "leitos regional.",
    "pct_mun_criticos": "Muitos municípios com taxa crítica: apoio técnico da DRS a esses municípios, com foco em "
                        "atenção primária.",
}


def secao(question_id: str, alertas: list[dict]) -> dict:
    """Importância da pergunta, problemas encontrados (Alerta/Crítico) e ações sugeridas."""
    base = POR_QUE[question_id]
    ruins = sorted((a for a in alertas if a["nivel"] != "aceitavel"),
                   key=lambda a: -NIVEIS.index(a["nivel"]))
    acoes: list[str] = []
    for a in ruins:
        acao = ACOES_ALERTA.get(a.get("chave"))
        if acao and acao not in acoes:
            acoes.append(acao)
    acoes += base["acoes"]
    if ruins:
        resumo = (f"{len(ruins)} indicador{'es' if len(ruins) > 1 else ''} fora do aceitável. "
                  "As primeiras ações atacam esses pontos.")
    else:
        resumo = "Nenhum indicador fora do aceitável: as ações abaixo servem para manter a situação."
    return {"importancia": base["importancia"], "resumo": resumo,
            "problemas": [{"nivel": a["nivel"], "indicador": a["indicador"], "valor": a["valor"]} for a in ruins],
            "acoes": acoes}
