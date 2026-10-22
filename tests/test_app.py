"""Testes do matcher, dos builders e da API (precisam do banco data/sqladies.db)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import dashboards
from app.main import app
from app.matcher import extrair, match
from app.questions import CATALOGO

client = TestClient(app)


@pytest.mark.parametrize("q", CATALOGO, ids=lambda q: q.id)
def test_catalogo_casa_consigo_mesmo(q):
    m = match(q.texto)
    assert m.question is not None and m.question.id == q.id


@pytest.mark.parametrize("texto,esperado", [
    ("compare Santos e Guarujá", "comparar_municipios"),
    ("quais meses têm mais internações?", "sazonal_estado"),
    ("top 10 hospitais da DRS VII", "ranking_hospitais"),
    ("hospitais de campinas", "ranking_hospitais"),
    ("quais hospitais ficam mais lotados", "ocupacao_hospitais"),
    ("quanto custa cada doença", "custos"),
    ("doenças respiratórias por DRS", "sazonal_cap_regiao"),
    ("Mostre o panorama de internações de São Paulo", "perfil_municipio"),
    ("relação entre ubs e internações", "ubs_internacoes"),
])
def test_variacoes(texto, esperado):
    m = match(texto)
    assert m.question is not None and m.question.id == esperado


def test_sem_correspondencia_sugere():
    m = match("bolo de chocolate")
    assert m.question is None and len(m.sugestoes) == 3


def test_extrai_entidades():
    p, _ = extrair("top 10 municípios da DRS de Bauru em 2025 com doenças respiratórias")
    assert p["drs"] == 6 and p["ano"] == 2025 and p["top_n"] == 10 and p["cap_cid"] == "X"
    p, _ = extrair("compare Santos e Guarujá")
    assert p["municipios"] == [354850, 351870]
    p, _ = extrair("qual o panorama geral do estado de São Paulo?")
    assert "municipios" not in p


@pytest.mark.parametrize("q", CATALOGO, ids=lambda q: q.id)
def test_builders_retornam_dashboard(q):
    d = dashboards.build(q.id, dict(q.exemplo_params))
    assert d["title"] and d["charts"] and d["insights"]
    for c in d["charts"]:
        assert c["traces"], c["title"]
    json.dumps(d, default=float)


@pytest.mark.parametrize("params", [{"ano": 2025}, {"drs": 7}, {"cap_cid": "X"}, {"municipios": [350950]}])
def test_builders_com_filtros(params):
    for q in CATALOGO:
        dashboards.build(q.id, {**q.exemplo_params, **params})


def test_api():
    assert client.get("/api/health").json()["ok"]
    assert len(client.get("/api/questions").json()["categorias"]) == 5
    r = client.post("/api/ask", json={"text": "hospitais de Campinas em 2025"}).json()
    assert r["matched"] and r["question_id"] == "ranking_hospitais" and r["params"]["ano"] == 2025
    r = client.post("/api/ask", json={"text": "xyz", "question_id": "fatores"}).json()
    assert r["question_id"] == "fatores"
    assert client.post("/api/ask", json={"text": ""}).status_code == 400


# ------------------------------------------------------------ alertas e SQL --
from app import alerts as A  # noqa: E402
from app.sql_oracle import oracle_sql  # noqa: E402

FILTROS = [{}, {"ano": 2025}, {"drs": 7}, {"cap_cid": "X"}, {"municipios": [350950, 354340]}]


@pytest.mark.parametrize("q", CATALOGO, ids=lambda q: q.id)
def test_alertas_em_todo_dashboard(q):
    d = dashboards.build(q.id, dict(q.exemplo_params))
    assert d["alertas"], q.id
    assert d["status_geral"] in A.NIVEIS
    for a in d["alertas"]:
        assert a["nivel"] in A.NIVEIS and a["rotulo"] and a["indicador"] and a["valor"]
    assert d["status_geral"] == A.pior(d["alertas"])


def test_limiares_de_borda():
    assert A.nivel("ocupacao", 75) == "aceitavel"
    assert A.nivel("ocupacao", 75.1) == "alerta"
    assert A.nivel("ocupacao", 85) == "alerta"
    assert A.nivel("ocupacao", 85.1) == "critico"
    assert A.nivel("leitos_10k", 15) == "aceitavel"
    assert A.nivel("leitos_10k", 12) == "alerta"
    assert A.nivel("leitos_10k", 9.9) == "critico"
    assert A.nivel("taxa", 110, ref=100) == "aceitavel"
    assert A.nivel("taxa", 125, ref=100) == "alerta"
    assert A.nivel("taxa", 131, ref=100) == "critico"
    assert A.nivel("ocupacao", None) is None
    assert A.pior([{"nivel": "aceitavel"}, {"nivel": "critico"}, {"nivel": "alerta"}]) == "critico"


@pytest.mark.parametrize("q", CATALOGO, ids=lambda q: q.id)
def test_sql_oracle(q):
    for f in FILTROS:
        blocos = oracle_sql(q.id, {**q.exemplo_params, **f})
        assert blocos
        for b in blocos:
            sql = b["sql"]
            assert "adaptação demonstrativa do projeto entregue à Oracle" in sql
            assert "SELECT" in sql and "LIMIT" not in sql
            assert sql.rstrip().endswith(";")


def test_sql_oracle_ignora_valores_inseguros():
    sql = " ".join(b["sql"] for b in oracle_sql("ranking_hospitais",
                                                 {"ano": "2025; DROP TABLE x", "cap_cid": "X' OR '1'='1",
                                                  "carater": "qualquer", "municipios": ["1 OR 1=1", 350950]}))
    assert "DROP" not in sql and "OR '1'" not in sql and "qualquer" not in sql
    assert "350950" in sql


def test_api_inclui_alertas_e_sql():
    r = client.post("/api/ask", json={"text": "Quais hospitais têm a maior ocupação estimada de leitos?"}).json()
    d = r["dashboard"]
    assert d["alertas"] and d["sql"] and d["status_geral"] in A.NIVEIS
    assert any(c["fmt"] == "status" for t in d["tables"] for c in t["columns"])


# ------------------------------------------------- por que a pergunta importa ---
from app import relevancia as R  # noqa: E402


def test_relevancia_cobre_catalogo_e_regras():
    assert {q.id for q in CATALOGO} == set(R.POR_QUE)
    assert set(A.REGRAS) == set(R.ACOES_ALERTA)


@pytest.mark.parametrize("q", CATALOGO, ids=lambda q: q.id)
def test_relevancia_em_todo_dashboard(q):
    r = dashboards.build(q.id, q.exemplo_params)["relevancia"]
    assert r["importancia"] and r["acoes"] and r["resumo"]
    assert all(p["nivel"] in ("alerta", "critico") for p in r["problemas"])


def test_relevancia_prioriza_criticos():
    al = [A.classificar("leitos_10k", 20), A.classificar("pct_fora", 40), A.classificar("ocupacao", 95)]
    r = R.secao("capacidade_drs", al)
    assert [p["nivel"] for p in r["problemas"]] == ["critico", "alerta"]
    assert r["acoes"][:2] == [R.ACOES_ALERTA["ocupacao"], R.ACOES_ALERTA["pct_fora"]]
    assert R.secao("capacidade_drs", [al[0]])["acoes"] == R.POR_QUE["capacidade_drs"]["acoes"]


def test_api_relevancia():
    d = client.post("/api/ask", json={"text": "Quais hospitais têm a maior ocupação estimada de leitos?"}).json()
    assert d["dashboard"]["relevancia"]["importancia"]


# ------------------------------------------ próxima pergunta dentro da aba ---
from app.questions import POR_ID, SEGUINTES  # noqa: E402


def test_seguintes_validos():
    assert set(SEGUINTES) == set(POR_ID)
    for qid, prox in SEGUINTES.items():
        assert 2 <= len(prox) <= 3 and qid not in prox and len(set(prox)) == len(prox)
        assert all(i in POR_ID for i in prox)


def test_api_seguintes_e_categoria():
    d = client.post("/api/ask", json={"text": "Qual o panorama geral das internações SUS no estado?"}).json()
    seg = d["dashboard"]["seguintes"]
    assert 2 <= len(seg) <= 3 and all(x["id"] and x["texto"] for x in seg)
    cats = client.get("/api/questions").json()["categorias"]
    assert all(q["categoria"] == c["nome"] for c in cats for q in c["perguntas"])


# --------------------------------------------------------- filtros editáveis ---
from app.matcher import validar_params  # noqa: E402
from app.questions import FILTROS as FILTROS_Q  # noqa: E402

VALORES = {"ano": 2025, "drs": 7, "cap_cid": "X", "carater": "Urgência", "municipios": [350950, 354340, 355030],
           "top_n": 10}


def test_filtros_cobrem_catalogo():
    assert set(FILTROS_Q) == set(POR_ID)
    assert all(set(v) <= set(VALORES) for v in FILTROS_Q.values())


@pytest.mark.parametrize("q", CATALOGO, ids=lambda q: q.id)
def test_cada_filtro_aceito_constroi(q):
    for k in FILTROS_Q[q.id]:
        params = validar_params({k: VALORES[k]}, q.id)
        assert k in params
        dashboards.build(q.id, params)


def test_validar_params_lista_branca():
    sujo = {"ano": "1999", "drs": 99, "cap_cid": "X' OR 1=1 --", "carater": "Qualquer", "top_n": 999,
            "municipios": ["350950; DROP TABLE x", 1, 350950], "extra": "x"}
    assert validar_params(sujo, "ranking_hospitais") == {"top_n": 50, "municipios": [350950]}
    assert validar_params({"ano": 2025, "drs": "7"}, "custos") == {"ano": 2025, "drs": 7}
    assert validar_params({"cap_cid": "X"}, "custos") == {}  # custos não filtra por causa
    assert validar_params({}, "sazonal_cap_regiao") == {"cap_cid": "X"}  # obrigatório volta ao exemplo
    assert validar_params({"municipios": [355030]}, "comparar_municipios")["municipios"] == [355030, 350950]
    assert len(validar_params({"municipios": [350950, 354340, 355030, 355220]}, "comparar_municipios")["municipios"]) == 3
    assert validar_params("nao e dict", "visao_geral") == {}


def test_api_aplica_filtros():
    r = client.post("/api/ask", json={"text": "panorama", "question_id": "visao_geral",
                                      "params": {"ano": 2025, "drs": 7}}).json()
    assert r["params"] == {"ano": 2025, "drs": 7}
    assert r["dashboard"]["filtros"] == ["2025", "DRS VII - Campinas"]
    assert r["filtros_aceitos"]["chaves"] == list(FILTROS_Q["visao_geral"])
    assert any("2025" in b["sql"] for b in r["dashboard"]["sql"])


# -------------------------------------------------------------------- mapa ---
from pathlib import Path  # noqa: E402

from app import db  # noqa: E402

GEOJSON = Path(__file__).resolve().parents[1] / "static" / "vendor" / "sp_municipios.geojson"
COM_MAPA = ["ranking_municipios", "polos_atracao", "capacidade_municipios", "ubs_internacoes", "clusters"]


def _area(anel):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anel, anel[1:])) / 2


def test_geojson_cobre_municipios_e_orientacao():
    g = json.loads(GEOJSON.read_text(encoding="utf-8"))
    ids = {f["id"] for f in g["features"]}
    assert ids == set(db.municipios()["cod_mun"].astype(int))
    # anel externo no sentido horário (o que o Plotly espera)
    for f in g["features"]:
        pols = [f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon" else f["geometry"]["coordinates"]
        assert all(_area(pol[0]) < 0 for pol in pols)
    assert (GEOJSON.parent / "topojson" / "world_110m.json").exists()


@pytest.mark.parametrize("qid", COM_MAPA)
@pytest.mark.parametrize("params", [{}, {"drs": 6}])
def test_dashboards_com_mapa(qid, params):
    ids = {f["id"] for f in json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]}
    d = dashboards.build(qid, validar_params(params, qid))
    mapas = [t for c in d["charts"] for t in c["traces"] if t["type"] == "choropleth"]
    assert mapas and all(t["geojson"] == "sp" and set(t["locations"]) <= ids for t in mapas)
    if params.get("drs") and "drs" in FILTROS_Q[qid]:  # grupos (K-means) não filtra por DRS
        regiao = set(db.municipios().query("drs_num == 6")["cod_mun"].astype(int))
        assert all(set(t["locations"]) <= regiao for t in mapas)


# ------------------------------------------------------------ desempenho ---
def test_cache_de_dashboards():
    a = dashboards.build("visao_geral", {"ano": 2025}, "pergunta um")
    a["title"] = "alterado"  # alterar a resposta não pode contaminar o cache
    b = dashboards.build("visao_geral", {"ano": 2025}, "pergunta dois")
    assert b["title"] != "alterado"
    assert any("pergunta dois" in x["sql"] for x in b["sql"])  # a query acompanha o texto
    assert dashboards.build("visao_geral", {"ano": 2024})["kpis"] != b["kpis"]  # filtros diferentes, cache diferente


def test_extrai_municipios_compostos_e_ordem():
    p, _ = extrair("hospitais de sao jose do rio preto e sao jose dos campos")
    assert p["municipios"] == [354980, 354990]
    p, _ = extrair("compare guarujá e santos")
    assert p["municipios"] == [351870, 354850]


def test_gzip_e_cache_do_vendor():
    r = client.get("/static/vendor/plotly.min.js", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip" and "max-age" in r.headers["cache-control"]
    assert "max-age" not in client.get("/static/js/app.js").headers.get("cache-control", "")


# ----------------------------------------------------------------- rotas ---
def test_rotas_landing_e_aplicacao():
    r = client.get("/app")
    assert r.status_code == 200 and 'id="composer"' in r.text and "/static/css/base.css" in r.text
    r = client.get("/")
    assert r.status_code == 200 and "Abrir o DataCare" in r.text and 'href="/app"' in r.text
    assert "landing.css" in r.text and "plotly" not in r.text  # landing leve, sem Plotly
    d = client.get("/api/resumo").json()
    assert d["municipios"] == 645 and d["internacoes"] > 5_000_000 and d["analises"] == len(CATALOGO)
    for f in ("static/marca/app-claro.webp", "static/marca/mapa-claro.webp", "static/marca/app-escuro.webp", "static/vendor/fonts/Geist-Variable.woff2"):
        assert client.get("/" + f).status_code == 200
