const POR_PAGINA = 40;
const estado = { pagina: 0, deputados: [], filtrados: [] };

async function carregar() {
  try {
    const [resumo, deputados] = await Promise.all([
      lerJson("dados/resumo.json"),
      lerJson("dados/deputados.json"),
    ]);
    estado.deputados = deputados;
    preparar(resumo);
  } catch (erro) {
    falhaDados("dep-resumo");
    console.error(erro);
  }
}

function preparar(resumo) {
  const nota = resumo.deputado.nota_cadeira ? " " + resumo.deputado.nota_cadeira : "";
  texto(
    "dep-resumo",
    `${fmt.format(resumo.deputado.candidaturas)} deferidos, ${fmt.format(resumo.deputado.eleitos)} eleitos na base, ${fmt.format(resumo.deputado.votos_nominais)} votos nominais.${nota}`
  );
  const ufs = [...new Set(estado.deputados.map((d) => d.sg_uf))].sort();
  const partidos = [...new Set(estado.deputados.map((d) => d.sg_partido))].sort();
  document.getElementById("filtro-uf").innerHTML = `<option value="">Todas</option>` + ufs.map((u) => `<option>${u}</option>`).join("");
  document.getElementById("filtro-partido").innerHTML = `<option value="">Todos</option>` + partidos.map((p) => `<option>${p}</option>`).join("");
  ["filtro-nome", "filtro-uf", "filtro-partido", "filtro-eleito"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      estado.pagina = 0;
      desenhar();
    });
  });
  document.getElementById("pag-antes").addEventListener("click", () => { estado.pagina -= 1; desenhar(); });
  document.getElementById("pag-depois").addEventListener("click", () => { estado.pagina += 1; desenhar(); });
  document.getElementById("baixar-csv").addEventListener("click", baixarCsv);
  desenhar();
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

function desenhar() {
  estado.filtrados = filtrar();
  const total = estado.filtrados.length;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  estado.pagina = Math.min(Math.max(estado.pagina, 0), paginas - 1);
  const ini = estado.pagina * POR_PAGINA;
  const fatia = estado.filtrados.slice(ini, ini + POR_PAGINA);
  document.getElementById("corpo-dep").innerHTML = fatia.map((d) => `<tr>
    <td>${esc(d.nm_urna)}</td>
    <td>${esc(d.sg_uf)}</td>
    <td>${esc(d.sg_partido)}</td>
    <td class="num">${fmt.format(d.votos_nominais)}</td>
    <td>${d.eleito ? "Sim" : "Não"}</td>
    <td>${d.superou_quociente ? "Superou" : "Não"}</td>
    <td>${d.experiencia_previa ? "Sim" : "Não"}</td>
  </tr>`).join("");
  document.getElementById("dep-vazio").classList.toggle("escondido", total !== 0);
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
