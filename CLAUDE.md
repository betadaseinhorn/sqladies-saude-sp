# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DataCare_ (the product of the group SQLadies, Challenge Oracle + FIAP): a FastAPI + vanilla JS app that turns a question in Portuguese into a dashboard about SUS hospitalizations in the 645 municipalities of São Paulo state, 2024–2025.
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
- `db.py` opens SQLite read-only. `db.*` lookups, `alerts.referencias()` and `dashboards._montar` (the dashboard for a question and its params, everything except `sql`) are `lru_cache`d, so restart the server after rebuilding the DB. Callers must not mutate what `_montar` returns: `build()` returns a shallow copy with a fresh `sql`. At startup, `main.lifespan` warms the cache for the 18 catalog questions in a background thread. On Windows, an orphaned `uvicorn --reload` worker keeps `sqladies.db` locked.
- `main.py` enables gzip for every response. Files under `/static/vendor/` are sent with `Cache-Control: max-age=86400`; `app.js` and the CSS files are not cached.
- `matcher._mun_regex()` is a single compiled alternation over the 645 municipality names, longest first. Do not loop over per-name regexes: that overflows `re`'s cache and costs about 16 ms per question.

**Pages**:
- `/` serves the landing page, `static/landing.html` with `css/landing.css` and `js/landing.js`. It does not load Plotly.
- The landing's question box and its examples link to `/app#pergunta=…`.
- Old `/#pergunta=…` links are redirected by an inline script in the landing.
- `/api/resumo` returns the real figures the landing shows.
- The landing's screenshots live in `static/marca/` (`app-*.webp`, `mapa-*.webp`). They are captured from the running app; recapture them when the app's look changes.
- `PRODUCT.md` (Impeccable) records product truth and brand commitments. The landing follows the "category standard at Vercel's craft level" direction.
- `/app` serves `static/app.html`.
- `static/css/base.css` holds what both pages share: color tokens, Geist fonts (local, OFL), the brand, and global browser surfaces.
- `static/css/app.css` holds the application's own styles.

**Front-end** (`static/js/app.js`, one IIFE, no framework; Plotly is vendored in `static/vendor/plotly.min.js`):
- The "Início" tab cannot be closed. Each question opens a tab.
- The tab bar uses folder tabs, from the user's reference image (see DESIGN.md). The active tab is `--page` colored with radial-gradient flares in `::before` and `::after`, so do not reuse those pseudo-elements on `.tab`. The chevron menu (`abrirMenuAbas()` and `fecharMenuAbas()`) lists open tabs from `abas`, using `a.estado` saved by `setStatus()`. It supports ↑ ↓ Home End Enter Esc and closes on an outside click. It is hidden while no question tab is open (`salvar()`). `bordasAbas()` toggles `.mais-esq` and `.mais-dir` on `#tabs` to fade the edges when tabs overflow. Call it after adding, closing or activating a tab.
- A tab is a conversation of `turnos`: a question bubble followed by its dashboard, then a follow-up question box at the end. A sticky "Perguntas: 1 · 2 · 3" nav jumps between turns.
- Changing a filter rebuilds only that turn's dashboard in place.
- Tabs and turns (with their params) persist in `localStorage` under `sqladies_abas`.
- Each tab has its own URL, `#pergunta=<question text>`. `ativar()` pushes it to the browser history, so Back and Forward switch tabs (`popstate`). On load, a `#pergunta=` link opens or reactivates that question's tab.
- `html` has `scroll-padding-top` set to the height of the sticky tab bar plus the "Perguntas" strip, so focused or scrolled-to items are not hidden. Inside those horizontal strips, use `rolarParaVer()` and never `scrollIntoView`: with the padding, `scrollIntoView` also scrolls the page and cancels the smooth scroll already in progress.
- The backend sends chart specs as theme-neutral Plotly traces with `colorSlot`, `colorRole` and `scale`. `styleTrace` and `styleLayout` resolve them from the CSS tokens at draw time, so charts redraw when the theme changes.
- Charts are drawn lazily per tab.
- Chart cards sit in flex rows that never leave a hole: each card grows to fill its row, and `--cols` (2, or 3 at ≥1500px) is balanced by the number of normal cards (`data-n`). `wide` cards take a full row. Plot text is at least 12px.
- A dashboard with a map uses pairs (`data-mapa`): `ordenarGraficos()` puts the map next to the first chart, at the same height. `caixaGeo()` crops the map to the bounds of the municipalities drawn instead of using `fitbounds`, which left a large empty frame.
- "O que os dados mostram" and "Por que essa pergunta importa" are stacked, each using the full width. Side by side, the shorter one left a gap.
- "O que os dados mostram" is one divided panel, like the "why" panel, with one numbered cell per finding (01, 02…) that grows to fill its row. `destacarNumeros()` bolds the figures in each sentence. It leaves years, dates (mai/25), denominators ("por 1.000") and names ("Grupo 1") as plain text.

