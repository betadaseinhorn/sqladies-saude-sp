# DataCare_ · Dashboards de internações SUS por pergunta (SP)

> **Sobre este repositório.** Este projeto é uma **adaptação do trabalho SQLadies entregue à Oracle** e serve como
> **meio demonstrativo da aplicação entregue**. Ele reproduz a mesma proposta (perguntas em linguagem natural que geram
> dashboards a partir do SIH/SUS e do CNES) numa versão leve, que roda localmente e offline. O modelo relacional e as
> queries são apresentados no dialeto **Oracle SQL** (`sql/oracle_schema.sql` e o bloco "Query SQL" de cada dashboard).
> Por baixo, a demonstração usa SQLite.

**DataCare_** ("Transformando dados em cuidado e decisão") é a solução do grupo **SQLadies** no Challenge Oracle + FIAP.
A identidade visual (violeta `#7E3EE0`, roxo profundo `#230E50`, lilás e creme) vem da capa do grupo. Os gráficos usam só
as cores da marca (violeta, laranja e lilás), validadas para daltonismo nos temas claro e escuro (`static/css/base.css`).
O logo é o texto "DataCare_"; o favicon e a capa ficam em `static/marca/`.

Página web com uma aba **Início** (caixa de pergunta no topo): o usuário escolhe ou digita uma pergunta e uma
**nova aba** é aberta com o dashboard gerado na hora: KPIs, **alertas (Aceitável / Alerta / Crítico)**, gráficos
interativos, principais achados, tabela e a **query em Oracle SQL** que produz os dados.
Os dados são as internações SUS dos **645 municípios do estado de São Paulo (2024–2025)**, cruzadas com o cadastro de hospitais, leitos e UBS.
O MVP funciona **100% offline**: sem LLM e sem internet depois que o banco é montado.

## Fontes

| Fonte | Formato | Conteúdo | Tabela no banco |
|---|---|---|---|
| **SIH/SUS (RD-SP)**, FTP DATASUS | estruturado (.dbc → relacional) | 5,7 milhões de internações: valores pagos, permanência, CID, município de residência e de internação | `fato_internacao`, `agg_mensal_hosp`, `agg_mensal_res` |
| **CNES**, API de Dados Abertos do Ministério da Saúde | **JSON** semiestruturado | 8.600 hospitais, UBS e unidades de urgência: tipologia, contatos e atributos variáveis | `dim_estabelecimento` (`atributos_json`), `cnes_raw` |
| **CNES-LT**, FTP DATASUS | estruturado | leitos existentes e SUS por estabelecimento e mês | `fato_leitos` |
| **IBGE (SIDRA)** + base territorial DATASUS | JSON / CSV | população; DRS, Regiões de Saúde, RRAS | `dim_municipio` |

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

python pipeline.py                # 1ª vez: baixa cerca de 550 MB e monta data/sqladies.db (10–20 min)
uvicorn app.main:app              # landing em http://localhost:8000 · aplicação em /app
```

Depois do pipeline, o app não usa a internet: o Plotly e as fontes (Geist) estão em `static/vendor/`.

Desempenho: como o banco é somente leitura, cada dashboard (pergunta + filtros) fica em cache. Ao subir, o servidor
pré-monta em segundo plano as 21 perguntas do catálogo. As respostas e os arquivos estáticos saem compactados (gzip).
Depois de refazer o banco com o `pipeline.py`, reinicie o servidor.

## Rodar em outro PC

O banco `data/sqladies.db` (1,2 GB) não fica no git. Há três formas de tê-lo num PC novo:

1. **Baixar o banco pronto do GitHub Release** (recomendado, cerca de 290 MB e menos de 1 minuto):
   ```bash
   git clone https://github.com/betadaseinhorn/sqladies-saude-sp.git
   cd sqladies-saude-sp
   python setup_demo.py              # baixa o Release v1.0-dados, confere o SHA-256 e extrai
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app
   ```
   Se você já tem o `sqladies.db.zip`, use `python setup_demo.py --zip caminho\sqladies.db.zip`.
2. **Kit de pendrive (offline)**: pasta com o projeto, o banco, os pacotes Python (3.12–3.14) e o instalador do
   Python. No PC novo: `1-instalar.bat` e depois `2-iniciar.bat`. Não precisa de internet.
3. **Recriar do zero** a partir do DATASUS/IBGE: `python pipeline.py` (10–20 min, cerca de 550 MB de download).

Testes: `pytest -q`. Notebook de exploração: [analysis/eda.ipynb](analysis/eda.ipynb).

## Estrutura

```
etl/        download_sih.py, download_cnes.py  → data/raw/
            dbc.py            leitor de .dbc em Python puro (descompressor "blast"; sem compilador C)
            build_ref.py      municípios + DRS/Regiões de Saúde/RRAS + população; capítulos CID-10
            transform_*.py    limpeza → Parquet (data/processed/)
            build_db.py       SQLite: dimensões, fatos, agregados, índices
            build_mapa.py     malha dos municípios de SP (IBGE) para os mapas
