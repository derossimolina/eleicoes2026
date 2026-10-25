const UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"];
const URL_BR = "https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json";
const INTERVALO_NACIONAL_MS = 2 * 60 * 1000;

const estado = {
  municipios: [],
  porCd: new Map(),
  uf: "",
  atual: null,
  nacional: null,
  lidoEm: 0,
  lendoNacional: false,
  lidos: new Map(),
  controle: null,
};

function quandoCena(fn) {
  if (window.__cena) fn(window.__cena);
  else window.addEventListener("cena-pronta", () => fn(window.__cena), { once: true });
}

function esperar(ms, signal) {
  return new Promise((resolve, reject) => {
    const id = setTimeout(() => resolve(), ms);
    if (!signal) return;
    const abortar = () => {
      clearTimeout(id);
      reject(new DOMException("abortado", "AbortError"));
    };
    if (signal.aborted) abortar();
    else signal.addEventListener("abort", abortar, { once: true });
  });
}

const TSE_DADOS = "https://resultados.tse.jus.br/oficial/ele2026/6258/dados";

function urlOficial(caminho) {
  const partes = String(caminho).split("/").filter(Boolean);
  if (partes[0] !== "tse") return null;
  if (partes.length === 2 && partes[1] === "br") {
    return `${TSE_DADOS}/br/br-c0001-e006258-u.json`;
  }
  if (partes.length === 3 && partes[1] === "uf") {
    const uf = partes[2].toLowerCase();
    if (!UFS.includes(uf.toUpperCase())) return null;
    return `${TSE_DADOS}/${uf}/${uf}-c0001-e006258-u.json`;
  }
  if (partes.length === 4 && partes[1] === "mun") {
    const uf = partes[2].toLowerCase();
    const cd = partes[3];
    if (!UFS.includes(uf.toUpperCase()) || !/^\d{5}$/.test(cd)) return null;
    return `${TSE_DADOS}/${uf}/${uf}${cd}-c0001-e006258-u.json`;
  }
  return null;
}

async function baixarJson(url, signal) {
  const resposta = await fetch(url, { signal, cache: "no-store" });
  if (!resposta.ok) throw new Error(resposta.status + " " + url);
  return resposta.json();
}

async function lerTse(caminho, signal) {
  const oficial = urlOficial(caminho);
  if (oficial) {
    const vivo = oficial + "?nocache=" + Date.now();
    try {
      return await baixarJson(vivo, signal);
    } catch (erro) {
      if (erro && erro.name === "AbortError") throw erro;
    }
  }
  return baixarJson(caminho, signal);
}

function lerCandidatos(dados) {
  const achados = {};
  for (const cargo of dados.carg || []) {
    if (String(cargo.cd) !== "1") continue;
    for (const agr of cargo.agr || []) {
      for (const par of agr.par || []) {
        for (const cand of par.cand || []) {
          achados[Number(cand.n)] = {
            nome: cand.nmu || cand.nm || "",
            votos: intBr(cand.vap),
            partido: par.sg || "",
            percentual: cand.pvap,
          };
        }
      }
    }
  }
  return achados;
}

function resumir(dados) {
  const s = dados.s || {};
  const v = dados.v || {};
  const st = intBr(s.st);
  const ts = intBr(s.ts);
  const pst = numBr(s.pst);
  const saida = {
    carimbo: `${dados.dg || ""} ${dados.hg || ""}`.trim(),
    tf: dados.tf || "",
    st,
    ts,
    pst,
    pstTexto: s.pst == null || s.pst === "" ? null : String(s.pst),
    apurado: st > 0,
    fracao: pst != null ? pst / 100 : (ts ? st / ts : 0),
  };
  if (!saida.apurado) return saida;
  const cands = lerCandidatos(dados);
  saida.lula = cands[13] || { nome: "LULA", votos: 0, partido: "PT" };
  saida.flavio = cands[22] || { nome: "FLAVIO BOLSONARO", votos: 0, partido: "PL" };
  saida.vv = intBr(v.vv);
  saida.vb = intBr(v.vb);
  saida.vn = intBr(v.vn);
  saida.tv = intBr(v.tv);
  return saida;
}

function fraseSecoes(r) {
  const pctSecoes = r.pstTexto == null ? "—" : casas2(r.pstTexto);
  return `Carimbo ${r.carimbo || "—"}. Seções totalizadas: ${fmt.format(r.st)} de ${fmt.format(r.ts)} (${pctSecoes}). Totalização encerrada: ${r.tf === "s" ? "sim" : "não"}.`;
}

