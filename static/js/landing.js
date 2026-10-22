/* DataCare_ (grupo SQLadies) — adaptação demonstrativa da aplicação entregue à Oracle.
   Landing page: tema, caixa de pergunta (abre /app#pergunta=…) e números reais do banco. */
(() => {
  "use strict";
  const raiz = document.documentElement;

  // tema: mesma preferência ("tema" no localStorage) usada pela aplicação
  document.getElementById("tema-btn").addEventListener("click", () => {
    const escuro = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    raiz.dataset.theme = escuro ? "light" : "dark";
    try { localStorage.setItem("tema", raiz.dataset.theme); } catch (e) { /* ok */ }
  });

  // a pergunta digitada aqui chega pronta na aplicação
  const form = document.getElementById("pergunta-form");
  const campo = document.getElementById("pergunta-campo");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = campo.value.trim() || campo.placeholder;
    location.href = "/app#pergunta=" + encodeURIComponent(texto);
  });

  // o placeholder alterna entre perguntas reais do catálogo (para quando o campo recebe foco ou texto)
  const exemplos = [
    "Quais hospitais estão mais lotados?",
    "Em que meses as internações aumentam?",
    "Quais causas mais custam ao SUS?",
    "Compare Santos e Guarujá",
    "Hospitais de Campinas em 2025",
  ];
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let i = 0;
    const timer = setInterval(() => {
      if (document.activeElement === campo || campo.value) return;
      i = (i + 1) % exemplos.length;
      campo.placeholder = exemplos[i];
    }, 3200);
    campo.addEventListener("input", () => campo.value && clearInterval(timer), { once: true });
  }

  // números reais do banco (os valores do HTML já são reais; isto só confirma com a API)
  const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  const inteiro = new Intl.NumberFormat("pt-BR");
  fetch("/api/resumo").then((r) => (r.ok ? r.json() : null)).then((d) => {
    if (!d) return;
    const valores = {
      internacoes: compacto.format(d.internacoes).replace(/\s?mi$/, " mi"),
      municipios: inteiro.format(d.municipios),
      hospitais: inteiro.format(d.hospitais),
      analises: inteiro.format(d.analises),
      periodo: `${d.ano_inicio}–${d.ano_fim}`,
    };
    for (const el of document.querySelectorAll("[data-resumo]")) {
      const v = valores[el.dataset.resumo];
      if (v) el.textContent = v;
    }
  }).catch(() => { /* sem API: ficam os valores do HTML */ });

  // malhas: pontos que se movem devagar e se ligam por linhas quando estão perto (estilo "plexus");
  // param fora da tela e com a aba escondida; com "reduzir movimento", ficam paradas
  const parado = matchMedia("(prefers-reduced-motion: reduce)").matches;
  function malha(canvas) {
    const ctx = canvas.getContext("2d");
    const escura = canvas.dataset.malha === "escura"; // sobre o bloco roxo: linhas claras nos dois temas
    let w = 0, h = 0, pontos = [], visivel = false, quadro = 0;
    let sementeAtual = 7;
    const aleatorio = () => ((sementeAtual = (sementeAtual * 16807) % 2147483647) / 2147483647);
    function montar() {
      const r = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
      w = r.width; h = r.height;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      sementeAtual = 7;
      const n = Math.min(150, Math.max(36, Math.round((w * h) / 8000)));
      pontos = Array.from({ length: n }, () => ({
        x: aleatorio() * w, y: aleatorio() * h,
        vx: (aleatorio() - 0.5) * 0.22, vy: (aleatorio() - 0.5) * 0.22,
        r: 1.4 + aleatorio() * 2.4, brilho: aleatorio() < 0.3,
      }));
    }
    function desenhar() {
      const escuro = escura || document.documentElement.dataset.theme === "dark"
        || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
      const linha = escura ? "196,166,247" : escuro ? "167,123,243" : "126,62,224";
      const forca = escuro ? 0.6 : 0.3;
      ctx.clearRect(0, 0, w, h);
      const lim = Math.min(180, Math.max(120, w / 8));
      for (let i = 0; i < pontos.length; i++) {
        const a = pontos[i];
        for (let j = i + 1; j < pontos.length; j++) {
          const b = pontos[j], dx = a.x - b.x, dy = a.y - b.y, d = Math.hypot(dx, dy);
          if (d < lim) {
            ctx.strokeStyle = `rgba(${linha},${(1 - d / lim) * forca})`;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      for (const p of pontos) {
        if (p.brilho) {
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
          g.addColorStop(0, `rgba(${linha},${forca * 0.9})`); g.addColorStop(1, `rgba(${linha},0)`);
          ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2); ctx.fill();
        }
        ctx.fillStyle = escura || escuro ? `rgba(226,212,255,${p.brilho ? 0.95 : 0.7})` : `rgba(${linha},${p.brilho ? 0.75 : 0.45})`;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
      }
    }
    function passo() {
      if (!visivel || document.hidden) { quadro = 0; return; }
      for (const p of pontos) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < -20) p.x = w + 20; else if (p.x > w + 20) p.x = -20;
        if (p.y < -20) p.y = h + 20; else if (p.y > h + 20) p.y = -20;
      }
      desenhar();
      quadro = requestAnimationFrame(passo);
    }
    const iniciar = () => { if (!parado && visivel && !quadro && !document.hidden) quadro = requestAnimationFrame(passo); };
    montar(); desenhar();
    new ResizeObserver(() => { montar(); desenhar(); }).observe(canvas);
    new IntersectionObserver(([e]) => { visivel = e.isIntersecting; iniciar(); }).observe(canvas);
    document.addEventListener("visibilitychange", iniciar);
    // o tema mudou: redesenha com as cores novas
    new MutationObserver(desenhar).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  }
  document.querySelectorAll("canvas[data-malha]").forEach(malha);

  // revela os blocos da página uma vez, quando entram na tela
  if ("IntersectionObserver" in window) {
    const blocos = document.querySelectorAll(".numeros-in, .secao-cab, .cadeia, .como, .recursos, .dados, .resultados, .proximos, .final");
    blocos.forEach((b) => b.setAttribute("data-revelar", ""));
    document.documentElement.classList.add("revelar-js");
    const io = new IntersectionObserver((entradas) => {
      for (const e of entradas) if (e.isIntersecting) { e.target.classList.add("visivel"); io.unobserve(e.target); }
    }, { rootMargin: "0px 0px -80px 0px" });
    blocos.forEach((b) => io.observe(b));
  }
})();