analysis/   seasonality.py    índice sazonal + STL por estado, DRS, região de saúde e causa
            ranking.py        indicadores por município (residência e ocorrência) e por hospital
            capacity.py       ocupação estimada mensal por DRS
            clustering.py     K-means + PCA de municípios; Spearman e regressão WLS dos fatores de demanda
            eda.ipynb         exploração que originou o catálogo de perguntas
app/        main.py           FastAPI (/api/questions, /api/ask, /api/filters)
            questions.py      catálogo de 21 perguntas em 6 categorias
            matcher.py        casa texto livre → pergunta (fuzzy + palavras-chave) e extrai filtros
            dashboards.py     um construtor de dashboard por pergunta
            alerts.py         regras de alerta (Aceitável / Alerta / Crítico), limites configuráveis
            relevancia.py     por que cada pergunta importa e ações sugeridas conforme os alertas
            sql_oracle.py     query Oracle equivalente de cada dashboard, com os filtros da pergunta
sql/        oracle_schema.sql DDL Oracle do modelo relacional (partições, JSON, materialized views)
static/     landing.html (/) + css/landing.css + js/landing.js · app.html (/app) + css/app.css + js/app.js
            css/base.css (tokens, fontes Geist, marca) · vendor/ (plotly, fontes, malha de SP, topojson) · marca/ (ícone, capa, capturas)
```

## Landing page

`/` apresenta o DataCare_ para quem chega ao projeto:
- problema, como funciona, recursos, dados e ética, resultados relatados pela equipe;
- uma caixa de pergunta que abre o dashboard direto em `/app#pergunta=…`;
- números reais do banco (`/api/resumo`).

O conteúdo vem dos slides da banca. O que é do produto entregue à Oracle (Select AI, APEX, Power BI, OES) fica separado do que esta demonstração faz.

O contexto do produto para o design está em `PRODUCT.md`. A tipografia é a Geist (licença OFL), servida localmente.

## Interface: aba Início e abas de dashboard

- **Perguntas simples**: a 1ª coluna do catálogo traz 3 perguntas de um resultado só, para começar a demonstração:
  "Baixe a lista de internações por município" (tabela aberta, com o **Baixar CSV** em destaque), "Gráfico das
  internações mês a mês" (um gráfico) e "Mapa das internações por município" (um mapa). Têm filtros e a query
  Oracle, mas não têm alertas nem análise; as sugestões no fim levam às 18 análises completas.
- **Início**: aba fixa (não pode ser fechada) com a caixa de pergunta no topo, o catálogo de perguntas por categoria e,
  embaixo, "Continuar de onde parou" e "Sobre os dados".
- **Abas de dashboard**: cada pergunta abre uma aba (no estilo de pasta) com o texto digitado como título. O ícone da
  aba (✓ ! ✕) indica a pior situação dos alertas daquele dashboard. As abas podem ser fechadas (×, clique do meio ou
  tecla Delete), trocadas pelas setas do teclado e são reabertas ao recarregar a página. O menu ˅ no fim da barra
  lista todas as abas abertas, com a situação e o número de perguntas de cada uma.
- **Conversa na aba**: cada pergunta aparece num balão, seguido do dashboard que responde a ela. No fim da aba
  há uma caixa para fazer outra pergunta, com 2–3 sugestões de continuação (`SEGUINTES` em `app/questions.py`); o
  novo balão e o novo dashboard aparecem logo abaixo. A partir da 2ª pergunta, uma faixa fixa "Perguntas: 1 · 2 · 3"
  leva de volta a cada uma. O ícone da aba mostra a pior situação entre os dashboards dela.
