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
})();