**Maps**:
- Builders emit `choropleth` traces with `geojson: "sp"`. The front-end swaps in `static/vendor/sp_municipios.geojson`, generated by `etl/build_mapa.py`.
- The feature `id` is the 6-digit `cod_mun`. Rings must be clockwise (d3-geo convention). Otherwise every municipality renders as "the world minus the municipality".
- Plotly's base topojson is served from `static/vendor/topojson/` through the `topojsonURL` config. Without it, Plotly fetches from cdn.plot.ly.

**CSS**:
- Colors are tokens on `:root`, with dark-mode overrides. Brand: violet `#7E3EE0`, deep purple `#230E50`, lilac and cream, taken from the group's cover. Charts use only brand colors: `--s1` violet, `--s2` orange, `--s3` lilac (#9e7fd8 light, #c4a6f7 dark); no chart has more than 3 series. Checked with the dataviz skill's `validate_palette.js` (`--pairs all`). In dark mode the lilac sits slightly above the lightness band, so the 3rd series also differs in shape: dashed line, diamond marker. Do not add other hues. Bar hatching (`marker.pattern`) is off: Plotly does not draw it together with `barcornerradius`. SQL highlighting keeps its own colors (green strings, raspberry functions); the user asked to leave them.
  Horizontal bars that label every value hide the x axis and its grid. Status colors never change.
- `static/marca/` holds `favicon.svg` (the brain-circuit icon, now only the favicon; the logo is the "DataCare_" wordmark alone) and `capa-topo.webp` (the cover cropped above the members' names). The original `capa.png` has names and student IDs, so it is gitignored; never commit it.
- Use prefixed class names (`tab-home`, `n-alerta`, `relev-*`, `aba-*`, `turno-*`). Generic names such as `.home` and `.alerta` already collided with existing components.
- `body` uses `min-height` rather than a fixed `height`, so the sticky tab bar stays visible on long pages.
- Printing uses `body.modo-impressao` together with `.turno.imprimir`.
- The front was refined with the Impeccable skill (`polish`, Operate mode) and reviewed with `better-interface`. Its detector only reports advisories and known false positives (Geist, `.janela-barra`, Plotly); do not add new kinds of finding. Run it with `~/.claude/skills/impeccable/scripts/impeccable detect --json static/ http://localhost:8000/`.
  - Do not use colored side borders on cards.
  - Status icons are SVG (`ICONE_NIVEL`), never ✓/!/✕ characters, including on the tabs (`.tab-sico`); never show status as a bare color dot.
  - A tab that fails to load shows `erroComSaida()`: what happened, what to do, the matcher's suggestions and a way back. Errors always name a next step.
  - KPIs, alerts and the "Por que essa pergunta importa" section are single panels with dividers, not one card per item.
  - Shape tokens: `--r-*`, `--fs-*` (including `--fs-base` 15px), `--dur`, `--ease`. Use them instead of literal sizes and radii.
  - Layout tokens: `--gutter` (fluid margin), `--wide` (1600px content limit) and `--measure` (68ch).
  - Pages use the width of the screen; avoid fixed narrow centered columns. On the landing, blocks are padded with `--pad-x`.
  - The app's Início, top to bottom: the question block centered at the top, the catalog in category columns, then "Continuar de onde parou" + "Sobre os dados" side by side, and a centered footer.
  - Only the Início question box and "Fazer outra pergunta" stay centered, as the user asked.
  - Loading is a skeleton (`.esqueleto`), not a spinner.
  - Motion follows Emil Kowalski's skills (`find-animation-opportunities`, `animate`, `review-animations`).
    - Token: `--ease-out` (cubic-bezier(0.23, 1, 0.32, 1)) for entering and leaving. If something has to move across the screen, add `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`.
    - Animate only `transform` and `opacity`, plus height on `details.tbl` and `display` with `allow-discrete` on the menu.
    - Never animate frequent actions: switching tabs, arrow keys, hover. Data (KPIs, Plotly charts) is never animated for style.
    - Entrance classes are temporary (`marcarEntrada()`), so animations do not replay when a hidden tab is shown again.
    - Reduced motion keeps the fades and removes movement. Do not go back to a global `animation: none !important`.
    - The landing reveals blocks once with an IntersectionObserver, only when JS adds `.revelar-js`.
    - Dashboards sit in a glass reading column (`.turno`, `.aba-pergunta`, `.esqueleto`, `.erro-box`) built from the `--vidro*` tokens, so text never sits straight on the glow. Keep the cards inside solid.
    - The brand glow is a fixed `body::before` on both pages. The landing meshes (`canvas[data-malha]`, `malha()` in landing.js) are decorative, use at most 150 points, and pause offscreen. Keep them out of the app's dashboards: data there must not compete with motion.

## Testing notes

`tests/test_app.py` runs the API, the matcher, all builders with and without filters, the alert thresholds, filter validation, the Oracle SQL and the map geojson against the real `data/sqladies.db`. It has no fixtures or mocks.

For UI changes, the project has been checked with Playwright using the installed Chrome (`channel="chrome"`) with external requests blocked. Check light theme, dark theme and 390px width, and confirm there is no horizontal scroll.
