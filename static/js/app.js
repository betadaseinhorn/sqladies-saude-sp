/* SQLadies — adaptação demonstrativa da aplicação entregue à Oracle.
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
    aceitavel: { rotulo: "Aceitável", icone: "✓" },
    alerta: { rotulo: "Alerta", icone: "!" },
    critico: { rotulo: "Crítico", icone: "✕" },
  };
  const ORDEM_NIVEL = { aceitavel: 0, alerta: 1, critico: 2 };

  const abas = new Map(); // id -> {id, text, qid, params, tab, panel, charts[], drawn, data}
  let ativa = "inicio";
  let seq = 0;
  let pendingId = null; // id da pergunta escolhida num chip (enquanto o texto não for editado)
  let pendingText = "";

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
      series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => css(`--s${i}`)),
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
    const color = t.colorRole === "muted" ? T.muted : T.series[(t.colorSlot ?? 0) % 8];
    const isMuted = t.colorRole === "muted";
    if (t.type === "bar") {
      t.marker = Object.assign({}, t.marker);
      if (t.colorByValue === "diverging") {
        const vals = t.orientation === "h" ? t.x : t.y;
        t.marker.color = vals.map((v) => (v >= 0 ? T.pos : T.neg));
      } else t.marker.color = color;
      t.marker.line = { width: 0 };
      t.textfont = { color: T.text2, size: 11.5 };
      if (t.error_x) t.error_x = Object.assign({ color: T.text2, thickness: 1.5, width: 4 }, t.error_x);
    } else if (t.type === "scatter") {
      const lines = (t.mode || "").includes("lines");
      const markers = (t.mode || "").includes("markers");
      if (lines) t.line = Object.assign({ width: 2 }, t.line, { color });
      if (markers) {
        const m = t.marker || {};
        t.marker = Object.assign({ size: lines ? 7 : 8 }, m, {
          color: isMuted ? alpha(T.muted, 0.45) : color,
          line: { color: T.surface, width: lines ? 2 : 1 },
        });
        if (!lines && !isMuted && m.opacity == null) t.marker.opacity = 0.85;
      }
      if (t.fill) t.fillcolor = alpha(color, 0.1);
      if ((t.mode || "").includes("text")) t.textfont = { color: T.text2, size: 11 };
    } else if (t.type === "heatmap") {
      t.colorscale = t.scale === "sequential"
        ? [[0, T.seq0], [1, T.seq1]]
        : [[0, T.neg], [0.5, T.mid], [1, T.pos]];
      if (t.scale !== "sequential" && t.zmid === 0) {
        const flat = t.z.flat().filter((v) => v != null);
        const m = Math.max(...flat.map(Math.abs));
        t.zmin = -m; t.zmax = m;
      }
      t.colorbar = Object.assign({ outlinewidth: 0, tickfont: { color: T.text2, size: 11 } }, t.colorbar);
      t.hoverongaps = false;
    }
    delete t.colorSlot; delete t.colorRole; delete t.colorByValue; delete t.scale;
    return t;
  }

  function styleLayout(lay, traces, T, height) {
    const axis = (a = {}) => Object.assign({
      gridcolor: T.grid, linecolor: T.axis, zerolinecolor: T.axis, tickfont: { color: T.muted, size: 11.5 },
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
    }
    for (const ax of [L.xaxis, L.yaxis]) if (ax.type === "log" && ax.dtick == null) ax.dtick = 1;
    if (lay.xaxis && lay.xaxis.visible === false) L.xaxis.visible = false;
    if (lay.yaxis && lay.yaxis.visible === false) L.yaxis.visible = false;
    L.shapes = (lay.shapes || []).map((s) => {
      const c = Object.assign({}, s);
      if (c.role === "reference") { c.line = { color: T.text2, width: 1, dash: "dot" }; delete c.role; }
      return c;
    });
    return L;
  }

  function drawChart(div, spec) {
    const T = theme();
    const traces = spec.traces.map((t) => styleTrace(t, T));
    const layout = styleLayout(spec.layout || {}, traces, T, spec.height || 340);
    Plotly.react(div, traces, layout, { displayModeBar: false, responsive: true });
  }

  function desenharAba(a) {
    if (!a || !a.charts.length) return;
    if (a.drawn) { a.charts.forEach(([div]) => Plotly.Plots.resize(div)); return; }
    a.charts.forEach(([div, spec]) => drawChart(div, spec));
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
    return el("span", { class: `status-badge st-${nivel}` },
      el("span", { class: "sico", "aria-hidden": "true", text: n.icone }), n.rotulo);
  }

  // -------------------------------------------------------------- tabelas ---
  function buildTable(spec) {
    const det = el("details", { class: "tbl" }, el("summary", { text: `Ver tabela: ${spec.title} (${spec.rows.length})` }));
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
      const th = el("th", { class: isNum(c) ? "num" : "", scope: "col", tabindex: "0", text: c.label });
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
    const label = btn.querySelector("span");
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
    setTimeout(() => { label.textContent = "Copiar"; }, 1600);
  }

  function buildSql(blocos) {
    const box = el("div", { class: "sql-box" });
    const tabs = el("div", { class: "sql-tabs", role: "tablist" });
    const area = el("div");
    let atual = 0;
    const btn = el("button", { type: "button", class: "copy-btn", onclick: () => copiar(blocos[atual].sql, btn) },
      svgIcon('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>'),
      el("span", { text: "Copiar" }));
    function mostrar(i) {
      atual = i;
      tabs.querySelectorAll(".sql-tab").forEach((t, j) => t.setAttribute("aria-selected", String(i === j)));
      area.replaceChildren(highlight(blocos[i].sql));
    }
    blocos.forEach((b, i) => tabs.append(el("button", {
      type: "button", class: "sql-tab", role: "tab", text: b.titulo, onclick: () => mostrar(i),
    })));
    box.append(el("div", { class: "sql-head" }, tabs, btn), area,
      el("div", { class: "sql-note", text: "Dialeto Oracle. Os filtros da sua pergunta já estão aplicados. "
        + "A demonstração roda em SQLite com o mesmo modelo relacional (DDL em sql/oracle_schema.sql)." }));
    mostrar(0);
    return box;
  }

  // ------------------------------------------------------------ dashboard ---
  function renderDashboard(a, res) {
    const d = res.dashboard;
    const root = el("div", { class: "dash" });
    const tags = (d.filtros || []).map((f) => el("span", { class: "tag", text: f }));
    root.append(el("div", { class: "dash-head" },
      el("div", {}, el("h2", { text: d.title }), el("div", { class: "dash-sub", text: d.subtitle || "" }),
        tags.length ? el("div", { class: "tags" }, tags) : null),
      el("div", { class: "match-info", text: `Sua pergunta: “${a.text}”` })));

    if (d.kpis && d.kpis.length) {
      root.append(el("div", { class: "kpis" }, d.kpis.map((k) => el("div", { class: "kpi" },
        el("div", { class: "kpi-label", text: k.label }),
        el("div", { class: "kpi-value", text: k.value }),
        k.hint ? el("div", { class: "kpi-hint", text: k.hint }) : null))));
    }

    if (d.alertas && d.alertas.length) {
      root.append(el("h3", { class: "section-title" }, "Situação", badge(d.status_geral)));
      root.append(el("div", { class: "alertas" }, d.alertas.map((al) => el("div", { class: `alerta st-${al.nivel}` },
        badge(al.nivel),
        el("div", { class: "alerta-ind", text: al.indicador }),
        el("div", { class: "alerta-val", text: al.valor }),
        el("div", { class: "alerta-exp", text: al.explicacao })))));
      root.append(el("p", { class: "legenda-status",
        text: "✓ Aceitável · ! Alerta · ✕ Crítico. Limites configuráveis em app/alerts.py." }));
    }

    if (d.insights && d.insights.length) {
      root.append(el("div", { class: "insights" }, el("h3", { text: "O que os dados mostram" }),
        el("ul", {}, d.insights.map((t) => el("li", { text: t })))));
    }
    if (d.relevancia) {
      const r = d.relevancia;
      root.append(el("h3", { class: "section-title", text: "Por que essa pergunta importa" }));
      root.append(el("div", { class: "relev" },
        el("div", { class: "relev-bloco" }, el("h4", { text: "O que tem de importante nesta pergunta" }),
          el("p", { text: r.importancia })),
        el("div", { class: "relev-bloco" }, el("h4", { text: "Problemas identificados" }),
          r.problemas.length
            ? el("ul", { class: "relev-prob" }, r.problemas.map((pr) => el("li", {},
              badge(pr.nivel), el("span", { text: `${pr.indicador}: ${pr.valor}` }))))
            : null,
          el("p", { class: "relev-resumo", text: r.resumo })),
        el("div", { class: "relev-bloco" }, el("h4", { text: "O que poderia ser feito" }),
          el("ol", {}, r.acoes.map((t) => el("li", { text: t }))))));
    }
    const charts = el("div", { class: "charts" });
    a.charts = [];
    for (const c of d.charts || []) {
      const plot = el("div", { class: "plot", role: "img", "aria-label": c.title });
      charts.append(el("div", { class: "card" + (c.wide ? " wide" : "") },
        el("h4", { text: c.title }), c.subtitle ? el("p", { class: "card-sub", text: c.subtitle }) : null, plot));
      a.charts.push([plot, c]);
    }
    root.append(charts);
    for (const t of d.tables || []) if (t.rows && t.rows.length) root.append(buildTable(t));
    if (d.nota) root.append(el("p", { class: "nota", text: d.nota }));
    if (d.sql && d.sql.length) {
      root.append(el("h3", { class: "section-title", text: "Query SQL (Oracle)" }));
      root.append(buildSql(d.sql));
    }
    a.panel.replaceChildren(root);
    a.drawn = false;
    if (ativa === a.id) desenharAba(a);
  }

  // ---------------------------------------------------------------- abas ---
  function salvar() {
    try {
      const lista = [...abas.values()].map(({ text, qid }) => ({ text, qid }));
      localStorage.setItem(STORE, JSON.stringify({ abas: lista, ativa: ativa === "inicio" ? -1 : [...abas.keys()].indexOf(ativa) }));
    } catch (e) { /* ok */ }
  }

  function ativar(id) {
    ativa = id;
    for (const t of tabsEl.querySelectorAll(".tab")) {
      const sel = t.dataset.tab === id;
      t.setAttribute("aria-selected", String(sel));
      t.tabIndex = sel ? 0 : -1;
    }
    for (const p of panelsEl.children) p.hidden = p.id !== `panel-${id}`;
    const tab = tabsEl.querySelector(`[data-tab="${id}"]`);
    if (tab) tab.scrollIntoView({ block: "nearest", inline: "nearest" });
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
    a.charts.forEach(([div]) => Plotly.purge(div));
    a.tab.remove();
    a.panel.remove();
    abas.delete(id);
    if (ativa === id) ativar(ids[pos + 1] || ids[pos - 1] || "inicio");
    else salvar();
  }

  function setStatus(a, estado) {
    const slot = a.tab.querySelector(".tab-status");
    slot.replaceChildren(estado === "carregando" ? el("span", { class: "spinner", "aria-hidden": "true" })
      : el("span", { class: `dot ${estado ? "n-" + estado : ""}`, title: NIVEL[estado] ? `Situação: ${NIVEL[estado].rotulo}` : "" }));
  }

  function novaAba(text, qid) {
    const id = `aba-${++seq}`;
    const panel = el("section", { class: "panel", id: `panel-${id}`, role: "tabpanel", "aria-labelledby": `tab-${id}`, hidden: "" });
    const close = el("span", { class: "tab-close", role: "button", "aria-label": `Fechar aba: ${text}`, title: "Fechar aba" },
      svgIcon('<path d="M6 6l12 12M18 6L6 18"/>'));
    const tab = el("div", { class: "tab", id: `tab-${id}`, role: "tab", "aria-selected": "false", tabindex: "-1",
      "aria-controls": `panel-${id}`, "data-tab": id, title: text },
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
    const a = { id, text, qid, tab, panel, charts: [], drawn: false };
    abas.set(id, a);
    return a;
  }

  async function carregar(a, preRes) {
    setStatus(a, "carregando");
    a.panel.replaceChildren(el("div", { class: "loading" }, el("div", { class: "spinner" }), "Gerando dashboard…"));
    try {
      const res = preRes || await perguntar(a.text, a.qid);
      if (res.erro || !res.matched) throw new Error(res.erro || "Pergunta não reconhecida.");
      a.qid = res.question_id;
      renderDashboard(a, res);
      setStatus(a, res.dashboard.status_geral);
      salvar();
    } catch (e) {
      setStatus(a, null);
      a.panel.replaceChildren(el("div", { class: "erro-box" }, el("p", { class: "erro", text: e.message })));
    }
  }

  async function perguntar(text, qid) {
    const r = await fetch("/api/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, question_id: qid || null }),
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

  // navegação por teclado entre abas (setas)
  tabsEl.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const ids = ["inicio", ...abas.keys()];
    const i = ids.indexOf(ativa) + (e.key === "ArrowRight" ? 1 : -1);
    if (i >= 0 && i < ids.length) { ativar(ids[i]); tabsEl.querySelector(`[data-tab="${ids[i]}"]`).focus(); }
  });

  // ---------------------------------------------------------------- init ---
  async function init() {
    try {
      const qs = await fetch("/api/questions").then((r) => r.json());
      const cat = $("#catalogo");
      for (const c of qs.categorias) {
        cat.append(el("div", { class: "cat" }, el("h3", { text: c.nome }),
          el("div", { class: "chips" }, c.perguntas.map(chip))));
      }
    } catch (e) {
      mostrarFeedback(el("p", { class: "erro", text: "Não consegui carregar as perguntas. Inicie o servidor com: uvicorn app.main:app" }));
    }
    // reabre as abas da última visita (preferência local; falha em silêncio)
    let salvo = null;
    try { salvo = JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { salvo = null; }
    if (salvo && Array.isArray(salvo.abas)) {
      const criadas = salvo.abas.filter((x) => x && x.text).map((x) => novaAba(x.text, x.qid));
      const alvo = criadas[salvo.ativa];
      ativar(alvo ? alvo.id : "inicio");
      for (const a of criadas) carregar(a);
    } else {
      ativar("inicio");
    }
  }
  init();
})();
