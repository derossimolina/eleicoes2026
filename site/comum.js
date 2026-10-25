const fmt = new Intl.NumberFormat("pt-BR");

function texto(id, valor) {
  const el = document.getElementById(id);
  if (el) el.textContent = valor;
}

function pct(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

function pct1(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
}

function semAcento(s) {
  return (s || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

async function lerJson(caminho) {
  const resposta = await fetch(caminho);
  if (!resposta.ok) throw new Error(caminho + " " + resposta.status);
  return resposta.json();
}

function falhaDados(id) {
  texto(id, "Não consegui ler os arquivos de dados. Abra o site pelo servidor (python app.py) ou pelo endereço publicado. O navegador bloqueia esses arquivos se a página for aberta direto do disco.");
}

function numBr(valor) {
  if (valor == null || valor === "") return null;
  const n = Number(String(valor).trim().replace(/\./g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function intBr(valor) {
  const n = numBr(valor);
  return n == null ? 0 : Math.round(n);
}

function esc(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function centesimos(valor) {
  if (valor == null || valor === "") return null;
  const bruto = String(valor).trim().replace("%", "");
  if (!bruto || bruto === "—") return null;
  const negativo = bruto.startsWith("-");
  const corpo = bruto.replace(/^-/, "").trim();
  let esq;
  let dir;
  if (corpo.includes(",")) {
    [esq, dir = ""] = corpo.replace(/\./g, "").split(",");
  } else {
    [esq, dir = ""] = corpo.split(".");
  }
  if (!/^\d+$/.test(esq || "0") || (dir && !/^\d+$/.test(dir))) return null;
  const frac = (dir + "00").slice(0, 2);
  const total = Number(esq || "0") * 100 + Number(frac);
  return negativo ? -total : total;
}

function casas2(valor) {
  const cents = centesimos(valor);
  if (cents == null) return "—";
  const negativo = cents < 0;
  const abs = Math.abs(cents);
  const inteiro = Math.trunc(abs / 100);
  const frac = String(abs % 100).padStart(2, "0");
  return (negativo ? "-" : "") + inteiro.toLocaleString("pt-BR") + "," + frac + "%";
}

const prefereMenosMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function animarBarras(raiz) {
  if (!raiz) return;
  const fatias = raiz.matches(".fatia-lula, .fatia-flavio, .fatia-cobertura")
    ? [raiz]
    : raiz.querySelectorAll(".fatia-lula, .fatia-flavio, .fatia-cobertura");
  fatias.forEach((el) => {
    const alvo = el.style.width;
    if (!alvo) return;
    el.dataset.alvo = alvo;
    if (prefereMenosMovimento) return;
    el.style.transition = "none";
    el.style.width = "0%";
    void el.offsetWidth;
    el.style.transition = "";
    el.style.width = alvo;
  });
}

const EASE = "cubic-bezier(.7,0,.3,1)";
let saindo = false;

function mesmaPagina(url) {
  return url.pathname === location.pathname && url.search === location.search;
}

function gravarTransicao(rotulo) {
  try { sessionStorage.setItem("derossi-transicao", rotulo); } catch (erro) {}
}

function lerTransicao() {
  try {
    const valor = sessionStorage.getItem("derossi-transicao") || "";
    sessionStorage.removeItem("derossi-transicao");
    return valor;
  } catch (erro) {
    return "";
  }
}

function rotuloDoLink(link) {
  const textoLink = (link.textContent || "").replace(/\s+/g, " ").trim();
  if (textoLink) return textoLink;
  const img = link.querySelector("img");
  if (img && img.alt) return img.alt;
  return "Eleições 2026";
}

function montarCortina() {
  if (document.querySelector(".cortina")) return;
  const cortina = document.createElement("div");
  cortina.className = "cortina";
  cortina.setAttribute("aria-hidden", "true");
  cortina.innerHTML = '<div class="cortina-faixa b"></div><div class="cortina-faixa"></div><p class="cortina-titulo"></p>';
  document.body.appendChild(cortina);
}

function limparCortina() {
  const cortina = document.querySelector(".cortina");
  if (!cortina) return;
  cortina.classList.remove("ativa", "cobre");
  cortina.querySelectorAll(".cortina-faixa, .cortina-titulo").forEach((el) => {
    el.getAnimations().forEach((anim) => anim.cancel());
  });
}

function animarEl(el, quadros, opcoes) {
  return el.animate(quadros, { fill: "forwards", easing: EASE, ...opcoes });
}

function cortinaEntra(rotulo) {
  const cortina = document.querySelector(".cortina");
  if (!cortina) return;
  const faixas = cortina.querySelectorAll(".cortina-faixa");
  const titulo = cortina.querySelector(".cortina-titulo");
  cortina.classList.add("ativa");
  cortina.classList.remove("cobre");
  titulo.textContent = rotulo || "Eleições 2026";
  animarEl(faixas[0], [
    { transform: "translateX(-120%) skewX(-12deg)" },
    { transform: "translateX(0) skewX(-12deg)" },
  ], { duration: 420 });
  animarEl(faixas[1], [
    { transform: "translateX(-120%) skewX(-12deg)" },
    { transform: "translateX(0) skewX(-12deg)" },
  ], { duration: 420, delay: 70 });
  animarEl(titulo, [
    { opacity: 0, transform: "translateX(-40px)" },
    { opacity: 1, transform: "none" },
  ], { duration: 360, delay: 220 });
}

function cortinaSai() {
  const cortina = document.querySelector(".cortina");
  if (!cortina || !cortina.classList.contains("cobre")) return;
  cortina.dataset.saindo = "1";
  const faixas = cortina.querySelectorAll(".cortina-faixa");
  const titulo = cortina.querySelector(".cortina-titulo");
  window.setTimeout(() => {
    animarEl(titulo, [
      { opacity: 1, transform: "none" },
      { opacity: 0, transform: "translateX(40px)" },
    ], { duration: 260 });
    const frente = animarEl(faixas[1], [
      { transform: "translateX(0) skewX(-12deg)" },
      { transform: "translateX(130%) skewX(-12deg)" },
    ], { duration: 460, delay: 60 });
    animarEl(faixas[0], [
      { transform: "translateX(0) skewX(-12deg)" },
      { transform: "translateX(130%) skewX(-12deg)" },
    ], { duration: 460 });
    frente.onfinish = limparCortina;
  }, 140);
  window.setTimeout(limparCortina, 1400);
}

function prepararMenu() {
  const nav = document.querySelector(".nav");
  const cab = document.querySelector(".cabecalho");
  if (!nav || !cab || document.querySelector(".menu-botao")) return;
  nav.id = nav.id || "menu-paginas";
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = "menu-botao";
  botao.setAttribute("aria-expanded", "false");
  botao.setAttribute("aria-controls", nav.id);
  botao.setAttribute("aria-label", "Abrir o menu");
  botao.innerHTML = "<span></span><span></span><span></span>";
  cab.appendChild(botao);
  const ajustarTopo = () => {
    const topo = document.querySelector(".topo");
    if (topo) document.documentElement.style.setProperty("--altura-topo", topo.offsetHeight + "px");
  };
  ajustarTopo();
  const fechar = () => {
    nav.classList.remove("aberto");
    botao.setAttribute("aria-expanded", "false");
    botao.setAttribute("aria-label", "Abrir o menu");
    document.body.style.overflow = "";
  };
  botao.addEventListener("click", () => {
    const abrir = !nav.classList.contains("aberto");
    nav.classList.toggle("aberto", abrir);
    botao.setAttribute("aria-expanded", abrir ? "true" : "false");
    botao.setAttribute("aria-label", abrir ? "Fechar o menu" : "Abrir o menu");
    document.body.style.overflow = abrir ? "hidden" : "";
    if (abrir) ajustarTopo();
    if (abrir) {
      nav.querySelectorAll("a").forEach((a, i) => {
        a.style.transitionDelay = `${60 + i * 35}ms`;
      });
    }
  });
  nav.addEventListener("click", (ev) => {
    if (ev.target.closest("a")) fechar();
  });
  window.addEventListener("resize", () => {
    ajustarTopo();
    if (window.innerWidth > 860) fechar();
  });
}

function prepararTarjas() {
  document.querySelectorAll(".kicker").forEach((el) => {
    const bruto = el.textContent.trim();
    if (bruto.length > 46 || el.querySelector("span")) return;
    const faixa = document.createElement("span");
    faixa.textContent = bruto;
    el.replaceChildren(faixa);
    el.classList.add("tarja");
  });
}

function revelar() {
  if (prefereMenosMovimento) return;
  const els = [...document.querySelectorAll(".grade-hero > div, .cartao, .linha-titulo, h2.titulo, .tags, .legenda, .tabela-wrap, .grade-filtros")]
    .filter((el) => el.classList.contains("linha-titulo") || !el.closest(".linha-titulo"));
  if (!els.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entrada) => {
      if (!entrada.isIntersecting) return;
      entrada.target.classList.add("vis");
      entrada.target.addEventListener("animationend", () => {
        entrada.target.style.animation = "none";
      }, { once: true });
      io.unobserve(entrada.target);
    });
  }, { threshold: 0.08 });
  els.forEach((el, i) => {
    el.classList.add("an");
    if (el.getBoundingClientRect().top < window.innerHeight) {
      el.style.transitionDelay = `${Math.min(i, 8) * 70}ms`;
    }
  });
  window.setTimeout(() => els.forEach((el) => io.observe(el)), 30);
}

function prepararTransicao() {
  montarCortina();
  prepararMenu();
  prepararTarjas();
  revelar();
  const veio = lerTransicao();
  if (veio && !prefereMenosMovimento && document.querySelector(".cortina.cobre")) {
    cortinaSai();
  } else {
    limparCortina();
  }
  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) limparCortina();
  });
  if (prefereMenosMovimento) return;
  document.addEventListener("click", (ev) => {
    if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    const link = ev.target.closest("a[href]");
    if (!link || link.hasAttribute("download")) return;
    if (link.target && link.target !== "_self") return;
    let url;
    try {
      url = new URL(link.href, location.href);
    } catch (erro) {
      return;
    }
    if (url.origin !== location.origin || mesmaPagina(url)) return;
    ev.preventDefault();
    if (saindo) return;
    saindo = true;
    const rotulo = rotuloDoLink(link);
    gravarTransicao(rotulo);
    cortinaEntra(rotulo);
    window.setTimeout(() => {
      location.href = url.href;
    }, 600);
  });
}

prepararTransicao();
