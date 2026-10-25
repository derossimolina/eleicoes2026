const estado = { camada: "26", selecionado: null, camadaGeo: null, revelado: false };

const LEGENDA = {
  "26": "Vermelho: Lula. Azul: Flávio. 1º turno de 2026.",
  "22": "Vermelho: Lula. Azul: Bolsonaro. 2º turno de 2022.",
  "18": "Vermelho: Haddad. Azul: Bolsonaro. 2º turno de 2018.",
};

function tom(fatiaDireita) {
  const t = Math.min(1, Math.max(0, fatiaDireita));
  const vermelho = [210, 33, 33];
  const branco = [255, 255, 255];
  const azul = [31, 78, 174];
  const misturar = (a, b, u) => a.map((v, i) => Math.round(v + (b[i] - v) * u));
  const cor = t < 0.5 ? misturar(vermelho, branco, t / 0.5) : misturar(branco, azul, (t - 0.5) / 0.5);
  return `rgb(${cor[0]}, ${cor[1]}, ${cor[2]})`;
}

function parDaCamada(p) {
  if (estado.camada === "26") return [p.pl26, p.pf26];
  if (estado.camada === "22") return [p.pl22, p.pb22];
  return [p.ph18, p.pb18];
}

function corDe(p) {
  const [esq, dir] = parDaCamada(p);
  if (esq == null || dir == null) return "#ffffff";
  const soma = esq + dir;
  if (!soma) return "#ffffff";
  return tom(dir / soma);
}

function estilo(feature) {
  const ativo = estado.selecionado && feature.properties.ibge === estado.selecionado;
  return {
    color: ativo ? "#1a1024" : "rgba(26,16,36,0.4)",
    weight: ativo ? 2 : 0.4,
    fillColor: corDe(feature.properties),
    fillOpacity: estado.revelado ? 1 : 0,
  };
}

function pintarCamada() {
  if (!estado.camadaGeo) return;
  estado.camadaGeo.eachLayer((layer) => {
    const s = estilo(layer.feature);
    layer.options.fillColor = s.fillColor;
    layer.options.fillOpacity = s.fillOpacity;
    layer.options.color = s.color;
    layer.options.weight = s.weight;
    const el = layer.getElement();
    if (!el) return;
    el.style.fill = s.fillColor;
    el.style.fillOpacity = String(s.fillOpacity);
    el.style.stroke = s.color;
    el.style.strokeWidth = s.weight + "px";
  });
}

function revelarMapa() {
  if (prefereMenosMovimento) {
    estado.revelado = true;
    pintarCamada();
    return;
  }
  estado.revelado = false;
  pintarCamada();
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      estado.revelado = true;
      pintarCamada();
    });
  });
}

function bloco(titulo, a, b, va, vb, validos, nomeA, nomeB) {
  return `<h3 class="rotulo espaco">${titulo}</h3>
    <p class="espaco">${nomeA} ${pct1(a)} <span class="num">${va == null ? "" : "· " + fmt.format(va)}</span></p>
    <p>${nomeB} ${pct1(b)} <span class="num">${vb == null ? "" : "· " + fmt.format(vb)}</span></p>
    <p class="miudo">Válidos ${validos == null ? "—" : fmt.format(validos)}</p>`;
}

function fichaDe(p) {
  const ficha = document.getElementById("ficha");
  ficha.classList.remove("ficha-entra");
  ficha.innerHTML = `
    <p class="rotulo">${p.uf || "Malha"}</p>
    <h2 class="titulo" style="font-size:2.2rem">${esc(p.nm)}</h2>
    ${p.v26 == null ? "<p class='espaco'>Sem voto de presidente neste polígono.</p>" : ""}
    ${bloco("2026, 1º turno", p.pl26, p.pf26, p.l26, p.f26, p.v26, "Lula", "Flávio")}
    ${bloco("2022, 2º turno", p.pl22, p.pb22, p.l22, p.b22, p.v22, "Lula", "Bolsonaro")}
    ${bloco("2018, 2º turno", p.ph18, p.pb18, p.h18, p.b18, p.v18, "Haddad", "Bolsonaro")}
    <p class="miudo espaco">IBGE ${p.ibge}. <a href="index.html">Apuração ao vivo do 2º turno</a></p>`;
  if (!prefereMenosMovimento) {
    void ficha.offsetWidth;
    ficha.classList.add("ficha-entra");
  }
}

function selecionar(ibge, voar) {
  estado.selecionado = ibge;
  const layer = estado.indice.get(ibge);
  if (!layer) return;
  pintarCamada();
  fichaDe(layer.feature.properties);
  if (voar) estado.camadaGeo._map.fitBounds(layer.getBounds(), { maxZoom: 8 });
}

function montarMapa(geo) {
  const mapa = L.map("mapa-folha", { scrollWheelZoom: true }).setView([-14.2, -51.9], 4);
  const indice = new Map();
  estado.camadaGeo = L.geoJSON(geo, {
    style: estilo,
    onEachFeature(feature, layer) {
      indice.set(feature.properties.ibge, layer);
      layer.on("click", () => selecionar(feature.properties.ibge));
    },
  }).addTo(mapa);
  estado.indice = indice;
  revelarMapa();
  document.querySelectorAll(".camada").forEach((botao) => {
    botao.addEventListener("click", () => {
      estado.camada = botao.dataset.camada;
      document.querySelectorAll(".camada").forEach((b) => {
        b.setAttribute("aria-pressed", b === botao ? "true" : "false");
      });
      texto("legenda-texto", LEGENDA[estado.camada]);
      pintarCamada();
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
    const achados = geo.features
      .filter((f) => semAcento(`${f.properties.nm} ${f.properties.uf || ""}`).includes(q))
      .slice(0, 8);
    lista.innerHTML = achados.map((f) =>
      `<li><button type="button" data-ibge="${esc(f.properties.ibge)}" class="busca-item">${esc(f.properties.nm)}${f.properties.uf ? " · " + esc(f.properties.uf) : ""}</button></li>`
    ).join("");
  });
  lista.addEventListener("click", (ev) => {
    const botao = ev.target.closest("button");
    if (!botao) return;
    selecionar(botao.dataset.ibge, true);
    lista.innerHTML = "";
    busca.value = "";
  });
}

async function carregar() {
  try {
    const geo = await lerJson("dados/municipios.geojson");
    montarMapa(geo);
  } catch (erro) {
    falhaDados("ficha");
    console.error(erro);
  }
}

carregar();
