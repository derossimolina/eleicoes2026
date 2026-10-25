const CORES = { pt: "#E04B4B", pl: "#2F6FED", empate: "#B7B1A8", sem: "#E6E2DA", outro: "#8C8378" };
const POR_PAGINA = 40;
const estado = { camada: "26", pagina: 0, deputados: [], filtrados: [], selecionado: null, camadaGeo: null };

const fmt = new Intl.NumberFormat("pt-BR");
const pct = (n) => (n == null || Number.isNaN(n) ? "—" : n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%");
const pct1 = (n) => (n == null ? "—" : Number(n).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%");
const semAcento = (s) => (s || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

function texto(id, valor) {
  const el = document.getElementById(id);
  if (el) el.textContent = valor;
}

async function lerJson(caminho) {
  const resposta = await fetch(caminho);
  if (!resposta.ok) throw new Error(caminho + " " + resposta.status);
  return resposta.json();
}

async function carregar() {
  try {
    const [resumo, pred] = await Promise.all([lerJson("dados/resumo.json"), lerJson("dados/prediction.json")]);
    pintarInicio(resumo, pred);
    pintarPesquisas(pred);
    pintarMetodo(pred);
    const deputados = await lerJson("dados/deputados.json");
    estado.deputados = deputados;
    prepararDeputados(resumo);
    const geo = await lerJson("dados/municipios.geojson");
    montarMapa(geo);
    if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
  } catch (erro) {
    texto("aviso-pred", "Não consegui ler os arquivos de dados. Abra o site por python app.py, em http://127.0.0.1:8765/. O navegador bloqueia esses arquivos se a página for aberta direto do disco.");
    console.error(erro);
  }
}

function pintarInicio(resumo, pred) {
  texto("aviso-pred", pred.aviso);
  texto("pct-flavio", pct(pred.media_ponderada_flavio_pct));
  texto("pct-lula", pct(pred.media_ponderada_lula_pct));
  texto("prob-flavio", Math.round(pred.prob_vitoria_flavio * 100) + "%");
  texto("prob-lula", Math.round(pred.prob_vitoria_lula * 100) + "%");
  const [a, b] = pred.intervalo_95_flavio_tau_2pp;
  texto("intervalo", pct1(a * 100) + " a " + pct1(b * 100));
  const s = pred.sensibilidade_prob_flavio;
  texto("sensibilidade", "Se o erro for 1,5 ponto, a chance de Flávio vai a " + Math.round(s.tau_1_5pp * 100 || s["tau_1.5pp"] * 100) + "%. Com 3 pontos, fica em " + Math.round(s["tau_3.0pp"] * 100) + "%.");
  texto("aviso-2t", resumo.segundo_turno.aviso + " Carimbo do arquivo: " + resumo.segundo_turno.carimbo_tse + ".");
  const t1 = resumo.primeiro_turno_2026;
  texto("t1-flavio", pct(t1.pct_flavio));
  texto("t1-lula", pct(t1.pct_lula));
  texto("t1-flavio-votos", fmt.format(t1.votos_flavio) + " votos");
  texto("t1-lula-votos", fmt.format(t1.votos_lula) + " votos");
  texto("t1-validos", fmt.format(t1.votos_validos));
  texto("t1-mun", fmt.format(t1.municipios) + " municípios, sem exterior");
  const caixa = document.getElementById("barras-uf");
  const ordenadas = [...resumo.ufs].sort((x, y) => y.pct_flavio - y.pct_lula - (x.pct_flavio - x.pct_lula));
  caixa.innerHTML = ordenadas.map((u) => {
    const total = u.pct_flavio + u.pct_lula || 1;
    const esq = (u.pct_lula / total) * 100;
    const margem = u.pct_flavio - u.pct_lula;
    const sinal = margem > 0 ? "+" : "";
    return `<div class="grid grid-cols-[2.5rem_1fr_4.5rem] items-center gap-2 text-xs">
      <span>${u.uf}</span>
      <div class="flex h-3 overflow-hidden rounded-sm" title="Lula ${pct(u.pct_lula)} · Flávio ${pct(u.pct_flavio)}">
        <span class="bg-pt" style="width:${esq}%"></span>
        <span class="bg-pl" style="width:${100 - esq}%"></span>
      </div>
      <span class="num text-right text-faint">${sinal}${margem.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</span>
    </div>`;
  }).join("");
}

function pintarPesquisas(pred) {
  const lista = document.getElementById("lista-pesquisas");
  lista.innerHTML = pred.pesquisas.map((p) => {
    const soma = p.flavio_validos + p.lula_validos || 1;
    const esq = (p.lula_validos / soma) * 100;
    return `<article class="grid gap-2 border-b border-muted pb-3 sm:grid-cols-[14rem_1fr_4rem] sm:items-center">
      <div>
        <p>${p.instituto}</p>
        <p class="text-xs text-faint">${p.data_inicio.slice(8)}–${p.data_fim.slice(8)}/10 · n=${fmt.format(p.n)}</p>
      </div>
      <div>
        <div class="flex h-3 overflow-hidden rounded-sm">
          <span class="bg-pt" style="width:${esq}%"></span>
          <span class="bg-pl" style="width:${100 - esq}%"></span>
        </div>
        <p class="mt-1 text-xs text-faint num">Lula ${pct(p.lula_validos)} · Flávio ${pct(p.flavio_validos)}</p>
      </div>
      <p class="num text-sm sm:text-right">${Math.round(p.peso_relativo * 1000) / 10}%</p>
    </article>`;
  }).join("");
}

function pintarMetodo(pred) {
  const fora = (pred.excluidas || []).map((e) => `${e.instituto}: ${e.observacao || e.motivo}`).join(" ");
  texto("metodo-exclusoes", fora ? "Ficaram de fora da média. " + fora : "");
  const linhas = pred.pesquisas.map((p) => `<tr class="border-b border-muted">
      <td class="py-2 pr-3">${p.instituto}</td>
      <td class="py-2 pr-3">${p.data_inicio} a ${p.data_fim}</td>
      <td class="py-2 pr-3 num">${fmt.format(p.n)}</td>
      <td class="py-2 pr-3 num">${String(p.margem_erro_pp).replace(".", ",")}</td>
      <td class="py-2 pr-3 num">${pct(p.flavio_validos)}</td>
      <td class="py-2 pr-3 num">${pct(p.lula_validos)}</td>
      <td class="py-2 pr-3 num">${Math.round(p.peso_relativo * 1000) / 10}%</td>
      <td class="py-2"><a class="underline" href="${p.url_fonte}">fonte</a></td>
    </tr>`).join("");
  document.getElementById("tabela-metodo").innerHTML = `<table class="min-w-full text-left text-sm">
    <thead class="text-faint"><tr>
      <th class="py-2 pr-3">Instituto</th><th class="py-2 pr-3">Campo</th><th class="py-2 pr-3">Amostra</th>
      <th class="py-2 pr-3">Margem</th><th class="py-2 pr-3">Flávio</th><th class="py-2 pr-3">Lula</th>
      <th class="py-2 pr-3">Peso</th><th class="py-2">Fonte</th>
    </tr></thead><tbody>${linhas}</tbody></table>`;
}

function corDe(props) {
  return CORES[props["c" + estado.camada]] || CORES.sem;
}

function estilo(feature) {
  const ativo = estado.selecionado && feature.properties.ibge === estado.selecionado;
  return {
    color: ativo ? "#141210" : "#ffffff",
    weight: ativo ? 1.6 : 0.3,
    fillColor: corDe(feature.properties),
    fillOpacity: 0.9,
  };
}

function fichaDe(p) {
  const bloco = (titulo, a, b, va, vb, validos, nomeA, nomeB) => `
    <h3 class="mt-4 text-xs uppercase tracking-widest text-faint">${titulo}</h3>
    <p class="mt-1">${nomeA} ${pct1(a)} <span class="text-faint num">${va == null ? "" : "· " + fmt.format(va)}</span></p>
    <p>${nomeB} ${pct1(b)} <span class="text-faint num">${vb == null ? "" : "· " + fmt.format(vb)}</span></p>
    <p class="text-faint">Válidos ${validos == null ? "—" : fmt.format(validos)}</p>`;
  document.getElementById("ficha").innerHTML = `
    <p class="text-xs uppercase tracking-widest text-faint">${p.uf || "Malha"}</p>
    <h3 class="font-display text-2xl leading-tight">${p.nm}</h3>
    ${p.v26 == null ? "<p class='mt-3 text-soft'>Sem voto de presidente neste polígono.</p>" : ""}
    ${bloco("2026, 1º turno", p.pl26, p.pf26, p.l26, p.f26, p.v26, "Lula", "Flávio")}
    ${bloco("2022, 2º turno", p.pl22, p.pb22, p.l22, p.b22, p.v22, "Lula", "Bolsonaro")}
    ${bloco("2018, 2º turno", p.ph18, p.pb18, p.h18, p.b18, p.v18, "Haddad", "Bolsonaro")}
    <p class="mt-4 text-xs text-faint">IBGE ${p.ibge}</p>`;
}

function montarMapa(geo) {
  const mapa = L.map("mapa-folha", { scrollWheelZoom: true }).setView([-14.2, -51.9], 4);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
    maxZoom: 12,
  }).addTo(mapa);
  const indice = new Map();
  estado.camadaGeo = L.geoJSON(geo, {
    style: estilo,
    onEachFeature(feature, layer) {
      indice.set(feature.properties.ibge, layer);
      layer.on("click", () => selecionar(feature.properties.ibge));
    },
  }).addTo(mapa);
  estado.indice = indice;
  estado.features = geo.features;
  document.querySelectorAll(".camada").forEach((botao) => {
    botao.addEventListener("click", () => {
      estado.camada = botao.dataset.camada;
      document.querySelectorAll(".camada").forEach((b) => {
        const ativo = b === botao;
        b.classList.toggle("bg-ink", ativo);
        b.classList.toggle("text-paper", ativo);
        b.classList.toggle("border-ink", ativo);
        b.classList.toggle("bg-white", !ativo);
      });
      estado.camadaGeo.setStyle(estilo);
    });
  });
  const busca = document.getElementById("busca-mun");
  const lista = document.getElementById("busca-resultado");
  busca.addEventListener("input", () => {
    const q = semAcento(busca.value.trim());
    if (q.length < 2) {
      lista.innerHTML = "";
      return;
    }
    const achados = geo.features.filter((f) => semAcento(`${f.properties.nm} ${f.properties.uf || ""}`).includes(q)).slice(0, 8);
    lista.innerHTML = achados.map((f) => `<li><button type="button" data-ibge="${f.properties.ibge}" class="w-full px-2 py-1 text-left hover:bg-subtle">${f.properties.nm}${f.properties.uf ? " · " + f.properties.uf : ""}</button></li>`).join("");
    lista.classList.add("border-line", "bg-white");
  });
  lista.addEventListener("click", (ev) => {
    const botao = ev.target.closest("button");
    if (!botao) return;
    selecionar(botao.dataset.ibge, true);
    lista.innerHTML = "";
  });
}

function selecionar(ibge, voar) {
  estado.selecionado = ibge;
  const layer = estado.indice.get(ibge);
  if (!layer) return;
  estado.camadaGeo.setStyle(estilo);
  const props = layer.feature.properties;
  fichaDe(props);
  if (voar) estado.camadaGeo._map.fitBounds(layer.getBounds(), { maxZoom: 8 });
}

function prepararDeputados(resumo) {
  const nota = resumo.deputado.nota_cadeira ? " " + resumo.deputado.nota_cadeira : "";
  texto("dep-resumo", `${fmt.format(resumo.deputado.candidaturas)} deferidos, ${fmt.format(resumo.deputado.eleitos)} eleitos na base, ${fmt.format(resumo.deputado.votos_nominais)} votos nominais.${nota}`);
  const ufs = [...new Set(estado.deputados.map((d) => d.sg_uf))].sort();
  const partidos = [...new Set(estado.deputados.map((d) => d.sg_partido))].sort();
  document.getElementById("filtro-uf").innerHTML = `<option value="">Todas</option>` + ufs.map((u) => `<option>${u}</option>`).join("");
  document.getElementById("filtro-partido").innerHTML = `<option value="">Todos</option>` + partidos.map((p) => `<option>${p}</option>`).join("");
  ["filtro-nome", "filtro-uf", "filtro-partido", "filtro-eleito"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => { estado.pagina = 0; desenharDeputados(); });
  });
  document.getElementById("pag-antes").addEventListener("click", () => { estado.pagina -= 1; desenharDeputados(); });
  document.getElementById("pag-depois").addEventListener("click", () => { estado.pagina += 1; desenharDeputados(); });
  document.getElementById("baixar-csv").addEventListener("click", baixarCsv);
  desenharDeputados();
}

