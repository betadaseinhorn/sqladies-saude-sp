/* SQLadies · chat que gera dashboards (sem dependências além do Plotly local) */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const chat = $("#chat");
  const input = $("#pergunta");
  const form = $("#composer");
  const sendBtn = $("#send");
  const rendered = []; // gráficos para redesenhar quando o tema muda
  let pendingId = null; // id da pergunta escolhida num botão (enquanto o texto não for editado)
  let pendingText = "";

  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf3 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v);
    }
    for (const k of kids.flat()) if (k != null) n.append(k);
    return n;
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
      title: Object.assign({ font: { color: T.text2, size: 12 } }, a.title || {}), automargin: true,
      exponentformat: "none", separatethousands: true,
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

  function redrawAll() {
    for (const r of rendered) if (document.body.contains(r.div)) drawChart(r.div, r.spec);
  }

  $("#tema-btn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("tema", next); } catch (e) { /* ok */ }
    redrawAll();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redrawAll);

  // -------------------------------------------------------------- tabelas ---
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

  function buildTable(spec) {
    const det = el("details", { class: "tbl" }, el("summary", { text: `Ver tabela: ${spec.title} (${spec.rows.length})` }));
    const wrap = el("div", { class: "tbl-wrap" });
    const tbl = el("table");
    const thead = el("thead");
    const tbody = el("tbody");
    const isNum = (c) => c.fmt !== "text";
    let rows = spec.rows.slice();
    let sortKey = null, dir = 1;

    function fill() {
      tbody.replaceChildren(...rows.map((r) => el("tr", {}, spec.columns.map((c) =>
        el("td", { class: isNum(c) && typeof r[c.key] === "number" ? "num" : "", text: fmt(r[c.key], c.fmt) })))));
    }
    const tr = el("tr");
    for (const c of spec.columns) {
      const th = el("th", { class: isNum(c) ? "num" : "", scope: "col", tabindex: "0", text: c.label });
      const sort = () => {
        dir = sortKey === c.key ? -dir : (isNum(c) ? -1 : 1);
        sortKey = c.key;
        rows.sort((a, b) => {
          const x = a[c.key], y = b[c.key];
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
    thead.append(tr);
    tbl.append(thead, tbody);
    wrap.append(tbl);
    det.append(wrap);
    fill();
    return det;
  }

  // ---------------------------------------------------------------- chat ---
  function scrollTo(node) {
    requestAnimationFrame(() => node.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  function chip(q) {
    return el("button", { type: "button", class: "chip", text: q.texto, onclick: () => fill(q) });
  }

  function fill(q) {
    input.value = q.texto;
    pendingId = q.id;
    pendingText = q.texto;
    autosize();
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    $(".composer-box").classList.remove("flash");
    void $(".composer-box").offsetWidth;
    $(".composer-box").classList.add("flash");
    closeMenu();
  }

  function addUser(text) {
    const m = el("div", { class: "msg user" }, el("div", { class: "bubble", text }));
    chat.append(m);
    scrollTo(m);
  }

  function addBot(content) {
    const bubble = el("div", { class: "bubble" }, content);
    const m = el("div", { class: "msg bot" }, el("div", { class: "avatar", "aria-hidden": "true", text: "S" }), bubble);
    chat.append(m);
    return { msg: m, bubble };
  }

  function renderDashboard(res) {
    const d = res.dashboard;
    const frag = document.createDocumentFragment();
    const tags = (d.filtros || []).map((f) => el("span", { class: "tag", text: f }));
    frag.append(el("div", { class: "dash-head" },
      el("div", {}, el("h2", { text: d.title }), el("div", { class: "dash-sub", text: d.subtitle || "" }),
        tags.length ? el("div", { class: "tags" }, tags) : null),
      el("div", { class: "match-info", text: `Pergunta reconhecida: “${res.pergunta}”` })));

    if (d.kpis && d.kpis.length) {
      frag.append(el("div", { class: "kpis" }, d.kpis.map((k) => el("div", { class: "kpi" },
        el("div", { class: "kpi-label", text: k.label }),
        el("div", { class: "kpi-value", text: k.value }),
        k.hint ? el("div", { class: "kpi-hint", text: k.hint }) : null))));
    }
    if (d.insights && d.insights.length) {
      frag.append(el("div", { class: "insights" }, el("h3", { text: "O que os dados mostram" }),
        el("ul", {}, d.insights.map((t) => el("li", { text: t })))));
    }
    const charts = el("div", { class: "charts" });
    const toDraw = [];
    for (const c of d.charts || []) {
      const plot = el("div", { class: "plot", role: "img", "aria-label": c.title });
      charts.append(el("div", { class: "card" + (c.wide ? " wide" : "") },
        el("h4", { text: c.title }), c.subtitle ? el("p", { class: "card-sub", text: c.subtitle }) : null, plot));
      toDraw.push([plot, c]);
    }
    frag.append(charts);
    for (const t of d.tables || []) if (t.rows && t.rows.length) frag.append(buildTable(t));
    if (d.nota) frag.append(el("p", { class: "nota", text: d.nota }));
    if (res.sugestoes && res.sugestoes.length) {
      frag.append(el("div", { class: "followups" }, el("div", { class: "lbl", text: "Perguntas relacionadas" }),
        el("div", { class: "chips" }, res.sugestoes.map(chip))));
    }
    const { msg } = addBot(frag);
    msg.querySelector(".bubble").classList.add("dash");
    for (const [div, spec] of toDraw) { drawChart(div, spec); rendered.push({ div, spec }); }
    scrollTo(msg);
  }

  async function ask(text, questionId) {
    addUser(text);
    const { msg, bubble } = addBot(el("div", { class: "typing", "aria-label": "Gerando dashboard" },
      el("span"), el("span"), el("span")));
    scrollTo(msg);
    sendBtn.disabled = true;
    try {
      const r = await fetch("/api/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, question_id: questionId || null }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const res = await r.json();
      msg.remove();
      if (res.erro) {
        addBot(el("p", { class: "erro", text: res.erro }));
      } else if (!res.matched) {
        const { msg: m } = addBot([
          el("p", { text: "Não encontrei uma análise para essa pergunta. Você quis dizer alguma destas?" }),
          el("div", { class: "chips" }, res.sugestoes.map(chip)),
        ]);
        scrollTo(m);
      } else {
        renderDashboard(res);
      }
    } catch (e) {
      bubble.replaceChildren(el("p", { class: "erro", text: "Não consegui falar com o servidor. Ele está rodando? (" + e.message + ")" }));
    } finally {
      sendBtn.disabled = false;
    }
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
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
    const id = pendingId;
    input.value = ""; pendingId = null; pendingText = "";
    autosize();
    ask(text, id);
  });

  // --------------------------------------------------------- menu mobile ---
  const sidebar = $("#sidebar"), scrim = $("#scrim");
  function closeMenu() { sidebar.classList.remove("open"); scrim.hidden = true; }
  $("#menu-btn").addEventListener("click", () => { sidebar.classList.add("open"); scrim.hidden = false; });
  scrim.addEventListener("click", closeMenu);

  // ---------------------------------------------------------------- init ---
  async function init() {
    const welcome = $("#tpl-welcome").content.cloneNode(true);
    chat.append(welcome);
    try {
      const [qs, fl] = await Promise.all([fetch("/api/questions").then((r) => r.json()),
                                          fetch("/api/filters").then((r) => r.json())]);
      const nav = $("#catalogo");
      for (const c of qs.categorias) {
        nav.append(el("div", { class: "cat" }, el("h3", { text: c.nome }),
          c.perguntas.map((q) => el("button", { type: "button", class: "q-btn", text: q.texto, onclick: () => fill(q) }))));
      }
      const starters = ["visao_geral", "sazonal_cap_regiao", "comparar_municipios", "fatores"];
      const all = qs.categorias.flatMap((c) => c.perguntas);
      $("[data-role=starter]").append(...starters.map((id) => all.find((q) => q.id === id)).filter(Boolean).map(chip));
      if (fl.anos && fl.anos.length) $("#periodo").textContent = `${fl.anos[0]}–${fl.anos[fl.anos.length - 1]}`;
    } catch (e) {
      addBot(el("p", { class: "erro", text: "Não consegui carregar as perguntas. Inicie o servidor com: uvicorn app.main:app" }));
    }
  }
  init();
})();
