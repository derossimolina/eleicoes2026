function quandoCena(fn) {
  if (window.__cena) fn(window.__cena);
  else window.addEventListener("cena-pronta", () => fn(window.__cena), { once: true });
}

async function carregar() {
  try {
    const [resumo, pred] = await Promise.all([
      lerJson("dados/resumo.json"),
      lerJson("dados/prediction.json"),
    ]);
    pintarInicio(resumo, pred);
    pintarPesquisas(pred);
    quandoCena((cena) => cena.definirPesos(pred.media_ponderada_flavio, pred.media_ponderada_lula));
  } catch (erro) {
    falhaDados("aviso-pred");
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
  texto(
    "sensibilidade",
    "Se o erro for 1,5 ponto, a chance de Flávio vai a " + Math.round(s["tau_1.5pp"] * 100) +
    "%. Com 3 pontos, fica em " + Math.round(s["tau_3.0pp"] * 100) + "%."
  );
  const t1 = resumo.primeiro_turno_2026;
  texto("t1-flavio", pct(t1.pct_flavio));
  texto("t1-lula", pct(t1.pct_lula));
  texto("t1-flavio-votos", fmt.format(t1.votos_flavio) + " votos");
  texto("t1-lula-votos", fmt.format(t1.votos_lula) + " votos");
  texto("t1-validos", fmt.format(t1.votos_validos));
  texto("t1-mun", fmt.format(t1.municipios) + " municípios, sem exterior");
  const caixa = document.getElementById("barras-uf");
  const ordenadas = [...resumo.ufs].sort((x, y) => (y.pct_flavio - y.pct_lula) - (x.pct_flavio - x.pct_lula));
  caixa.innerHTML = ordenadas.map((u) => {
    const total = u.pct_flavio + u.pct_lula || 1;
    const esq = (u.pct_lula / total) * 100;
    const margem = u.pct_flavio - u.pct_lula;
    const sinal = margem > 0 ? "+" : "";
    return `<div class="uf-linha">
      <span>${u.uf}</span>
      <div class="barra" title="Lula ${pct(u.pct_lula)} · Flávio ${pct(u.pct_flavio)}">
        <span class="fatia-lula" style="width:${esq}%"></span>
        <span class="fatia-flavio" style="width:${100 - esq}%"></span>
      </div>
      <span class="num">${sinal}${margem.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</span>
    </div>`;
  }).join("");
  animarBarras(caixa);
}

function dia(iso) {
  const partes = String(iso || "").split("-");
  if (partes.length < 3) return iso || "";
  return partes[2] + "/" + partes[1];
}

function pintarPesquisas(pred) {
  const lista = document.getElementById("lista-pesquisas");
  lista.innerHTML = pred.pesquisas.map((p) => {
    const soma = p.flavio_validos + p.lula_validos || 1;
    const esq = (p.lula_validos / soma) * 100;
    return `<article class="pesquisa">
      <div>
        <p>${p.instituto}</p>
        <p class="miudo">${dia(p.data_inicio)}–${dia(p.data_fim)} · n=${fmt.format(p.n)}</p>
      </div>
      <div>
        <div class="barra">
          <span class="fatia-lula" style="width:${esq}%"></span>
          <span class="fatia-flavio" style="width:${100 - esq}%"></span>
        </div>
        <p class="miudo num">Lula ${pct(p.lula_validos)} · Flávio ${pct(p.flavio_validos)}</p>
      </div>
      <p class="num">peso ${Math.round(p.peso_relativo * 1000) / 10}%</p>
    </article>`;
  }).join("");
  animarBarras(lista);
}

carregar();