function filtrar() {
  const nome = semAcento(document.getElementById("filtro-nome").value.trim());
  const uf = document.getElementById("filtro-uf").value;
  const partido = document.getElementById("filtro-partido").value;
  const soEleito = document.getElementById("filtro-eleito").checked;
  return estado.deputados.filter((d) => {
    if (uf && d.sg_uf !== uf) return false;
    if (partido && d.sg_partido !== partido) return false;
    if (soEleito && !d.eleito) return false;
    if (nome && !semAcento(`${d.nm_urna} ${d.nm_candidato}`).includes(nome)) return false;
    return true;
  });
}

function desenharDeputados() {
  estado.filtrados = filtrar();
  const total = estado.filtrados.length;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  estado.pagina = Math.min(estado.pagina, paginas - 1);
  const ini = estado.pagina * POR_PAGINA;
  const fatia = estado.filtrados.slice(ini, ini + POR_PAGINA);
  document.getElementById("corpo-dep").innerHTML = fatia.map((d) => `<tr class="border-b border-muted">
    <td class="px-3 py-2">${d.nm_urna}</td>
    <td class="px-3 py-2">${d.sg_uf}</td>
    <td class="px-3 py-2">${d.sg_partido}</td>
    <td class="px-3 py-2 text-right num">${fmt.format(d.votos_nominais)}</td>
    <td class="px-3 py-2">${d.eleito ? "Sim" : "Não"}</td>
    <td class="px-3 py-2">${d.superou_quociente ? "Superou" : "Não"}</td>
    <td class="px-3 py-2">${d.experiencia_previa ? "Sim" : "Não"}</td>
  </tr>`).join("");
  document.getElementById("dep-vazio").classList.toggle("hidden", total !== 0);
  texto("dep-contagem", fmt.format(total) + (total === 1 ? " candidatura" : " candidaturas"));
  texto("pag-info", `Página ${estado.pagina + 1} de ${paginas}`);
  document.getElementById("pag-antes").disabled = estado.pagina === 0;
  document.getElementById("pag-depois").disabled = estado.pagina >= paginas - 1;
}

function baixarCsv() {
  const cols = ["nm_urna", "nm_candidato", "sg_uf", "sg_partido", "votos_nominais", "eleito", "superou_quociente", "experiencia_previa", "votos_presidente_partido_uf"];
  const linhas = [cols.join(",")].concat(estado.filtrados.map((d) => cols.map((c) => {
    const v = d[c] == null ? "" : String(d[c]);
    return /[",\n]/.test(v) ? `"${v.replaceAll('"', '""')}"` : v;
  }).join(",")));
  const blob = new Blob([linhas.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "deputados_filtro.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

carregar();