function pctCandidato(cand, votos, validos) {
  if (cand && cand.percentual != null && cand.percentual !== "") return casas2(cand.percentual);
  if (!validos) return "—";
  return casas2((100 * votos) / validos);
}

function fraseVotos(r) {
  if (!r.apurado) {
    return " Ainda sem apuração. Os zeros do arquivo não entram como voto.";
  }
  return ` ${r.lula.nome} ${fmt.format(r.lula.votos)} (${pctCandidato(r.lula, r.lula.votos, r.vv)}). ${r.flavio.nome} ${fmt.format(r.flavio.votos)} (${pctCandidato(r.flavio, r.flavio.votos, r.vv)}). Válidos ${fmt.format(r.vv)}. Brancos ${fmt.format(r.vb)}. Nulos ${fmt.format(r.vn)}. Comparecimento ${fmt.format(r.tv)}.`;
}

function horaLocal(ms) {
  return new Date(ms).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function semApuracaoNacional() {
  texto("nac-lula", "sem apuração");
  texto("nac-lula-votos", "Os zeros do arquivo não entram como voto.");
  texto("nac-flavio", "sem apuração");
  texto("nac-flavio-votos", "");
  texto("nac-validos", "sem apuração");
  texto("nac-brancos", "sem apuração");
  texto("nac-nulos", "");
  texto("nac-comparecimento", "sem apuração");
  document.getElementById("nac-barra-votos").innerHTML = "";
  document.getElementById("nac-barra-votos").classList.add("escondido");
  document.getElementById("nac-legenda-votos").classList.add("escondido");
}

function pintarNacional(r) {
  if (!r) {
    texto("nac-secoes", "—");
    texto("nac-pct-secoes", "");
    document.getElementById("nac-barra-secoes").innerHTML = "";
    semApuracaoNacional();
    ["nac-lula", "nac-flavio", "nac-validos", "nac-brancos", "nac-comparecimento"].forEach((id) => texto(id, "—"));
    texto("nac-lula-votos", "");
    texto("nac-atualizado", "");
    return;
  }
  texto(
    "status-nacional",
    `Arquivo nacional do TSE, com o exterior quando ele entra nessa soma. ${fraseSecoes(r)}${fraseVotos(r)} Fonte: ${URL_BR}.`
  );
  texto("nac-secoes", `${fmt.format(r.st)} de ${fmt.format(r.ts)}`);
  texto("nac-pct-secoes", r.pstTexto == null ? "" : `${casas2(r.pstTexto)} das seções`);
  const pctSecoes = r.pst == null ? 0 : Math.min(100, Math.max(0, r.pst));
  document.getElementById("nac-barra-secoes").innerHTML = `<span class="fatia-escura" style="width:${pctSecoes}%"></span>`;
  if (!r.apurado) {
    texto("nac-rotulo-lula", "Lula");
    texto("nac-rotulo-flavio", "Flávio");
    semApuracaoNacional();
  } else {
    texto("nac-rotulo-lula", r.lula.nome || "Lula");
    texto("nac-rotulo-flavio", r.flavio.nome || "Flávio");
    texto("nac-lula", pctCandidato(r.lula, r.lula.votos, r.vv));
    texto("nac-lula-votos", `${fmt.format(r.lula.votos)} votos`);
    texto("nac-flavio", pctCandidato(r.flavio, r.flavio.votos, r.vv));
    texto("nac-flavio-votos", `${fmt.format(r.flavio.votos)} votos`);
    texto("nac-validos", fmt.format(r.vv));
    texto("nac-brancos", fmt.format(r.vb));
    texto("nac-nulos", `${fmt.format(r.vn)} nulos`);
    texto("nac-comparecimento", fmt.format(r.tv));
    const soma = r.lula.votos + r.flavio.votos;
    const barra = document.getElementById("nac-barra-votos");
    if (soma) {
      const esq = (r.lula.votos / soma) * 100;
      barra.innerHTML = `<span class="fatia-clara" style="width:${esq}%"></span><span class="fatia-escura" style="width:${100 - esq}%"></span>`;
      barra.classList.remove("escondido");
      document.getElementById("nac-legenda-votos").classList.remove("escondido");
    } else {
      barra.innerHTML = "";
      barra.classList.add("escondido");
      document.getElementById("nac-legenda-votos").classList.add("escondido");
    }
  }
  texto(
    "nac-atualizado",
    `Última leitura desta página: ${horaLocal(estado.lidoEm)}. Próxima leitura automática: ${horaLocal(estado.lidoEm + INTERVALO_NACIONAL_MS)}.`
  );
  animarBarras(document.getElementById("nac-barra-secoes"));
  animarBarras(document.getElementById("nac-barra-votos"));
}

function pintarCobertura(r) {
  quandoCena((cena) => cena.definirCobertura(r ? r.fracao : 0));
}

function liberarUf() {
  const botao = document.getElementById("ler-uf");
  if (!botao) return;
  const pode = Boolean(estado.uf && estado.nacional && estado.nacional.apurado && !estado.controle);
  botao.disabled = !pode;
  texto(
    "nota-uf",
    estado.nacional && estado.nacional.apurado
      ? "A leitura pede um arquivo do TSE por município desta UF."
      : "A leitura de uma UF inteira só libera quando o arquivo nacional tiver seção totalizada."
  );
}

async function atualizarNacional() {
  if (estado.lendoNacional) return;
  estado.lendoNacional = true;
  if (!estado.nacional) texto("status-nacional", "Consultando o arquivo nacional do TSE.");
  else texto("nac-atualizado", "Lendo o arquivo nacional de novo.");
  try {
    const dados = await lerTse("/tse/br");
    estado.nacional = resumir(dados);
    estado.lidoEm = Date.now();
    pintarNacional(estado.nacional);
    pintarCobertura(estado.nacional);
  } catch (erro) {
    if (!estado.nacional) {
      texto("status-nacional", "Não consegui ler o arquivo nacional do TSE agora. Nenhum total foi preenchido no lugar.");
      pintarNacional(null);
      pintarCobertura(null);
    } else {
      texto("status-nacional", `A leitura nova falhou. Os totais abaixo são os de ${horaLocal(estado.lidoEm)}.`);
    }
    console.error(erro);
  }
  estado.lendoNacional = false;
  liberarUf();
}

function fatia(votos, validos) {
  if (votos == null || !validos) return null;
  return (100 * votos) / validos;
}

function celulaSegundo(cd) {
  const lido = estado.lidos.get(cd);
  if (!lido) return "não lido";
  if (lido.erro) return "sem resposta";
  if (!lido.apurado) return `sem apuração · ${lido.carimbo}`;
  return `${fmt.format(lido.lula.votos)} e ${fmt.format(lido.flavio.votos)} · ${fmt.format(lido.st)}/${fmt.format(lido.ts)} seções`;
}

function desenharTabela() {
  const corpo = document.getElementById("corpo-mun");
  const vazia = document.getElementById("tabela-vazia");
  if (!estado.uf) {
    corpo.innerHTML = "";
    vazia.classList.remove("escondido");
    return;
  }
  const linhas = estado.municipios.filter((m) => m.uf === estado.uf);
  vazia.classList.toggle("escondido", linhas.length > 0);
  corpo.innerHTML = linhas.map((m) => `<tr class="${estado.atual && estado.atual.cd === m.cd ? "linha-ativa" : ""}">
      <td><button type="button" class="link-mun" data-cd="${esc(m.cd)}">${esc(m.nm)}</button></td>
      <td class="num">${m.l == null ? "—" : fmt.format(m.l)}</td>
      <td class="num">${m.f == null ? "—" : fmt.format(m.f)}</td>
      <td class="num">${m.v == null ? "—" : fmt.format(m.v)}</td>
      <td id="vivo-${esc(m.cd)}">${esc(celulaSegundo(m.cd))}</td>
    </tr>`).join("");
}

function pintarFicha(m) {
  const lula = fatia(m.l, m.v);
  const flavio = fatia(m.f, m.v);
  texto("ficha-base", "");
  document.getElementById("ficha-mun").querySelector(".rotulo").textContent = m.uf;
  const base = document.getElementById("ficha-base");
  base.innerHTML = `<h2 class="titulo" style="font-size:2.4rem">${esc(m.nm)}</h2>
    <p class="miudo espaco">Código TSE ${esc(m.cd)}. IBGE ${esc(m.ibge || "—")}.</p>
    <p class="espaco">1º turno de 4 de outubro, base já apurada, sem exterior. Lula ${m.l == null ? "—" : fmt.format(m.l)} (${casas2(lula)}). Flávio ${m.f == null ? "—" : fmt.format(m.f)} (${casas2(flavio)}). Válidos ${m.v == null ? "—" : fmt.format(m.v)}.</p>`;
}

function pintarVivo(m, r) {
  const caixa = document.getElementById("ficha-vivo");
  if (!r.apurado) {
    caixa.innerHTML = `<p class="espaco">2º turno: o TSE publicou este município com zero seções totalizadas. ${esc(fraseSecoes(r))} Os zeros do arquivo não entram como voto.</p>`;
    return;
  }
  const l1 = fatia(m.l, m.v);
  const f1 = fatia(m.f, m.v);
  const l2 = r.vv ? (100 * r.lula.votos) / r.vv : null;
  const f2 = r.vv ? (100 * r.flavio.votos) / r.vv : null;
  const delta = (a, b) => {
    const ca = centesimos(a);
    const cb = centesimos(b);
    if (ca == null || cb == null) return "—";
    const d = ca - cb;
    const texto = casas2(d / 100).replace("%", "");
    return (d > 0 ? "+" : "") + texto;
  };
  caixa.innerHTML = `<p class="espaco">2º turno ao vivo. ${esc(fraseSecoes(r))}</p>
    <p class="grande num espaco">${esc(r.lula.nome)} ${fmt.format(r.lula.votos)} <span class="miudo">(${pctCandidato(r.lula, r.lula.votos, r.vv)})</span></p>
    <p class="grande num">${esc(r.flavio.nome)} ${fmt.format(r.flavio.votos)} <span class="miudo">(${pctCandidato(r.flavio, r.flavio.votos, r.vv)})</span></p>
    <p class="espaco">Válidos ${fmt.format(r.vv)}. Brancos ${fmt.format(r.vb)}. Nulos ${fmt.format(r.vn)}. Comparecimento ${fmt.format(r.tv)}.</p>
    <p class="miudo">Diferença em pontos contra o 1º turno deste município: Lula ${delta(r.lula.percentual ?? l2, l1)}, Flávio ${delta(r.flavio.percentual ?? f2, f1)}.</p>`;
}

async function abrirMunicipio(cd) {
  const m = estado.porCd.get(cd);
  if (!m) return;
  estado.atual = m;
  if (estado.uf !== m.uf) {
    estado.uf = m.uf;
    document.getElementById("filtro-uf").value = m.uf;
  }
  pintarFicha(m);
  desenharTabela();
  document.getElementById("ficha-vivo").innerHTML = `<p class="espaco">Lendo o arquivo deste município no TSE.</p>`;
  try {
    const dados = await lerTse(`/tse/mun/${m.uf.toLowerCase()}/${m.cd}`);
    const r = resumir(dados);
    estado.lidos.set(m.cd, r);
    pintarVivo(m, r);
    const celula = document.getElementById(`vivo-${m.cd}`);
    if (celula) celula.textContent = celulaSegundo(m.cd);
  } catch (erro) {
    estado.lidos.set(m.cd, { erro: true });
    document.getElementById("ficha-vivo").innerHTML = `<p class="espaco">Não consegui ler o arquivo deste município no TSE.</p>`;
    console.error(erro);
  }
}

async function aoMudarUf() {
  estado.uf = document.getElementById("filtro-uf").value;
  desenharTabela();
  liberarUf();
  if (!estado.uf) {
    texto("status-uf", "");
    return;
  }
  const n = estado.municipios.filter((m) => m.uf === estado.uf).length;
  texto("status-uf", `Lendo o arquivo de ${estado.uf} no TSE. A UF tem ${fmt.format(n)} municípios na base.`);
  try {
    const dados = await lerTse(`/tse/uf/${estado.uf.toLowerCase()}`);
    const r = resumir(dados);
    texto("status-uf", `${estado.uf}. ${fraseSecoes(r)}${fraseVotos(r)}`);
  } catch (erro) {
    texto("status-uf", `Não consegui ler o arquivo de ${estado.uf} no TSE.`);
    console.error(erro);
  }
}

async function lerUfInteira() {
  if (!estado.uf || !estado.nacional || !estado.nacional.apurado) return;
  if (estado.controle) estado.controle.abort();
  const controle = new AbortController();
  estado.controle = controle;
  document.getElementById("parar-uf").classList.remove("escondido");
  document.getElementById("ler-uf").disabled = true;
  const lista = estado.municipios.filter((m) => m.uf === estado.uf);
  let i = 0;
  try {
    for (const m of lista) {
      if (controle.signal.aborted) break;
      i += 1;
      texto("progresso", `Lendo ${fmt.format(i)} de ${fmt.format(lista.length)}: ${m.nm}`);
      try {
        const dados = await lerTse(`/tse/mun/${m.uf.toLowerCase()}/${m.cd}`, controle.signal);
        estado.lidos.set(m.cd, resumir(dados));
        const celula = document.getElementById(`vivo-${m.cd}`);
        if (celula) celula.textContent = celulaSegundo(m.cd);
      } catch (erro) {
        if (erro.name === "AbortError") break;
        estado.lidos.set(m.cd, { erro: true });
        const celula = document.getElementById(`vivo-${m.cd}`);
        if (celula) celula.textContent = "sem resposta";
      }
      await esperar(150, controle.signal);
    }
  } catch (erro) {
    if (erro.name !== "AbortError") console.error(erro);
  }
  estado.controle = null;
  document.getElementById("parar-uf").classList.add("escondido");
  texto("progresso", controle.signal.aborted ? "Leitura interrompida." : "Leitura da UF encerrada.");
  liberarUf();
}

function prepararBusca() {
  const busca = document.getElementById("busca-mun");
  const lista = document.getElementById("busca-resultado");
  busca.addEventListener("input", () => {
    const q = semAcento(busca.value.trim());
    if (q.length < 2) {
      lista.innerHTML = "";
      return;
    }
    const achados = estado.municipios
      .filter((m) => semAcento(`${m.nm} ${m.uf}`).includes(q))
      .slice(0, 12);
    lista.innerHTML = achados.map((m) =>
      `<li><button type="button" class="busca-item" data-cd="${esc(m.cd)}">${esc(m.nm)} · ${esc(m.uf)}</button></li>`
    ).join("");
  });
  lista.addEventListener("click", (ev) => {
    const botao = ev.target.closest("button");
    if (!botao) return;
    lista.innerHTML = "";
    busca.value = "";
    abrirMunicipio(botao.dataset.cd);
  });
}

async function carregar() {
  document.getElementById("filtro-uf").innerHTML = `<option value="">Escolha</option>` +
    UFS.map((uf) => `<option value="${uf}">${uf}</option>`).join("");
  document.getElementById("filtro-uf").addEventListener("change", aoMudarUf);
  document.getElementById("atualizar-br").addEventListener("click", atualizarNacional);
  document.getElementById("ler-uf").addEventListener("click", lerUfInteira);
  document.getElementById("parar-uf").addEventListener("click", () => {
    if (estado.controle) estado.controle.abort();
  });
  document.getElementById("corpo-mun").addEventListener("click", (ev) => {
    const botao = ev.target.closest("button");
    if (!botao) return;
    abrirMunicipio(botao.dataset.cd);
  });
  prepararBusca();
  try {
    const [municipios, resumo] = await Promise.all([
      lerJson("dados/municipios.json"),
      lerJson("dados/resumo.json").catch(() => null),
    ]);
    estado.municipios = municipios;
    estado.porCd = new Map(municipios.map((m) => [m.cd, m]));
    if (resumo && resumo.segundo_turno) {
      texto(
        "carimbo-pipeline",
        "Último carimbo gravado pelo pipeline, que pode estar atrasado: " + resumo.segundo_turno.carimbo_tse + "."
      );
    }
  } catch (erro) {
    falhaDados("status-nacional");
    console.error(erro);
    return;
  }
  await atualizarNacional();
  agendarNacional();
}

function agendarNacional() {
  setInterval(() => {
    if (!document.hidden) atualizarNacional();
  }, INTERVALO_NACIONAL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden || !estado.lidoEm) return;
    if (Date.now() - estado.lidoEm >= INTERVALO_NACIONAL_MS) atualizarNacional();
  });
}

async function iniciarSoNacional() {
  const botao = document.getElementById("atualizar-br");
  if (botao) botao.addEventListener("click", atualizarNacional);
  try {
    const resumo = await lerJson("dados/resumo.json");
    if (resumo && resumo.segundo_turno && document.getElementById("carimbo-pipeline")) {
      texto(
        "carimbo-pipeline",
        "Último carimbo gravado pelo pipeline, que pode estar atrasado: " + resumo.segundo_turno.carimbo_tse + "."
      );
    }
  } catch (erro) {
    console.error(erro);
  }
  await atualizarNacional();
  agendarNacional();
}

if (document.getElementById("filtro-uf")) carregar();
else if (document.getElementById("nac-secoes")) iniciarSoNacional();