- **Filtros editáveis**: cada dashboard tem uma barra com os filtros que ele usa (ano, DRS, causa, caráter,
  município, top N; lista em `FILTROS`, `app/questions.py`). Mudar um filtro refaz só aquele dashboard, no mesmo lugar,
  e a query Oracle acompanha. Os valores são validados por lista branca (`validar_params`, `app/matcher.py`).
- **Exportar**: "Baixar CSV" em cada tabela (separador `;`, vírgula decimal e BOM, para abrir direto no Excel) e
  "Imprimir / PDF" em cada dashboard: imprime só aquela pergunta, em tema claro, com as tabelas abertas e a query
  completa ("Salvar como PDF" na janela de impressão).
- **Mapa dos municípios**: mapas de SP em ranking de municípios (taxa), polos (% de pacientes de fora + bolhas),
  internações por leito, UBS por habitante e grupos (K-means). A malha do IBGE fica em
  `static/vendor/sp_municipios.geojson` (gerada por `etl/build_mapa.py`) e o mapa-base do Plotly em
  `static/vendor/topojson/`, então os mapas funcionam offline. Com filtro de DRS, o mapa mostra só a região.
- **Menu de abas fixo**: a barra de abas fica sempre visível no topo, mesmo no fim de abas longas.
- **Leitura e movimento**: cada dashboard fica numa coluna de vidro fosco sobre o degradê da marca; as entradas
  (dashboard novo, menu, filtros, tabela, "Copiar") têm animações curtas, que viram só um esmaecer com
  "reduzir movimento" ativado no sistema. Se a pergunta não for reconhecida, a aba mostra perguntas parecidas.
- **Conteúdo da aba**: cabeçalho e KPIs → **Situação** (alertas) → achados → **Por que essa pergunta importa** → gráficos → tabela → **Query SQL (Oracle)**.

### Por que essa pergunta importa

Cada dashboard explica por que a pergunta é relevante para a gestão do SUS-SP e sugere o que poderia ser feito:

- **O que tem de importante nesta pergunta**: o motivo da pergunta (planejamento, custo, risco ao paciente).
- **Problemas identificados**: os indicadores do dashboard em Alerta ou Crítico, com os filtros aplicados.
- **O que poderia ser feito**: primeiro as ações ligadas aos indicadores críticos, depois às de alerta e por fim
  ações gerais do tema (ex.: NIR e gestão de leitos, PPI, vacinação antes do pico, atenção primária).

Os textos ficam em `app/relevancia.py` (`POR_QUE` por pergunta e `ACOES_ALERTA` por regra de alerta). São sugestões
de gestão a partir de indicadores agregados, não substituem a análise local.

## Como a pergunta é entendida

1. Um clique numa sugestão **preenche a caixa de texto**; o usuário pode editar antes de enviar.
2. Se o texto foi digitado ou editado, o `matcher` normaliza o texto e procura nele:
   - **município**, como em "compare Santos e Guarujá";
   - **DRS**, como em "DRS VII" ou "DRS de Bauru";
   - **ano** (2024 ou 2025);
   - **causa (CID)**, como "respiratórias", "dengue" ou "parto";
   - **top N** e **caráter** (eletivo ou urgência).
3. Depois pontua cada pergunta do catálogo por similaridade (RapidFuzz) e palavras-chave. Se nenhuma passa do limiar,
   a aba Início sugere as 3 mais próximas, sem abrir aba.

Exemplos: *"hospitais de Campinas em 2025"*, *"sazonalidade da dengue entre as DRS"*,
*"top 10 municípios com mais internações por habitante na DRS de Bauru"*, *"mostre o panorama de internações de Santos"*.

## Sistema de alertas

Cada dashboard classifica seus indicadores em **✓ Aceitável**, **! Alerta** ou **✕ Crítico** (ícone + rótulo, nunca só cor).
As regras ficam em `app/alerts.py` (dicionário `REGRAS`) e podem ser ajustadas sem mexer nos dashboards.

| Indicador | Aceitável | Alerta | Crítico | Referência |
|---|---|---|---|---|
| Ocupação estimada de leitos SUS | ≤ 75% | 75–85% | > 85% | limite usual de ocupação alta |
| Taxa de internação por 1.000 hab. | ≤ 1,1× | 1,1–1,3× | > 1,3× | mediana dos municípios com 5 mil+ hab. |
| Permanência média | ≤ 1,2× | 1,2–1,5× | > 1,5× | média do estado |
| Mortalidade hospitalar | ≤ 1,1× | 1,1–1,3× | > 1,3× | média do estado |
| Internações por leito SUS/ano | ≤ 1,3× | 1,3–1,6× | > 1,6× | média do estado |
| Residentes internados fora do município | ≤ 30% | 30–60% | > 60% | dependência regional |
| Pico sazonal | ≤ +10% | +10% a +25% | > +25% | média mensal do ano |
| Leitos SUS por 10 mil hab. | ≥ 15 | 10–15 | < 10 | cobertura |
| % de hospitais / municípios em situação crítica | ≤ 10% | 10–25% / 10–20% | acima | parcela do total |

