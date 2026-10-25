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
