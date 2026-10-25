async function carregar() {
  try {
    const pred = await lerJson("dados/prediction.json");
    pintar(pred);
  } catch (erro) {
    falhaDados("metodo-numeros");
    console.error(erro);
  }
}

function casas(n) {
  return Number(n).toLocaleString("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 6 });
}

function pintar(pred) {
  const [a, b] = pred.intervalo_95_flavio_tau_2pp;
  texto(
    "metodo-numeros",
    `Média ponderada de Flávio ${pct(pred.media_ponderada_flavio_pct)} e de Lula ${pct(pred.media_ponderada_lula_pct)}. ` +
    `Desvio amostral da média ${casas(pred.sigma_amostral)}. Com erro de eleição de 2 pontos, o desvio total é ${casas(pred.sigma_total_tau_2pp)}. ` +
    `Intervalo de 95% para Flávio: ${pct1(a * 100)} a ${pct1(b * 100)}. ` +
    `${pred.n_pesquisas_na_media} pesquisas. Referência ${pred.data_referencia}.`
  );
  const fora = (pred.excluidas || []).map((e) => `${e.instituto}: ${e.observacao || e.motivo}`).join(" ");
  texto("metodo-exclusoes", fora ? "Ficaram de fora da média. " + fora : "");
  const linhas = pred.pesquisas.map((p) => `<tr>
      <td>${esc(p.instituto)}</td>
      <td>${esc(p.data_inicio)} a ${esc(p.data_fim)}</td>
      <td class="num">${fmt.format(p.n)}</td>
      <td class="num">${String(p.margem_erro_pp).replace(".", ",")}</td>
      <td class="num">${pct(p.flavio_validos)}</td>
      <td class="num">${pct(p.lula_validos)}</td>
      <td class="num">${Math.round(p.peso_relativo * 1000) / 10}%</td>
      <td><a href="${esc(p.url_fonte)}">fonte</a></td>
    </tr>`).join("");
  document.getElementById("tabela-metodo").innerHTML = `<table class="tabela">
    <thead><tr>
      <th>Instituto</th><th>Campo</th><th class="num">Amostra</th>
      <th class="num">Margem</th><th class="num">Flávio</th><th class="num">Lula</th>
      <th class="num">Peso</th><th>Fonte</th>
    </tr></thead><tbody>${linhas}</tbody></table>`;
}

carregar();
