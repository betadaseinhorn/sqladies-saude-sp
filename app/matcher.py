"""Casa o texto digitado com uma pergunta do catálogo, sem internet nem LLM.

1. Normaliza o texto (minúsculas, sem acentos).
2. Extrai entidades: municípios, DRS, ano, capítulo da CID, top N.
3. Pontua cada pergunta: similaridade fuzzy com o texto da pergunta + palavras-chave
   + pistas vindas das entidades (ex.: dois municípios → comparação).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from rapidfuzz import fuzz

from app import db
from app.questions import CATALOGO, FILTROS, MUN_MAX, OBRIGATORIOS, POR_ID, Question

LIMIAR = 52  # abaixo disso, o chat sugere perguntas em vez de responder

# Nomes de município que também são palavras comuns e geram falso positivo
IGNORAR_MUN = {"panorama", "paraiso", "bastos", "lins", "itu", "areias", "flora rica", "salto",
               "estrela do norte", "santa cruz da conceicao"}

CID_PALAVRAS = [
    (r"respirat|pneumon|gripe|asma|bronq", "X"),
    (r"circulat|cardio|coracao|infarto|avc|hipertens", "IX"),
    (r"infecc|dengue|parasit|sepse|chikungunya", "I"),
    (r"parto|gravid|gestac|obstet|gestant", "XV"),
    (r"neoplas|cancer|tumor|oncolog", "II"),
    (r"mental|psiqui|depress|alcool|drogas", "V"),
    (r"lesao|lesoes|trauma|fratura|acidente|envenen|violenc", "XIX"),
    (r"digestiv|gastro|figado|apendic", "XI"),
    (r"geniturin|urinar|renal|\brim\b|rins", "XIV"),
    (r"osteomusc|ortoped|coluna|articula", "XIII"),
    (r"perinatal|recem.nascido|neonat", "XVI"),
    (r"\bolho|oftalm|catarata", "VII"),
    (r"endocrin|diabet|metabol|obesid", "IV"),
    (r"sistema nervoso|neurol|epileps", "VI"),
    (r"\bpele\b|dermat", "XII"),
]

ROMANOS = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
           "xiii", "xiv", "xv", "xvi", "xvii"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Match:
    question: Question | None
    score: float
    params: dict = field(default_factory=dict)
    sugestoes: list[Question] = field(default_factory=list)


@lru_cache(maxsize=1)
def _mun_index() -> list[tuple[str, int, str]]:
    m = db.municipios()
    idx = [(norm(n), int(c), n) for c, n in zip(m["cod_mun"], m["nome"])]
    idx = [t for t in idx if t[0] not in IGNORAR_MUN]
    return sorted(idx, key=lambda t: -len(t[0]))  # nomes mais longos primeiro


@lru_cache(maxsize=1)
def _drs_index() -> list[tuple[str, int]]:
    d = db.drs()
    out = []
    for num, nome in zip(d["drs_num"], d["drs_nome"]):
        base = norm(nome.split(" - ", 1)[1])
        out.append((base, int(num)))
    return sorted(out, key=lambda t: -len(t[0]))


def extrair(texto: str) -> tuple[dict, str]:
    """Retorna (params, texto_restante_sem_entidades)."""
    t = f" {norm(texto)} "
    params: dict = {}

    # DRS: "drs vii", "drs 7", "drs de campinas", "drs campinas"
    m = re.search(r"\bdrs\s+(?:de |da |do )?([a-z0-9 ]+)", t)
    if m:
        resto = m.group(1).strip()
        tok = resto.split(" ")[0]
        if tok in ROMANOS:
            params["drs"] = ROMANOS.index(tok) + 1
        elif tok.isdigit() and 1 <= int(tok) <= 17:
            params["drs"] = int(tok)
        else:
            for base, num in _drs_index():
                if resto.startswith(base):
                    params["drs"] = num
                    t = t.replace(base, " ", 1)
                    break
        if "drs" in params:
            t = re.sub(r"\b(?:na |da |do )?drs\s+(?:de |da |do )?(?:[ivx]+\b|\d{1,2}\b)?", " ", t, count=1)

    # Municípios (ordem de aparição no texto)
    t_sem_estado = re.sub(r"estado de sao paulo|estado de sp|\bsp\b", " ", t)
    achados = []
    for nome_n, cod, _ in _mun_index():
        for mm in re.finditer(rf"\b{re.escape(nome_n)}\b", t_sem_estado):
            achados.append((mm.start(), cod, nome_n))
            t_sem_estado = (t_sem_estado[:mm.start()] + " " * len(nome_n)
                            + t_sem_estado[mm.end():])
    if achados:
        achados.sort()
        params["municipios"] = list(dict.fromkeys(c for _, c, _ in achados))
        for _, _, nome_n in achados:
            t = t.replace(nome_n, " ", 1)

    anos = [int(a) for a in re.findall(r"\b(20\d\d)\b", t) if int(a) in db.anos()]
    if anos:
        params["ano"] = anos[0]

    for padrao, cap in CID_PALAVRAS:
        if re.search(padrao, t):
            params["cap_cid"] = cap
            break

    m = re.search(r"\btop\s*(\d{1,2})\b|\b(\d{1,2})\s+(?:municipios|hospitais|maiores|cidades|primeiros)", t)
    if m:
        params["top_n"] = max(3, min(50, int(m.group(1) or m.group(2))))

    if "eletiv" in t:
        params["carater"] = "Eletivo"
    elif re.search(r"\b(?:de|em) (?:urgencia|emergencia)", t):
        params["carater"] = "Urgência"

    restante = re.sub(r"\b20\d\d\b", " ", t)
    return params, re.sub(r"\s+", " ", restante).strip()


def _pontuar(q: Question, texto: str, params: dict) -> float:
    qn = norm(q.texto)
    s = 0.55 * fuzz.token_set_ratio(texto, qn) + 0.25 * fuzz.partial_ratio(texto, qn)
    hits = sum(1 for k in q.keywords if re.search(rf"\b{re.escape(k)}", texto))
    s += min(hits, 3) * 9
    n_mun = len(params.get("municipios", []))
    if q.id == "comparar_municipios":
        s += 30 if n_mun >= 2 else -20
    if q.id == "perfil_municipio":
        s += 22 if n_mun == 1 else -20
    if q.id == "sazonal_cap_regiao" and "cap_cid" in params:
        s += 12
    if q.id == "sazonal_estado" and "drs" in params and "sazonal" in texto:
        s += 25
    if (q.id == "ranking_hospitais" and n_mun and re.search(r"\bhospita", texto)
            and not re.search(r"lotad|ocupa|permanen|tempo", texto)):
        s += 15
    if q.id == "capacidade_drs" and re.search(r"\bregi(ao|oes)\b|\bdrs\b", texto):
        s += 15
    return s


def validar_params(params: dict, question_id: str) -> dict:
    """Filtros escolhidos na barra do dashboard: só valores da lista branca e aceitos pela pergunta.

    Tudo o que não for reconhecido é descartado, então nenhum valor livre chega ao SQL.
    """
    aceitos = set(FILTROS[question_id])
    out: dict = {}
    p = params if isinstance(params, dict) else {}

    def inteiro(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    if "ano" in aceitos and inteiro(p.get("ano")) in db.anos():
        out["ano"] = inteiro(p["ano"])
    if "drs" in aceitos and inteiro(p.get("drs")) in set(db.drs()["drs_num"].astype(int)):
        out["drs"] = inteiro(p["drs"])
    if "cap_cid" in aceitos and p.get("cap_cid") in set(db.capitulos()["cap_cod"]):
        out["cap_cid"] = p["cap_cid"]
    if "carater" in aceitos and p.get("carater") in ("Eletivo", "Urgência"):
        out["carater"] = p["carater"]
    if "top_n" in aceitos and inteiro(p.get("top_n")) is not None:
        out["top_n"] = max(3, min(50, inteiro(p["top_n"])))
    if "municipios" in aceitos and isinstance(p.get("municipios"), list):
        validos = set(db.municipios()["cod_mun"].astype(int))
        cods = [c for c in (inteiro(x) for x in p["municipios"]) if c in validos]
        cods = list(dict.fromkeys(cods))[:MUN_MAX.get(question_id, 4)]
        if cods:
            out["municipios"] = cods
    # perguntas que precisam de um valor voltam ao exemplo do catálogo
    for k in OBRIGATORIOS.get(question_id, ()):
        if k not in out and k in POR_ID[question_id].exemplo_params:
            out[k] = POR_ID[question_id].exemplo_params[k]
    if question_id == "comparar_municipios" and len(out.get("municipios", [])) < 2:
        got = out.get("municipios", [])
        out["municipios"] = (got + [c for c in POR_ID[question_id].exemplo_params["municipios"] if c not in got])[:2]
    return out


def match(texto: str, question_id: str | None = None) -> Match:
    params, restante = extrair(texto)
    if question_id and question_id in POR_ID:
        q = POR_ID[question_id]
        return Match(q, 100.0, {**q.exemplo_params, **params})
    ranking = sorted(((_pontuar(q, restante, params), q) for q in CATALOGO),
                     key=lambda t: -t[0])
    score, best = ranking[0]
    sugestoes = [q for _, q in ranking[:3]]
    if score < LIMIAR:
        return Match(None, score, params, sugestoes)
    # parâmetros-exemplo só entram quando o usuário não informou o equivalente
    p = dict(params)
    for k, v in best.exemplo_params.items():
        if k == "municipios":
            needed = 2 if best.id == "comparar_municipios" else 1
            got = p.get("municipios", [])
            if len(got) < needed:
                p["municipios"] = (got + [c for c in v if c not in got])[:needed]
        else:
            p.setdefault(k, v)
    return Match(best, score, p, sugestoes[1:])