A taxa de internação é comparada à **mediana dos municípios**, e não à média ponderada do estado: a capital puxa a
média para baixo e marcaria como críticos municípios apenas medianos.

## Query SQL em Oracle

No fim de cada dashboard há o bloco **Query SQL (Oracle)**, com uma aba por consulta e botão **Copiar**.

- As queries usam o mesmo modelo relacional da demonstração (DDL em `sql/oracle_schema.sql`) e já trazem os filtros
  da pergunta: ano, DRS, causa, caráter e municípios.
- Recursos do dialeto Oracle usados:
  - `FETCH FIRST n ROWS ONLY`;
  - funções analíticas: `AVG() OVER (PARTITION BY …)`, `RATIO_TO_REPORT`, `NTILE`;
  - `MEDIAN` e `CORR_S` (correlação de Spearman nativa);
  - `JSON_VALUE` sobre o cadastro CNES semiestruturado.
- Os valores dos filtros entram como literais validados (inteiros e códigos do catálogo). Texto livre do usuário nunca
  entra no SQL, só como comentário de uma linha.
- Partes estatísticas (STL, K-means, regressão) são executadas em Python. A query mostra a extração dos dados.
- **Validação**: as queries das 21 perguntas (com e sem filtros) passam no parser Oracle do `sqlglot`. Também foram
  traduzidas para SQLite e executadas contra o banco da demonstração, devolvendo dados.

## Catálogo de perguntas

| Objetivo | Perguntas |
|---|---|
| Visão geral | panorama do estado; causas que mais custam |
| **Sazonalidade** (período e região) | variação mensal + STL; meses de pico por DRS; causas mais sazonais; sazonalidade de uma causa entre as DRS |
| **Rankings e comparações** | municípios por internações/hab.; hospitais por volume; hospitais por permanência; comparar municípios; panorama de um município; polos que recebem pacientes |
| **Capacidade** | internações por leito SUS; ocupação estimada dos hospitais; estrutura por DRS |
| **Padrões e fatores** | UBS × internações; grupos de municípios (K-means); fatores associados à demanda (regressão) |

## Principais achados (2024–2025)

- **Doenças respiratórias** são a causa mais sazonal: pico em maio (+29% sobre a média do ano) e vale em janeiro (−31%). Em todas as DRS o pico fica entre maio e junho; DRS VIII (Franca) tem o pico mais intenso.
- **Infecciosas** sobem de março a maio, compatível com a dengue. Cirurgias eletivas caem de dezembro a fevereiro.
- **Cerca de 30% das internações** acontecem fora do município de residência. São Paulo, São José do Rio Preto, Ribeirão Preto e Campinas são os maiores polos.
- **K-means** formou 3 perfis de municípios:
  - sedes regionais com muitos leitos e alta taxa de internação;
  - municípios pequenos que internam quase tudo fora;
  - grandes centros, com taxa menor e população mais jovem.
- **Regressão** (R² = 0,48; 496 municípios com 5.000+ hab.): leitos SUS/hab., UBS/hab. e % de idosos estão associados a **taxas de internação maiores**. A relação é associativa, não causal. Uma hipótese é que haja demanda reprimida onde há pouca estrutura.

## Limitações

- A **ocupação estimada** = dias de permanência ÷ (leitos SUS × dias) é uma aproximação. A permanência é contada no mês da internação, e o leito SUS cadastrado pode não refletir o uso real.
- **Período**: considera a data de internação entre jan/2024 e dez/2025. Foram incluídas as competências de jan–mar/2026 para captar AIHs apresentadas com atraso.
- **Contagem de internações**: AIHs de longa permanência (IDENT = 5) somam valores, mas não contam como nova internação.
- **Hospitais sem cadastro**: 16 dos 648 hospitais do SIH não estão no cadastro da API do CNES e aparecem como `CNES <código>`.
