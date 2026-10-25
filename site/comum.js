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
  const fatias = raiz.matches(".fatia-clara, .fatia-escura")
    ? [raiz]
    : raiz.querySelectorAll(".fatia-clara, .fatia-escura");
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

function entrarNaPagina() {
  if (prefereMenosMovimento) return;
  document.body.classList.remove("saindo", "entrou");
  void document.body.offsetWidth;
  document.body.classList.add("entrou");
}

function mesmaPagina(url) {
  return url.pathname === location.pathname && url.search === location.search;
}

function prepararTransicao() {
  entrarNaPagina();
  window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) entrarNaPagina();
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
    if (document.body.classList.contains("saindo")) return;
    document.body.classList.remove("entrou");
    document.body.classList.add("saindo");
    window.setTimeout(() => {
      location.href = url.href;
    }, 280);
  });
}

prepararTransicao();
