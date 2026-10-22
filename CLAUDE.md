# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SQLadies: a FastAPI + vanilla JS app that turns a question in Portuguese into a dashboard about SUS hospitalizations in the 645 municipalities of São Paulo state, 2024–2025.
- Data comes from SIH/SUS and CNES.
- It runs fully offline: no LLM and no CDN at runtime.

The repository is a demonstrative adaptation of the SQLadies work delivered to Oracle. Keep that framing in the README, in module docstrings, and in commit messages. Commits are written in Portuguese and say "adaptação demonstrativa do projeto entregue à Oracle".

UI text, comments, and identifiers are in Portuguese (`perguntar`, `turnos`, `filtros`). Match that.

## Commands

```bash
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
python setup_demo.py            # download the prebuilt DB (GitHub Release v1.0-dados, SHA-256 checked) → data/sqladies.db
python pipeline.py              # OR rebuild the DB from DATASUS/IBGE (~550 MB download, 10–20 min); --sem-download reuses data/raw
uvicorn app.main:app            # http://localhost:8000  (API docs at /api/docs)

pytest -q                                   # full suite (needs data/sqladies.db)
pytest -q tests/test_app.py::test_api       # one test
pytest -q -k "sql_oracle and fatores"       # one parametrized case (ids are question ids)
```

You can run individual pipeline stages as modules, for example `python -m etl.build_db`, `python -m analysis.run_all` or `python -m etl.build_mapa`.

There is no linter or build step. The front-end is static files under `static/`, served as they are.

## Architecture

**The data pipeline** (`pipeline.py`) runs these stages in order:
1. `etl/download_*` fetch the raw files into `data/raw`.
2. `etl/build_ref` builds the municipality, DRS and CID references.
3. `etl/transform_*` produce Parquet files.
4. `etl/build_db` builds the SQLite tables:
   - `fato_internacao`;
   - the aggregates `agg_mensal_hosp` (by place of hospitalization) and `agg_mensal_res` (by place of residence);
   - `fato_leitos`;
   - the `dim_*` tables.
5. `analysis/run_all` writes the precomputed result tables `res_*`, which hold STL seasonality, rankings, capacity, K-means and the WLS regression.

Points that are not obvious:
- `etl/dbc.py` is a pure-Python PKWare "blast" decompressor. The C-based `.dbc` readers do not build on Windows.
- Analyses use the admission month (`mes_inter`). AIHs with IDENT=5 (long stay) add to amounts but do not count as hospitalizations.

**How a question is answered** (`app/`):
1. `matcher.match(text, question_id)` normalizes the text and extracts entities (`municipios`, `drs`, `ano`, `cap_cid`, `top_n`, `carater`). It then scores the 18 catalog questions in `questions.py` with RapidFuzz plus keywords. Below `LIMIAR`, it returns suggestions instead of a match.
2. `dashboards.build(qid, params, pergunta)` dispatches to one builder per question through `BUILDERS`. Each builder returns KPIs, `alertas`, insights, chart specs, tables and `filtros`. `build()` then adds:
   - `status_geral`;
   - `relevancia` (`relevancia.py`);
   - `sql` (`sql_oracle.py`);
   - `seguintes` (2–3 follow-up questions).
3. When the request has `question_id` + `params`, the filter bar is in use. `main.py` then replaces the extracted params with `matcher.validar_params()`, a whitelist checked against the DB and against `FILTROS[qid]`.

Adding a question touches several places: `CATALOGO`, `FILTROS`, `SEGUINTES` (all in `questions.py`), `BUILDERS` (`dashboards.py`), `POR_QUE` (`relevancia.py`), and a query in `sql_oracle.py`. Tests assert that these stay in sync.

**Cross-cutting rules**:
- `alerts.py`: `REGRAS` holds the Aceitável/Alerta/Crítico thresholds. `classificar()` returns a `chave` that `relevancia.ACOES_ALERTA` maps to recommended actions. The municipal hospitalization rate (`taxa`) is compared with the **median** of municipalities with 5k+ inhabitants, not the state mean.
- `sql_oracle.py` produces the Oracle-dialect query shown under each dashboard. Filter values enter only as validated literals. The user's free text appears only as a one-line comment. Tests parse every query with sqlglot's Oracle dialect.
- `db.py` opens SQLite read-only. `db.*` lookups and `alerts.referencias()` are `lru_cache`d, so restart the server after rebuilding the DB. On Windows, an orphaned `uvicorn --reload` worker keeps `sqladies.db` locked.

**Front-end** (`static/js/app.js`, one IIFE, no framework; Plotly is vendored in `static/vendor/plotly.min.js`):
- The "Início" tab cannot be closed. Each question opens a tab.
- A tab is a conversation of `turnos`: a question bubble followed by its dashboard, then a follow-up question box at the end. A sticky "Perguntas: 1 · 2 · 3" nav jumps between turns.
- Changing a filter rebuilds only that turn's dashboard in place.
- Tabs and turns (with their params) persist in `localStorage` under `sqladies_abas`.
- The backend sends chart specs as theme-neutral Plotly traces with `colorSlot`, `colorRole` and `scale`. `styleTrace` and `styleLayout` resolve them from the CSS tokens at draw time, so charts redraw when the theme changes.
- Charts are drawn lazily per tab.

**Maps**:
- Builders emit `choropleth` traces with `geojson: "sp"`. The front-end swaps in `static/vendor/sp_municipios.geojson`, generated by `etl/build_mapa.py`.
- The feature `id` is the 6-digit `cod_mun`. Rings must be clockwise (d3-geo convention). Otherwise every municipality renders as "the world minus the municipality".
- Plotly's base topojson is served from `static/vendor/topojson/` through the `topojsonURL` config. Without it, Plotly fetches from cdn.plot.ly.

**CSS**:
- Colors are tokens on `:root`, with dark-mode overrides.
- Use prefixed class names (`tab-home`, `n-alerta`, `relev-*`, `aba-*`, `turno-*`). Generic names such as `.home` and `.alerta` already collided with existing components.
- `body` uses `min-height` rather than a fixed `height`, so the sticky tab bar stays visible on long pages.
- Printing uses `body.modo-impressao` together with `.turno.imprimir`.

## Testing notes

`tests/test_app.py` runs the API, the matcher, all builders with and without filters, the alert thresholds, filter validation, the Oracle SQL and the map geojson against the real `data/sqladies.db`. It has no fixtures or mocks.

For UI changes, the project has been checked with Playwright using the installed Chrome (`channel="chrome"`) with external requests blocked. Check light theme, dark theme and 390px width, and confirm there is no horizontal scroll.
