/* DataCare_ (grupo SQLadies) — adaptação demonstrativa da aplicação entregue à Oracle.
   Aba "Início" fixa com a caixa de pergunta centralizada; cada pergunta abre uma aba
   com o dashboard (alertas + gráficos + tabela + query Oracle). Sem dependências além do Plotly local. */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const input = $("#pergunta");
  const form = $("#composer");
  const sendBtn = $("#send");
  const tabsEl = $("#tabs");
  const panelsEl = $("#panels");
  const feedback = $("#feedback");
  const STORE = "sqladies_abas";
  const NIVEL = {
    aceitavel: { rotulo: "Aceitável" },
    alerta: { rotulo: "Alerta" },
    critico: { rotulo: "Crítico" },
  };
  const ORDEM_NIVEL = { aceitavel: 0, alerta: 1, critico: 2 };
  const ICONE_NIVEL = {
    aceitavel: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    alerta: '<path d="M12 6v7"/><path d="M12 17.5v.5"/>',
    critico: '<path d="M7 7l10 10M17 7L7 17"/>',
  };

  // id -> {id, text, qid, tab, panel, lista, nav, caixa, drawn, turnos[{text, qid, params, el, dash, charts[], nivel}]}
  const abas = new Map();
  let ativa = "inicio";
  let seq = 0;
  let pendingId = null; // id da pergunta escolhida num chip (enquanto o texto não for editado)
  let pendingText = "";
  let FILT = null; // opções dos filtros (/api/filters), carregadas no init
  let GEO = null; // malha dos municípios de SP (static/vendor/sp_municipios.geojson), carregada no init

  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf3 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v);
    }
    for (const k of kids.flat()) if (k != null) n.append(k);
    return n;
  }
  function svgIcon(path) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("class", "ico");
    s.innerHTML = path;
    return s;
  }

  // ---------------------------------------------------------------- tema ---
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  function theme() {
    return {
      series: [1, 2, 3].map((i) => css(`--s${i}`)),
      text: css("--text"), text2: css("--text-2"), muted: css("--muted"),
      grid: css("--grid"), axis: css("--axis"), surface: css("--surface"), surface2: css("--surface-2"),
      neg: css("--div-neg"), mid: css("--div-mid"), pos: css("--div-pos"),
      seq0: css("--seq-0"), seq1: css("--seq-1"), border: css("--border"),
    };
  }
  function alpha(hex, a) {
    const h = hex.replace("#", "");
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
    return `rgba(${r},${g},${b},${a})`;
  }

  function styleTrace(tr, T) {
    const t = structuredClone(tr);
    const slot = Math.min(t.colorSlot ?? 0, T.series.length - 1);
    const color = t.colorRole === "muted" ? T.muted : T.series[slot];
    const isMuted = t.colorRole === "muted";
    // a cor nunca é o único sinal: em linhas e pontos, cada série também tem forma própria (marcador e traço);
    // nas barras agrupadas, a ordem fixa e a legenda identificam a série
    const SIMBOLO = ["circle", "square", "diamond"], TRACO = ["solid", "solid", "dash"];
    if (t.type === "bar") {
      t.marker = Object.assign({}, t.marker);
      if (t.colorByValue === "diverging") {
        const vals = t.orientation === "h" ? t.x : t.y;
        t.marker.color = vals.map((v) => (v >= 0 ? T.pos : T.neg));
      } else t.marker.color = color;
      t.marker.line = { width: 0 };
      t.textfont = { color: T.text2, size: 12 };
      if (t.error_x) t.error_x = Object.assign({ color: T.text2, thickness: 1.5, width: 4 }, t.error_x);
    } else if (t.type === "choropleth") {
      // mapa dos municípios: a malha vem do arquivo local; bordas na cor da superfície
      t.geojson = GEO;
      if (t.scale === "base") t.colorscale = [[0, T.surface2], [1, T.surface2]];
      else if (t.scale === "categorical") {
        const n = t.categorias.length;
        const cor = (i) => T.series[Math.min(i, T.series.length - 1)];
        t.colorscale = t.categorias.flatMap((_, i) => [[i / n, cor(i)], [(i + 1) / n, cor(i)]]);
        t.colorbar = Object.assign({}, t.colorbar, { tickvals: t.categorias.map((_, i) => i), ticktext: t.categorias });
      } else t.colorscale = [[0, T.seq0], [1, T.seq1]];
      t.marker = { line: { color: T.surface, width: 0.4 } };
      if (t.showscale !== false) {
        t.colorbar = Object.assign({ outlinewidth: 0, tickfont: { color: T.text2, size: 12 } }, t.colorbar);
        if (t.colorbar.title) t.colorbar.title.font = { color: T.text2, size: 12 };
      }
      delete t.categorias;
    } else if (t.type === "scattergeo") {
      t.marker = Object.assign({}, t.marker, { color: color, line: { color: T.surface, width: 1 } });
    } else if (t.type === "scatter") {
      const lines = (t.mode || "").includes("lines");
      const markers = (t.mode || "").includes("markers");
      if (lines) t.line = Object.assign({ width: 2, dash: isMuted ? "solid" : TRACO[slot] }, t.line, { color });
      if (markers) {
        const m = t.marker || {};
        t.marker = Object.assign({ size: lines ? 7 : 8, symbol: isMuted ? "circle" : SIMBOLO[slot] }, m, {
          color: isMuted ? alpha(T.muted, 0.45) : color,
          line: { color: T.surface, width: lines ? 2 : 1 },
        });
        if (!lines && !isMuted && m.opacity == null) t.marker.opacity = 0.85;
      }
      if (t.fill) t.fillcolor = alpha(color, 0.1);
      if ((t.mode || "").includes("text")) t.textfont = { color: T.text2, size: 12 };
    } else if (t.type === "heatmap") {
      t.colorscale = t.scale === "sequential"
        ? [[0, T.seq0], [1, T.seq1]]
        : [[0, T.neg], [0.5, T.mid], [1, T.pos]];
      if (t.scale !== "sequential" && t.zmid === 0) {
        const flat = t.z.flat().filter((v) => v != null);
        const m = Math.max(...flat.map(Math.abs));
        t.zmin = -m; t.zmax = m;
      }
      t.colorbar = Object.assign({ outlinewidth: 0, tickfont: { color: T.text2, size: 12 } }, t.colorbar);
      t.hoverongaps = false;
    }
    delete t.colorSlot; delete t.colorRole; delete t.colorByValue; delete t.scale;
    return t;
  }

  function styleLayout(lay, traces, T, height) {
    const axis = (a = {}) => Object.assign({
      gridcolor: T.grid, linecolor: T.axis, zerolinecolor: T.axis, tickfont: { color: T.muted, size: 12 },
      automargin: true, exponentformat: "none", separatethousands: true,
    }, a, { title: Object.assign({ font: { color: T.text2, size: 12 } }, a.title || {}) });
    const multi = traces.filter((t) => t.name && t.showlegend !== false).length >= 2;
    const L = Object.assign({}, lay, {
      height, autosize: true,
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: css("--font") || "system-ui", color: T.text2, size: 12 },
      separators: ",.",
      margin: Object.assign({ l: 8, r: 16, t: multi ? 36 : 14, b: 8 }, lay.margin),
      xaxis: axis(lay.xaxis), yaxis: axis(lay.yaxis),
      hoverlabel: { bgcolor: T.surface, bordercolor: T.border, font: { color: T.text, family: "system-ui", size: 12.5 } },
      showlegend: lay.showlegend ?? multi,
      legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { color: T.text2, size: 12 } },
      bargap: lay.bargap ?? 0.35, bargroupgap: 0.12, barcornerradius: 4,
      hovermode: "closest",
    });
    // barras horizontais com rótulo externo: reserva espaço para o texto não ser cortado
    const hb = traces.filter((t) => t.type === "bar" && t.orientation === "h" && t.textposition === "outside");
    if (hb.length && !(lay.xaxis && lay.xaxis.range)) {
      const xs = hb.flatMap((t) => t.x).filter((v) => v != null);
      const lo = Math.min(0, ...xs), hi = Math.max(0, ...xs);
      const longest = Math.max(...hb.flatMap((t) => t.text || []).map((s) => String(s).length));
      const pad = Math.min(0.6, 0.06 + longest * 0.018);
      L.xaxis.range = [lo < 0 ? lo * (1 + pad) : 0, hi > 0 ? hi * (1 + pad) : 0];
      // cada barra já mostra o valor: o eixo de baixo só repetiria os números (e por extenso, como 2.000.000.000)
      if (hb.every((t) => t.text && t.text.length)) Object.assign(L.xaxis, { showticklabels: false, showgrid: false, title: { text: "" } });
    }
    for (const ax of [L.xaxis, L.yaxis]) if (ax.type === "log" && ax.dtick == null) ax.dtick = 1;
    if (lay.geo) {
      L.geo = Object.assign({ bgcolor: "rgba(0,0,0,0)", projection: { type: "mercator" } }, lay.geo);
      // recorte exato dos municípios desenhados: o mapa ocupa o cartão (fitbounds deixa uma moldura grande e vazia)
      const caixa = caixaGeo(traces);
      if (caixa) {
        delete L.geo.fitbounds;
        L.geo.lonaxis = { range: caixa.lon }; L.geo.lataxis = { range: caixa.lat };
      }
      L.showlegend = false;
    }
    if (lay.xaxis && lay.xaxis.visible === false) L.xaxis.visible = false;
    if (lay.yaxis && lay.yaxis.visible === false) L.yaxis.visible = false;
    L.shapes = (lay.shapes || []).map((s) => {
      const c = Object.assign({}, s);
      if (c.role === "reference") { c.line = { color: T.text2, width: 1, dash: "dot" }; delete c.role; }
      return c;
    });
    return L;
  }

  // limites (lon/lat) dos municípios e pontos de um mapa, com uma folga de 2%
  let caixasMun = null;
  function caixaGeo(traces) {
    if (!GEO) return null;
    if (!caixasMun) {
      caixasMun = new Map();
      for (const f of GEO.features) {
        const c = [Infinity, -Infinity, Infinity, -Infinity];
        const andar = (p) => { if (typeof p[0] === "number") { c[0] = Math.min(c[0], p[0]); c[1] = Math.max(c[1], p[0]); c[2] = Math.min(c[2], p[1]); c[3] = Math.max(c[3], p[1]); } else p.forEach(andar); };
        andar(f.geometry.coordinates);
        caixasMun.set(String(f.id), c);
      }
    }
    const c = [Infinity, -Infinity, Infinity, -Infinity];
    const somar = (x0, x1, y0, y1) => { c[0] = Math.min(c[0], x0); c[1] = Math.max(c[1], x1); c[2] = Math.min(c[2], y0); c[3] = Math.max(c[3], y1); };
    for (const t of traces) {
      if (t.type === "choropleth") for (const l of t.locations || []) { const m = caixasMun.get(String(l)); if (m) somar(...m); }
      if (t.type === "scattergeo") (t.lon || []).forEach((x, i) => somar(x, x, t.lat[i], t.lat[i]));
    }
    if (!isFinite(c[0])) return null;
    const px = (c[1] - c[0]) * 0.02 || 0.1, py = (c[3] - c[2]) * 0.02 || 0.1;
    return { lon: [c[0] - px, c[1] + px], lat: [c[2] - py, c[3] + py] };
  }

  // Plotly (4,3 MB) só é carregado quando há gráfico a desenhar: o Início aparece sem esperar por ele
  let plotlyPronto = null;
  function carregarPlotly() {
    if (window.Plotly) return Promise.resolve();
    if (!plotlyPronto) {
      plotlyPronto = new Promise((ok, falha) => {
        const s = el("script", { src: "/static/vendor/plotly.min.js" });
        s.onload = ok;
        s.onerror = () => { plotlyPronto = null; s.remove(); falha(new Error("plotly")); };
        document.head.append(s);
      });
    }
    return plotlyPronto;
  }

  function drawChart(div, spec) {
    if (!window.Plotly) {
      carregarPlotly().then(() => drawChart(div, spec), () => {
        div.replaceChildren(el("p", { class: "card-sub", text: "Não consegui carregar os gráficos. Recarregue a página." }));
      });
      return;
    }
    if (!GEO && spec.traces.some((t) => t.geojson === "sp")) {
      div.replaceChildren(el("p", { class: "card-sub", text: "Não consegui carregar o mapa dos municípios." }));
      return;
    }
    const T = theme();
    const traces = spec.traces.map((t) => styleTrace(t, T));
    const layout = styleLayout(spec.layout || {}, traces, T, spec.height || 340);
    // tela estreita: nomes longos no eixo das barras horizontais são encurtados (o nome completo segue no hover)
    const barrasH = traces.filter((t) => t.type === "bar" && t.orientation === "h");
    if (barrasH.length && div.clientWidth < 520) {
      const nomes = [...new Set(barrasH.flatMap((t) => t.y))];
      layout.yaxis = Object.assign({}, layout.yaxis, { tickmode: "array", tickvals: nomes,
        ticktext: nomes.map((s) => (String(s).length > 18 ? String(s).slice(0, 17) + "…" : s)),
        tickfont: Object.assign({}, layout.yaxis.tickfont, { size: 12 }) });
    }
    // topojsonURL: mapa-base do Plotly servido localmente (static/vendor/topojson), para funcionar offline
    Plotly.react(div, traces, layout, { displayModeBar: false, responsive: true, topojsonURL: "/static/vendor/topojson/" });
  }

  // achados: os números da frase (+5%, 13 pontos, R$ 2,3 bi, 2,8×) em negrito, para leitura rápida; anos e datas (mai/25) ficam normais
  const NUMERO = /((?<![\/\w.,])[+\-−]?(?:R\$\s?)?\d(?:[\d.,]*\d)?(?:\s?(?:%|×|x\b|pontos percentuais|p\.p\.|mil\b|mi\b|bi\b|dias\b))?)/g;
  function destacarNumeros(texto) {
    const partes = texto.split(NUMERO);
    return partes.map((parte, i) => {
      if (i % 2 === 0 || !parte) return parte;
      const antes = partes[i - 1] || "";
      // anos, denominadores ("por 1.000", "por 10 mil") e nomes ("Grupo 1") não são o dado em si
      if (/^(19|20)\d\d$/.test(parte) || /(por|Grupo)\s$/.test(antes)) return parte;
      return el("strong", { text: parte });
    });
  }

  const eMapa = (c) => c.traces.some((t) => t.geojson === "sp");
  // com mapa, os gráficos vão em pares: o mapa fica ao lado do 1º gráfico, com a mesma altura dele,
  // e o gráfico que sobrar ocupa a linha toda (em vez de três colunas estreitas com o mapa pequeno)
  function ordenarGraficos(lista) {
    const normais = lista.filter((c) => !c.wide);
    const mapa = normais.find(eMapa);
    if (!mapa || normais.length < 2) return lista;
    const par = normais.find((c) => c !== mapa);
    const h = Math.max(mapa.height || 340, par.height || 340);
    const resto = lista.filter((c) => c !== mapa).map((c) => (c === par ? { ...c, height: h } : c));
    const i = resto.findIndex((c) => c.title === par.title);
    return [...resto.slice(0, i + 1), { ...mapa, height: h }, ...resto.slice(i + 1)];
  }

  const graficos = (a) => a.turnos.flatMap((t) => t.charts);

  function desenharAba(a) {
    if (!a) return;
    const cs = graficos(a);
    if (a.drawn) { if (window.Plotly) cs.forEach(([div]) => Plotly.Plots.resize(div)); return; }
    cs.forEach(([div, spec]) => drawChart(div, spec));
    a.drawn = true;
  }

  $("#tema-btn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("tema", next); } catch (e) { /* ok */ }
    trocarTema();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", trocarTema);
  function trocarTema() {
    // redesenha a aba visível; as demais são redesenhadas quando forem abertas
    for (const a of abas.values()) a.drawn = false;
    desenharAba(abas.get(ativa));
  }

  // ------------------------------------------------------------- formatos ---
  function fmt(v, f) {
    if (v == null || v === "") return "–";
    if (typeof v !== "number") return String(v);
    switch (f) {
      case "int": return nf0.format(v);
      case "dec1": return nf1.format(v);
      case "dec2": return nf2.format(v);
      case "dec3": return nf3.format(v);
      case "pct": return nf1.format(v) + "%";
      case "brl": return brl.format(v);
      case "auto": return Math.abs(v) >= 100 ? nf0.format(v) : (Number.isInteger(v) ? nf0.format(v) : nf2.format(v));
      default: return String(v);
    }
  }

  function badge(nivel) {
    const n = NIVEL[nivel];
    if (!n) return el("span", { text: "–" });
    // ícone desenhado (mesmo traço dos demais ícones), no lugar dos caracteres ✓ ! ✕
    const sico = el("span", { class: "sico", "aria-hidden": "true" });
    sico.append(svgIcon(ICONE_NIVEL[nivel]));
    return el("span", { class: `status-badge st-${nivel}` }, sico, n.rotulo);
  }

  // -------------------------------------------------------------- exportar ---
  const nomeArquivo = (t) => "sqladies_" + t.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "").toLowerCase().slice(0, 60);

  // CSV para o Excel em português: separador ";", vírgula decimal e BOM UTF-8
  function baixarCsv(spec) {
    const CASAS = { int: 0, dec1: 1, pct: 1, dec2: 2, brl: 2, auto: 2, dec3: 3 };
    const cel = (v, f) => {
      if (v == null) return "";
      if (typeof v === "number") return String(Number(v.toFixed(CASAS[f] ?? 2))).replace(".", ",");
      const s = String(v);
      return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const linhas = [spec.columns.map((c) => cel(c.label)).join(";")];
    for (const r of spec.rows) {
      linhas.push(spec.columns.map((c) => cel(c.fmt === "status" ? (NIVEL[r[c.key]] || {}).rotulo : r[c.key], c.fmt)).join(";"));
    }
    const blob = new Blob(["\ufeff" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = el("a", { href: url, download: nomeArquivo(spec.title) + ".csv" });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // imprime só um turno (pergunta + dashboard); "Salvar como PDF" fica na janela de impressão do navegador
  async function imprimir(t) {
    const tema = document.documentElement.dataset.theme;
    const fechados = [...t.dash.querySelectorAll("details")].filter((d) => !d.open);
    fechados.forEach((d) => { d.open = true; });
    try { await carregarPlotly(); } catch (e) { /* imprime sem gráficos */ }
    document.documentElement.dataset.theme = "light"; // papel: sempre tema claro
    document.body.classList.add("modo-impressao");
    t.el.classList.add("imprimir");
    if (window.Plotly) await Promise.all(t.charts.map(([div, spec]) => {
      drawChart(div, spec);
      return Plotly.relayout(div, { width: 680 });
    }));
    const fim = () => {
      fechados.forEach((d) => { d.open = false; });
      if (tema) document.documentElement.dataset.theme = tema; else delete document.documentElement.dataset.theme;
      document.body.classList.remove("modo-impressao");
      t.el.classList.remove("imprimir");
      t.charts.forEach(([div, spec]) => { drawChart(div, spec); if (window.Plotly) Plotly.Plots.resize(div); });
    };
    window.addEventListener("afterprint", fim, { once: true });
    window.print();
  }

  // -------------------------------------------------------------- tabelas ---
  function buildTable(spec) {
    const csv = el("button", { type: "button", class: "csv-btn", title: "Baixar a tabela em CSV (abre no Excel)",
      onclick: (e) => { e.preventDefault(); e.stopPropagation(); baixarCsv(spec); } },
    svgIcon('<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>'), el("span", { text: "Baixar CSV" }));
    const chev = svgIcon('<path d="M9 6l6 6-6 6"/>');
    chev.classList.add("chev");
    chev.setAttribute("aria-hidden", "true");
    const det = el("details", { class: "tbl" }, el("summary", {}, chev,
      el("span", { class: "tbl-titulo", text: `Ver tabela: ${spec.title} (${spec.rows.length})` }), csv));
    const wrap = el("div", { class: "tbl-wrap" });
    const tbody = el("tbody");
    const isNum = (c) => c.fmt !== "text" && c.fmt !== "status";
    let rows = spec.rows.slice();
    let sortKey = null, dir = 1;
    const valor = (r, c) => (c.fmt === "status" ? ORDEM_NIVEL[r[c.key]] : r[c.key]);

    function fill() {
      tbody.replaceChildren(...rows.map((r) => el("tr", {}, spec.columns.map((c) => {
        if (c.fmt === "status") return el("td", {}, badge(r[c.key]));
        return el("td", { class: isNum(c) && typeof r[c.key] === "number" ? "num" : "", text: fmt(r[c.key], c.fmt) });
      }))));
    }
    const tr = el("tr");
    for (const c of spec.columns) {
      const seta = svgIcon('<path d="M12 19V5M6 11l6-6 6 6"/>');
    seta.classList.add("seta-ord");
    seta.setAttribute("aria-hidden", "true");
      const th = el("th", { class: isNum(c) ? "num" : "", scope: "col", tabindex: "0" }, el("span", { text: c.label }), seta);
      const sort = () => {
        dir = sortKey === c.key ? -dir : (isNum(c) || c.fmt === "status" ? -1 : 1);
        sortKey = c.key;
        rows.sort((a, b) => {
          const x = valor(a, c), y = valor(b, c);
          if (x == null) return 1; if (y == null) return -1;
          return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), "pt-BR")) * dir;
        });
        tr.querySelectorAll("th").forEach((h) => h.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        fill();
      };
      th.addEventListener("click", sort);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter") sort(); });
      tr.append(th);
    }
    const tbl = el("table", {}, el("thead", {}, tr), tbody);
    wrap.append(tbl);
    det.append(wrap);
    fill();
    return det;
  }

  // ------------------------------------------------------------------ SQL ---
  const SQL_RE = new RegExp([
    "(--[^\\n]*)",                                       // 1 comentário
    "('(?:[^']|'')*')",                                  // 2 string
    "\\b(SELECT|FROM|WHERE|AND|OR|NOT|JOIN|LEFT|INNER|ON|GROUP|BY|ORDER|HAVING|AS|WITH|CASE|WHEN|THEN|ELSE|END|" +
      "DESC|ASC|FETCH|FIRST|ROWS|ONLY|OVER|PARTITION|IN|IS|NULL|CROSS|DISTINCT|LIKE|BETWEEN)\\b", // 3 palavra-chave
    "\\b(SUM|AVG|COUNT|MAX|MIN|ROUND|NVL|NULLIF|SUBSTR|TO_NUMBER|MEDIAN|CORR_S|CORR|RATIO_TO_REPORT|" +
      "JSON_VALUE|NTILE|LOG|ABS)\\b",                     // 4 função
    "\\b(\\d+(?:\\.\\d+)?)\\b",                          // 5 número
  ].join("|"), "g");

  function highlight(sql) {
    const pre = el("pre", { class: "sql" });
    const code = el("code");
    let last = 0;
    for (const m of sql.matchAll(SQL_RE)) {
      if (m.index > last) code.append(sql.slice(last, m.index));
      const cls = m[1] ? "com" : m[2] ? "str" : m[3] ? "kw" : m[4] ? "fn" : "num";
      code.append(el("span", { class: cls, text: m[0] }));
      last = m.index + m[0].length;
    }
    code.append(sql.slice(last));
    pre.append(code);
    return pre;
  }

  async function copiar(texto, btn) {
    const label = btn.querySelector("span:last-child");
    try {
      await navigator.clipboard.writeText(texto);
    } catch (e) {
      const ta = el("textarea", { style: "position:fixed;opacity:0" });
      ta.value = texto;
      document.body.append(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    label.textContent = "Copiado!";
    btn.classList.add("copiado");
    clearTimeout(btn._copiado);
    btn._copiado = setTimeout(() => { label.textContent = "Copiar"; btn.classList.remove("copiado"); }, 1600);
  }

  function buildSql(blocos) {
    const box = el("div", { class: "sql-box" });
    const tabs = el("div", { class: "sql-tabs", role: "tablist" });
    const areaId = `sql-${Math.random().toString(36).slice(2, 8)}`;
    const area = el("div", { id: areaId, role: "tabpanel" });
    let atual = 0;
    const icoCopiar = svgIcon('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>');
    const icoOk = svgIcon('<path d="M5 12.5l4.5 4.5L19 7.5"/>');
    icoCopiar.classList.add("ico-copiar"); icoOk.classList.add("ico-ok");
    const btn = el("button", { type: "button", class: "copy-btn", onclick: () => copiar(blocos[atual].sql, btn) },
      el("span", { class: "ico-troca", "aria-hidden": "true" }, icoCopiar, icoOk),
      el("span", { text: "Copiar" }));
    function mostrar(i) {
      atual = i;
      tabs.querySelectorAll(".sql-tab").forEach((t, j) => { t.setAttribute("aria-selected", String(i === j)); t.tabIndex = i === j ? 0 : -1; });
      area.replaceChildren(highlight(blocos[i].sql));
    }
    blocos.forEach((b, i) => tabs.append(el("button", {
      type: "button", class: "sql-tab", role: "tab", "aria-controls": areaId, text: b.titulo, onclick: () => mostrar(i),
    })));
    tabs.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const i = (atual + (e.key === "ArrowRight" ? 1 : -1) + blocos.length) % blocos.length;
      mostrar(i);
      tabs.children[i].focus();
    });
    box.append(el("div", { class: "sql-head" }, tabs, btn), area,
      el("div", { class: "sql-note", text: "Dialeto Oracle. Os filtros da sua pergunta já estão aplicados. "
        + "A demonstração roda em SQLite com o mesmo modelo relacional (DDL em sql/oracle_schema.sql)." }));
    mostrar(0);
    return box;
  }

  // ------------------------------------------------------------ dashboard ---
  // ------------------------------------------------------------ filtros ---
  // Barra de filtros editáveis: só os filtros que o dashboard usa (filtros_aceitos, vindo da API).
  function barraFiltros(res, aoMudar) {
    const fa = res.filtros_aceitos;
    if (!FILT || !fa || !fa.chaves.length) return null;
    const atual = res.params || {};
    const obrig = new Set(fa.obrigatorios);
    const campos = [];
    const sel = (chave, rotulo, todos, opcoes) => {
      const s = el("select", { "data-chave": chave, "aria-label": rotulo });
      if (!obrig.has(chave)) s.append(el("option", { value: "", text: todos }));
      for (const [v, t] of opcoes) s.append(el("option", { value: String(v), text: t }));
      s.value = atual[chave] != null ? String(atual[chave]) : "";
      s.addEventListener("change", enviar);
      campos.push(el("label", { class: "filtro" }, el("span", { text: rotulo }), s));
    };
    const coletar = () => {
      const p = {};
      for (const s of fs.querySelectorAll("select")) if (s.value) p[s.dataset.chave] = s.dataset.chave === "cap_cid" || s.dataset.chave === "carater" ? s.value : Number(s.value);
      const cods = [...fs.querySelectorAll("input[data-cod]")].map((i) => Number(i.dataset.cod)).filter(Boolean);
      if (cods.length) p.municipios = cods;
      return p;
    };
    function enviar() { aoMudar(coletar(), fs); }

    for (const chave of fa.chaves) {
      if (chave === "ano") sel("ano", "Ano", "Todos os anos", FILT.anos.map((a) => [a, String(a)]));
      if (chave === "drs") sel("drs", "DRS", "Todas as DRS", FILT.drs.map((d) => [d.drs_num, d.drs_nome]));
      if (chave === "cap_cid") sel("cap_cid", "Causa", "Todas as causas", FILT.capitulos.map((c) => [c.cap_cod, c.cap_nome]));
      if (chave === "carater") sel("carater", "Caráter", "Eletivo e urgência", [["Eletivo", "Eletivo"], ["Urgência", "Urgência"]]);
      if (chave === "top_n") {
        const ns = [...new Set([5, 10, 15, 20, 30, 50, atual.top_n].filter(Boolean))].sort((x, y) => x - y);
        sel("top_n", "Mostrar", "Padrão", ns.map((n) => [n, `Top ${n}`]));
      }
      if (chave === "municipios") {
        const cods = atual.municipios || [];
        for (let i = 0; i < fa.mun_max; i++) {
          const cod = cods[i];
          const inp = el("input", { type: "text", list: "dl-municipios", placeholder: obrig.has("municipios") ? "Município" : "Todos",
            "aria-label": fa.mun_max > 1 ? `Município ${i + 1}` : "Município", autocomplete: "off" });
          if (cod) { inp.value = FILT.nomeMun.get(cod) || ""; inp.dataset.cod = cod; }
          inp.addEventListener("change", () => {
            const nome = inp.value.trim();
            const c = FILT.munPorNome.get(nome.toLowerCase());
            inp.classList.toggle("invalido", Boolean(nome) && !c);
            if (nome && !c) return;
            if (c) inp.dataset.cod = c; else delete inp.dataset.cod;
            enviar();
          });
          campos.push(el("label", { class: "filtro filtro-mun" },
            el("span", { text: fa.mun_max > 1 ? `Município ${i + 1}` : "Município" }), inp));
        }
      }
    }
    const temFiltro = fa.chaves.some((k) => !obrig.has(k) && atual[k] != null && k !== "top_n");
    const limpar = el("button", { type: "button", class: "filtro-limpar", text: "Limpar filtros",
      onclick: () => aoMudar({}, fs) });
    if (!temFiltro) limpar.disabled = true;
    const fs = el("fieldset", { class: "filtros-bar" }, el("legend", { text: "Filtros" }), ...campos, limpar,
      el("span", { class: "filtro-status", "aria-live": "polite" }));
    return fs;
  }

  // refaz o dashboard de um turno com os filtros escolhidos, no mesmo lugar
  // classe de animação temporária: a entrada roda uma vez e não se repete quando a aba volta a aparecer
  function marcarEntrada(elm, classe, ms) {
    elm.classList.add(classe);
    setTimeout(() => elm.classList.remove(classe), ms);
  }

  async function refazerTurno(a, t, params, fs) {
    const status = fs.querySelector(".filtro-status");
    fs.disabled = true;
    t.dash.classList.add("atualizando");
    status.replaceChildren(el("span", { class: "spinner", "aria-hidden": "true" }), "Atualizando…");
    try {
      const res = await perguntar(t.text, t.qid, params);
      if (res.erro || !res.matched) throw new Error(res.erro || "Não consegui aplicar os filtros.");
      if (window.Plotly) t.charts.forEach(([div]) => Plotly.purge(div));
      t.charts = [];
      t.params = res.params || {};
      t.nivel = res.dashboard.status_geral;
      const novo = montarDash(t, res, (p, f) => refazerTurno(a, t, p, f));
      marcarEntrada(novo, "trocando", 400);
      t.dash.replaceWith(novo);
      t.dash = novo;
      atualizarStatus(a);
      if (ativa === a.id) t.charts.forEach(([div, spec]) => drawChart(div, spec));
      salvar();
    } catch (e) {
      fs.disabled = false;
      t.dash.classList.remove("atualizando");
      status.replaceChildren(el("span", { class: "erro", text: e.message }));
    }
  }

  function montarDash(t, res, aoFiltrar) {
    const d = res.dashboard;
    const root = el("div", { class: "dash" });
    const tags = (d.filtros || []).map((f) => el("span", { class: "tag", text: f }));
    if (d.simples) tags.unshift(el("span", { class: "tag tag-simples", text: "Relatório simples" }));
    root.append(el("div", { class: "dash-head" },
      el("div", {}, el("h2", { text: d.title }), el("div", { class: "dash-sub", text: d.subtitle || "" }),
        tags.length ? el("div", { class: "tags" }, tags) : null),
      el("button", { type: "button", class: "print-btn", title: "Imprimir este dashboard ou salvar em PDF",
        onclick: () => imprimir(t) },
      svgIcon('<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7" rx="1"/>'),
      el("span", { text: "Imprimir / PDF" }))));
    const barra = barraFiltros(res, aoFiltrar);
    if (barra) root.append(barra);

    if (d.kpis && d.kpis.length) {
      root.append(el("div", { class: "kpis" }, d.kpis.map((k) => el("div", { class: "kpi" },
        el("div", { class: "kpi-label", text: k.label }),
        el("div", { class: "kpi-value", text: k.value }),
        k.hint ? el("div", { class: "kpi-hint", text: k.hint }) : null))));
    }

    if (d.alertas && d.alertas.length) {
      root.append(el("h3", { class: "section-title" }, "Situação", badge(d.status_geral)));
      root.append(el("ul", { class: "alertas" }, d.alertas.map((al) => el("li", { class: `alerta st-${al.nivel}` },
        badge(al.nivel),
        el("div", { class: "alerta-ind", text: al.indicador }),
        el("div", { class: "alerta-val", text: al.valor }),
        el("div", { class: "alerta-exp", text: al.explicacao })))));
      root.append(el("p", { class: "legenda-status" }, badge("aceitavel"), badge("alerta"), badge("critico"),
        el("span", { text: "Limites configuráveis em app/alerts.py." })));
    }

    const analise = el("div", { class: "analise" });
    if (d.insights && d.insights.length) {
      analise.append(el("div", { class: "analise-col" }, el("h3", { class: "section-title", text: "O que os dados mostram" }),
        el("div", { class: "insights" }, el("ul", {}, d.insights.map((t, i) =>
          el("li", {}, el("span", { class: "ins-n", "aria-hidden": "true", text: String(i + 1).padStart(2, "0") }), ...destacarNumeros(t)))))));
    }
    if (d.relevancia) {
      const r = d.relevancia;
      analise.append(el("div", { class: "analise-col" }, el("h3", { class: "section-title", text: "Por que essa pergunta importa" }),
        el("div", { class: "relev" },
        el("div", { class: "relev-bloco" }, el("h4", { text: "O que tem de importante nesta pergunta" }),
          el("p", { text: r.importancia })),
        el("div", { class: "relev-bloco" }, el("h4", { text: "Problemas identificados" }),
          r.problemas.length
            ? el("ul", { class: "relev-prob" }, r.problemas.map((pr) => el("li", {},
              badge(pr.nivel), el("span", { text: `${pr.indicador}: ${pr.valor}` }))))
            : null,
          el("p", { class: "relev-resumo", text: r.resumo })),
        el("div", { class: "relev-bloco" }, el("h4", { text: "O que poderia ser feito" }),
          el("ol", {}, r.acoes.map((t) => el("li", { text: t })))))));
    }
    if (analise.childNodes.length) root.append(analise);
    const lista = ordenarGraficos(d.charts || []);
    const charts = el("div", { class: "charts", "data-n": String(lista.filter((c) => !c.wide).length),
      "data-mapa": lista.some(eMapa) ? "" : null });
    for (const c of lista) {
      const plot = el("div", { class: "plot", role: "img",
        "aria-label": c.title + (d.insights && d.insights.length ? `. ${d.insights[0]}` : "") });
      charts.append(el("div", { class: "card" + (c.wide ? " wide" : "") },
        el("h4", { text: c.title }), c.subtitle ? el("p", { class: "card-sub", text: c.subtitle }) : null, plot));
      t.charts.push([plot, c]);
    }
    root.append(charts);
    for (const t of d.tables || []) {
      if (!t.rows || !t.rows.length) continue;
      const tb = buildTable(t);
      // pergunta simples de tabela: o resultado é a própria tabela, já aberta, com o CSV em destaque
      if (d.simples === "tabela") { tb.open = true; tb.querySelector(".csv-btn").classList.add("csv-destaque"); }
      root.append(tb);
    }
    if (d.nota) root.append(el("p", { class: "nota", text: d.nota }));
    if (d.sql && d.sql.length) {
      root.append(el("h3", { class: "section-title", text: "Query SQL (Oracle)" }));
      root.append(buildSql(d.sql));
    }
    return root;
  }

  // --------------------------------------------------- conversa na aba ---
  // Cada pergunta da aba é um "turno": balão com a pergunta + o dashboard que responde a ela.
  const suave = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

  function montarAba(a) {
    a.nav = el("nav", { class: "turnos-nav", "aria-label": "Perguntas desta aba", hidden: "" });
    a.lista = el("div", { class: "turnos" });
    a.observer = new IntersectionObserver((entradas) => {
      for (const e of entradas) if (e.isIntersecting) marcarTurno(a, e.target.dataset.n);
    }, { rootMargin: "-120px 0px -65% 0px" });
    a.panel.replaceChildren(el("h1", { class: "sr-only", text: `DataCare_ · ${a.text}` }), a.nav, a.lista);
  }

  function marcarTurno(a, n) {
    a.nav.querySelectorAll(".turno-pill").forEach((b) => {
      if (b.dataset.n === n) {
        b.setAttribute("aria-current", "true");
        rolarParaVer(a.nav, b);
      } else b.removeAttribute("aria-current");
    });
  }

  function atualizarNav(a) {
    a.nav.hidden = a.turnos.length < 2;
    a.nav.replaceChildren(el("span", { class: "turnos-nav-label", text: "Perguntas:" }),
      ...a.turnos.map((t, i) => el("button", {
        type: "button", class: "turno-pill", "data-n": String(i + 1), title: t.text,
        onclick: () => t.el.scrollIntoView({ behavior: suave(), block: "start" }),
      }, el("span", { class: "turno-pill-n", text: String(i + 1) }), el("span", { class: "turno-pill-txt", text: t.text }))));
  }

  function atualizarStatus(a) {
    const nv = a.turnos.map((t) => t.nivel).filter(Boolean);
    setStatus(a, nv.length ? nv.reduce((x, y) => (ORDEM_NIVEL[y] > ORDEM_NIVEL[x] ? y : x)) : null);
  }

  // acrescenta um turno no fim da aba (balão + dashboard) e move a caixa de pergunta para depois dele
  function adicionarTurno(a, t, res, rolar) {
    const n = a.turnos.length + 1;
    t.charts = [];
    t.nivel = res.dashboard.status_geral;
    t.qid = res.question_id;
    t.params = res.params || {};
    t.dash = montarDash(t, res, (p, f) => refazerTurno(a, t, p, f));
    t.el = el("section", { class: "turno", "data-n": String(n), "aria-label": `Pergunta ${n}` },
      el("div", { class: "so-impressao" },
        el("strong", {}, el("span", { class: "marca-texto" }, el("span", { class: "m-data", text: "Data" }),
          el("span", { class: "m-care", text: "Care" }), el("span", { class: "m-u", text: "_" })),
        " · grupo SQLadies · adaptação demonstrativa da aplicação entregue à Oracle"),
        el("span", { text: `Pergunta: “${t.text}” · ${new Date().toLocaleDateString("pt-BR")}` })),
      el("div", { class: "balao-linha" }, el("div", { class: "balao" },
        el("span", { class: "balao-quem", text: `Você · pergunta ${n}` }), el("p", { text: t.text }))),
      t.dash);
    a.turnos.push(t);
    marcarEntrada(t.el, "entrando", 900);
    a.lista.append(t.el);
    a.observer.observe(t.el);
    if (a.caixa) a.caixa.remove();
    a.caixa = caixaNaAba(a, res.dashboard.seguintes || []);
    a.panel.append(a.caixa);
    atualizarNav(a);
    atualizarStatus(a);
    if (ativa === a.id) {
      if (a.drawn) t.charts.forEach(([div, spec]) => drawChart(div, spec));
      else desenharAba(a);
    }
    if (rolar) t.el.scrollIntoView({ behavior: suave(), block: "start" });
  }

  // caixa "fazer outra pergunta" no fim da aba, com 2–3 sugestões de continuação
  function caixaNaAba(a, seguintes) {
    let pend = null, pendText = "";
    const ta = el("textarea", { rows: "1", maxlength: "300", placeholder: "Pergunte outra coisa sem sair desta aba",
      "aria-label": "Outra pergunta nesta aba" });
    const btn = el("button", { type: "submit", class: "send", "aria-label": "Enviar pergunta" },
      svgIcon('<path d="M5 12h14M13 6l6 6-6 6"/>'));
    const form = el("form", { class: "composer", autocomplete: "off" }, ta, btn);
    const fb = el("div", { class: "aba-feedback", "aria-live": "polite" });
    const ajusta = () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 180) + "px"; };
    const sug = (q) => el("button", { type: "button", class: "chip", text: q.texto, onclick: () => {
      ta.value = q.texto; pend = q.id; pendText = q.texto; ajusta(); ta.focus();
      form.classList.remove("flash"); void form.offsetWidth; form.classList.add("flash");
    } });
    ta.addEventListener("input", () => { ajusta(); if (ta.value !== pendText) pend = null; });
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const texto = ta.value.trim();
      if (!texto || btn.disabled) return;
      btn.disabled = true;
      btn.replaceChildren(el("span", { class: "spinner", "aria-hidden": "true" }));
      try {
        const res = await perguntar(texto, pend);
        if (res.erro) throw new Error(res.erro);
        if (!res.matched) {
          fb.replaceChildren(el("p", { text: "Não encontrei uma análise para essa pergunta. Você quis dizer:" }),
            el("div", { class: "chips" }, res.sugestoes.map(sug)));
          return;
        }
        ta.value = "";
        adicionarTurno(a, { text: texto }, res, true);
        salvar();
      } catch (err) {
        fb.replaceChildren(el("p", { class: "erro", text: err.message }));
      } finally {
        btn.disabled = false;
        btn.replaceChildren(svgIcon('<path d="M5 12h14M13 6l6 6-6 6"/>'));
      }
    });
    return el("section", { class: "aba-pergunta" },
      el("h3", { text: "Fazer outra pergunta nesta aba" }),
      el("p", { class: "aba-pergunta-hint", text: "O novo dashboard aparece logo abaixo, nesta mesma aba." }),
      form, fb,
      seguintes.length ? el("div", { class: "aba-sugestoes" }, el("span", { text: "Sugestões:" }),
        el("div", { class: "chips" }, seguintes.map(sug))) : null);
  }

  // ---------------------------------------------------------------- abas ---
  function salvar() {
    try {
      const lista = [...abas.values()].map((a) => ({
        text: a.text, qid: a.qid,
        turnos: (a.turnos.length ? a.turnos : a.pendentes || []).map(({ text, qid, params }) => ({ text, qid, params })),
      }));
      localStorage.setItem(STORE, JSON.stringify({ abas: lista, ativa: ativa === "inicio" ? -1 : [...abas.keys()].indexOf(ativa) }));
    } catch (e) { /* ok */ }
    atualizarContinuar();
    $("#abas-menu").hidden = abas.size === 0;
  }

  // Início: atalhos para as abas abertas ("Continuar de onde parou")
  function atualizarContinuar() {
    const sec = $("#continuar");
    if (!sec) return;
    sec.hidden = abas.size === 0;
    $("#continuar-lista").replaceChildren(...[...abas.values()].map((a) => el("button", {
      type: "button", class: "chip", text: a.text, onclick: () => ativar(a.id),
    })));
  }

  // rola só na horizontal a faixa (abas ou perguntas) até o item ficar visível. scrollIntoView também
  // rolaria a página por causa do scroll-padding-top e interromperia a rolagem suave em andamento.
  function rolarParaVer(faixa, item) {
    const ini = item.offsetLeft - faixa.offsetLeft, fim = ini + item.offsetWidth;
    if (ini < faixa.scrollLeft) faixa.scrollLeft = ini - 8;
    else if (fim > faixa.scrollLeft + faixa.clientWidth) faixa.scrollLeft = fim - faixa.clientWidth + 8;
  }

  // endereço da aba: "/" para a Início, "#pergunta=<texto>" para as demais
  const hashDe = (id) => (id === "inicio" ? "" : "#pergunta=" + encodeURIComponent(abas.get(id).text));

  function ativar(id, { historico = "push" } = {}) {
    ativa = id;
    if (historico !== "nenhum") {
      const url = location.pathname + hashDe(id);
      if (url !== location.pathname + location.hash || historico === "replace") {
        history[historico === "replace" ? "replaceState" : "pushState"]({ aba: id }, "", url);
      }
    }
    for (const t of tabsEl.querySelectorAll(".tab")) {
      const sel = t.dataset.tab === id;
      t.setAttribute("aria-selected", String(sel));
      t.tabIndex = sel ? 0 : -1;
    }
    for (const p of panelsEl.children) p.hidden = p.id !== `panel-${id}`;
    const tab = tabsEl.querySelector(`[data-tab="${id}"]`);
    if (tab) rolarParaVer(tabsEl, tab);
    bordasAbas();
    window.scrollTo(0, 0);
    if (id === "inicio") input.focus();
    else requestAnimationFrame(() => desenharAba(abas.get(id)));
    salvar();
  }

  function fechar(id) {
    const a = abas.get(id);
    if (!a) return;
    const ids = [...abas.keys()];
    const pos = ids.indexOf(id);
    if (window.Plotly) graficos(a).forEach(([div]) => Plotly.purge(div));
    if (a.observer) a.observer.disconnect();
    a.tab.remove();
    a.panel.remove();
    abas.delete(id);
    bordasAbas();
    if (ativa === id) ativar(ids[pos + 1] || ids[pos - 1] || "inicio");
    else salvar();
  }

  function setStatus(a, estado) {
    a.estado = estado;
    const slot = a.tab.querySelector(".tab-status");
    const n = NIVEL[estado];
    if (estado === "carregando") slot.replaceChildren(el("span", { class: "spinner", "aria-hidden": "true" }));
    else if (n) {
      // mesmo ícone dos alertas do dashboard: a forma (✓ ! ✕) diz a situação, não só a cor
      const sico = el("span", { class: `tab-sico st-${estado}`, "aria-hidden": "true" });
      sico.append(svgIcon(ICONE_NIVEL[estado]));
      slot.replaceChildren(sico);
    } else slot.replaceChildren(el("span", { class: "tab-sico", "aria-hidden": "true" }));
    const sit = estado === "carregando" ? "carregando" : n ? `situação: ${n.rotulo}` : "";
    a.tab.setAttribute("aria-label", sit ? `${a.text} (${sit})` : a.text);
    a.tab.title = `${a.text}${n ? ` · Situação: ${n.rotulo}` : ""}\nDelete fecha a aba`;
  }

  // pendentes: turnos a montar (a 1ª pergunta e, ao reabrir, as feitas dentro da aba)
  function novaAba(text, qid, pendentes = [{ text, qid }]) {
    const id = `aba-${++seq}`;
    const panel = el("section", { class: "panel", id: `panel-${id}`, role: "tabpanel", "aria-labelledby": `tab-${id}`, hidden: "" });
    // o X atende o mouse; no teclado a aba inteira é um controle só e Delete a fecha (aria-keyshortcuts)
    const close = el("span", { class: "tab-close", "aria-hidden": "true", title: "Fechar aba" },
      svgIcon('<path d="M6 6l12 12M18 6L6 18"/>'));
    const tab = el("div", { class: "tab", id: `tab-${id}`, role: "tab", "aria-selected": "false", tabindex: "-1",
      "aria-controls": `panel-${id}`, "aria-keyshortcuts": "Delete", "data-tab": id, title: `${text}\nDelete fecha a aba` },
      el("span", { class: "tab-status" }), el("span", { class: "tab-title", text }), close);
    close.addEventListener("click", (e) => { e.stopPropagation(); fechar(id); });
    tab.addEventListener("click", () => ativar(id));
    tab.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ativar(id); }
      if (e.key === "Delete") { e.preventDefault(); fechar(id); }
    });
    tab.addEventListener("auxclick", (e) => { if (e.button === 1) { e.preventDefault(); fechar(id); } });
    tabsEl.append(tab);
    panelsEl.append(panel);
    const a = { id, text, qid, tab, panel, turnos: [], pendentes, drawn: false, caixa: null };
    abas.set(id, a);
    return a;
  }

  async function carregar(a, preRes) {
    setStatus(a, "carregando");
    // esqueleto no formato do dashboard, no lugar do spinner
    a.panel.replaceChildren(el("div", { class: "esqueleto", role: "status", "aria-label": "Gerando dashboard…" },
      ["e-balao", "e-titulo", "e-sub", "e-kpis", "e-graf"].map((c) => el("i", { class: c, "aria-hidden": "true" }))));
    const pend = a.pendentes;
    try {
      const res = preRes || await perguntar(pend[0].text, pend[0].qid, pend[0].params);
      if (res.erro || !res.matched) {
        throw Object.assign(new Error(res.erro || "Não encontrei uma análise para essa pergunta."),
          { sugestoes: res.sugestoes || [], semMatch: !res.erro });
      }
      a.qid = res.question_id;
      montarAba(a);
      adicionarTurno(a, { text: pend[0].text }, res, false);
      // perguntas feitas dentro da aba na visita anterior
      for (const p of pend.slice(1)) {
        try {
          const r = await perguntar(p.text, p.qid, p.params);
          if (r.matched && !r.erro) adicionarTurno(a, { text: p.text }, r, false);
        } catch (e) { /* ignora a pergunta que falhou */ }
      }
      a.pendentes = null;
      salvar();
    } catch (e) {
      setStatus(a, null);
      a.panel.replaceChildren(erroComSaida(a, e));
    }
  }

  // erro da aba: o que aconteceu, o que fazer e um caminho para seguir
  function erroComSaida(a, e) {
    const sug = e.sugestoes || [];
    const abrir = (q) => { fechar(a.id); enviar(q.texto, q.id); };
    const dica = e.semMatch
      ? (sug.length ? "Escolha uma das perguntas parecidas abaixo ou volte ao Início para escrever de outro jeito."
        : "Volte ao Início e escreva de outro jeito, citando um município, uma DRS, um ano ou uma causa.")
      : "Confira se o servidor está rodando (uvicorn app.main:app) e tente de novo.";
    return el("div", { class: "erro-box", role: "alert" },
      el("h2", { text: e.message }),
      el("p", { text: dica }),
      sug.length ? el("div", { class: "chips" }, sug.slice(0, 3).map((q) =>
        el("button", { type: "button", class: "chip", text: q.texto, onclick: () => abrir(q) }))) : null,
      el("div", { class: "erro-acoes" },
        e.semMatch ? null : el("button", { type: "button", class: "btn-sec", text: "Tentar de novo", onclick: () => carregar(a) }),
        el("button", { type: "button", class: "btn-sec", text: "Voltar ao Início", onclick: () => ativar("inicio") })));
  }

  async function perguntar(text, qid, params) {
    const r = await fetch("/api/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, question_id: qid || null, params: qid && params ? params : null }),
    });
    if (!r.ok) throw new Error(`Erro do servidor (HTTP ${r.status}).`);
    return r.json();
  }

  // --------------------------------------------------------------- início ---
  function chip(q) {
    return el("button", { type: "button", class: "chip", text: q.texto, onclick: () => preencher(q) });
  }

  function preencher(q) {
    input.value = q.texto;
    pendingId = q.id;
    pendingText = q.texto;
    autosize();
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    form.classList.remove("flash");
    void form.offsetWidth;
    form.classList.add("flash");
  }

  function mostrarFeedback(...kids) {
    feedback.replaceChildren(kids.length ? el("div", { class: "box" }, kids) : "");
  }

  async function enviar(text, qid) {
    const norm = text.trim().toLowerCase();
    const existente = [...abas.values()].find((a) => a.text.trim().toLowerCase() === norm);
    if (existente) { ativar(existente.id); return; }
    sendBtn.disabled = true;
    sendBtn.replaceChildren(el("span", { class: "spinner", "aria-hidden": "true" }));
    try {
      const res = await perguntar(text, qid);
      if (!res.matched && !res.erro) {
        mostrarFeedback(el("p", { text: "Não encontrei uma análise para essa pergunta. Você quis dizer:" }),
          el("div", { class: "chips" }, res.sugestoes.map(chip)));
        return;
      }
      mostrarFeedback();
      input.value = ""; pendingId = null; pendingText = "";
      autosize();
      const a = novaAba(text, res.question_id);
      ativar(a.id);
      await carregar(a, res);
    } catch (e) {
      mostrarFeedback(el("p", { class: "erro", text: "Não consegui falar com o servidor. Ele está rodando? (" + e.message + ")" }));
    } finally {
      sendBtn.disabled = false;
      sendBtn.replaceChildren(svgIcon('<path d="M5 12h14M13 6l6 6-6 6"/>'));
    }
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }
  input.addEventListener("input", () => {
    autosize();
    if (input.value !== pendingText) pendingId = null; // texto editado: o matcher decide
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || sendBtn.disabled) return;
    enviar(text, pendingId);
  });
  $("#tab-inicio").addEventListener("click", () => ativar("inicio"));
  // Voltar/Avançar do navegador trocam de aba
  window.addEventListener("popstate", () => {
    const texto = perguntaDoHash();
    if (!texto) return ativar("inicio", { historico: "nenhum" });
    const a = [...abas.values()].find((x) => x.text === texto);
    if (a) ativar(a.id, { historico: "nenhum" }); else enviar(texto, null);
  });
  function perguntaDoHash() {
    const m = location.hash.match(/^#pergunta=(.+)$/);
    try { return m ? decodeURIComponent(m[1]).trim().slice(0, 300) : ""; } catch (e) { return ""; }
  }

  // menu "Todas as abas": cartão com cada aba aberta (situação, pergunta e quantas perguntas tem)
  const menuBtn = $("#abas-menu-btn"), menuCartao = $("#abas-menu-cartao");
  const plural = new Intl.PluralRules("pt-BR");
  function abrirMenuAbas() {
    const itens = [...abas.values()].map((a) => {
      const n = NIVEL[a.estado];
      const sico = el("span", { class: `tab-sico ${n ? "st-" + a.estado : ""}`, "aria-hidden": "true" });
      if (n) sico.append(svgIcon(ICONE_NIVEL[a.estado]));
      const qtd = (a.turnos.length || (a.pendentes || []).length || 1);
      const sub = a.estado === "carregando" ? "Carregando…" : n ? `Situação: ${n.rotulo}` : "Sem situação";
      return el("button", { type: "button", class: "abas-menu-item", role: "menuitem", tabindex: "-1",
        "aria-current": a.id === ativa ? "true" : null, onclick: () => { fecharMenuAbas(false); ativar(a.id); } },
        el("span", { class: "ami-ico" }, sico),
        el("span", { class: "ami-txt" }, el("strong", { text: a.text }), el("span", { text: sub })),
        el("span", { class: "ami-meta", text: `${qtd} ${plural.select(qtd) === "one" ? "pergunta" : "perguntas"}` }));
    });
    menuCartao.replaceChildren(el("p", { class: "abas-menu-titulo", text: "Abas abertas" }), ...itens);
    menuCartao.hidden = false;
    menuBtn.setAttribute("aria-expanded", "true");
    (menuCartao.querySelector('[aria-current="true"]') || itens[0]).focus();
  }
  function fecharMenuAbas(devolverFoco = true) {
    if (menuCartao.hidden) return;
    menuCartao.hidden = true;
    menuBtn.setAttribute("aria-expanded", "false");
    if (devolverFoco) menuBtn.focus();
  }
  menuBtn.addEventListener("click", () => (menuCartao.hidden ? abrirMenuAbas() : fecharMenuAbas()));
  menuCartao.addEventListener("keydown", (e) => {
    const itens = [...menuCartao.querySelectorAll(".abas-menu-item")];
    const i = itens.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      itens[(i + (e.key === "ArrowDown" ? 1 : -1) + itens.length) % itens.length].focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault(); itens[e.key === "Home" ? 0 : itens.length - 1].focus();
    } else if (e.key === "Escape") { e.preventDefault(); fecharMenuAbas(); }
    else if (e.key === "Tab") fecharMenuAbas(false);
  });
  document.addEventListener("pointerdown", (e) => { if (!$("#abas-menu").contains(e.target)) fecharMenuAbas(false); });

  // degradê nas bordas da lista de abas quando há abas escondidas daquele lado
  function bordasAbas() {
    const fim = tabsEl.scrollWidth - tabsEl.clientWidth;
    tabsEl.classList.toggle("mais-esq", tabsEl.scrollLeft > 1);
    tabsEl.classList.toggle("mais-dir", fim - tabsEl.scrollLeft > 1);
  }
  tabsEl.addEventListener("scroll", bordasAbas, { passive: true });
  window.addEventListener("resize", bordasAbas);

  // navegação por teclado entre abas (setas)
  tabsEl.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const ids = ["inicio", ...abas.keys()];
    const i = ids.indexOf(ativa) + (e.key === "ArrowRight" ? 1 : -1);
    if (i >= 0 && i < ids.length) { ativar(ids[i]); tabsEl.querySelector(`[data-tab="${ids[i]}"]`).focus(); }
  });

  // ---------------------------------------------------------------- init ---
  async function carregarFiltros() {
    try {
      const f = await fetch("/api/filters").then((r) => r.json());
      f.nomeMun = new Map(f.municipios.map((m) => [m.cod_mun, m.nome]));
      f.munPorNome = new Map(f.municipios.map((m) => [m.nome.toLowerCase(), m.cod_mun]));
      document.body.append(el("datalist", { id: "dl-municipios" },
        f.municipios.map((m) => el("option", { value: m.nome }))));
      FILT = f;
    } catch (e) { FILT = null; /* sem filtros editáveis; o dashboard funciona igual */ }
  }

  async function carregarMapa() {
    try { GEO = await fetch("/static/vendor/sp_municipios.geojson").then((r) => r.json()); } catch (e) { GEO = null; }
  }

  async function init() {
    const doLink = perguntaDoHash(); // lido antes de a restauração das abas reescrever o endereço
    const filtros = carregarFiltros();
    const mapa = carregarMapa();
    try {
      const qs = await fetch("/api/questions").then((r) => r.json());
      const cat = $("#catalogo");
      for (const c of qs.categorias) {
        cat.append(el("div", { class: "cat" }, el("h2", { text: c.nome }),
          c.descricao ? el("p", { class: "cat-desc", text: c.descricao }) : null,
          el("div", { class: "chips" }, c.perguntas.map(chip))));
      }
    } catch (e) {
      mostrarFeedback(el("p", { class: "erro", text: "Não consegui carregar as perguntas. Inicie o servidor com: uvicorn app.main:app" }));
    }
    // espera a Geist carregar para os gráficos medirem o texto com a fonte certa
    await Promise.all([filtros, mapa, document.fonts ? document.fonts.ready : null]);
    // reabre as abas da última visita (preferência local; falha em silêncio)
    let salvo = null;
    try { salvo = JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { salvo = null; }
    if (salvo && Array.isArray(salvo.abas)) {
      const criadas = salvo.abas.filter((x) => x && x.text).map((x) => {
        // formato antigo: {text, qid, seg[]}; atual: {text, qid, turnos[]}
        const turnos = Array.isArray(x.turnos) ? x.turnos : [{ text: x.text, qid: x.qid }, ...(x.seg || [])];
        return novaAba(x.text, x.qid, turnos.filter((t) => t && t.text));
      });
      const alvo = criadas[salvo.ativa];
      ativar(alvo ? alvo.id : "inicio", { historico: "replace" });
      for (const a of criadas) carregar(a);
    } else {
      ativar("inicio", { historico: "replace" });
    }
    // link direto para uma pergunta (#pergunta=…): abre a aba dela (ou reativa, se já estiver aberta)
    if (doLink) {
      const a = [...abas.values()].find((x) => x.text === doLink);
      if (a) ativar(a.id, { historico: "replace" }); else enviar(doLink, null);
    }
    // com o Início na tela, o Plotly vem em segundo plano: o primeiro dashboard não espera o download
    const ocioso = window.requestIdleCallback || ((f) => setTimeout(f, 300));
    ocioso(() => carregarPlotly().catch(() => {}));
  }
  init();
})();
