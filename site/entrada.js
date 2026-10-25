(function () {
  var titulo = "";
  try {
    titulo = sessionStorage.getItem("derossi-transicao") || "";
  } catch (erro) {
    return;
  }
  if (!titulo) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    try { sessionStorage.removeItem("derossi-transicao"); } catch (erro) {}
    return;
  }
  var seguro = String(titulo).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
  document.write(
    '<div class="cortina ativa cobre" aria-hidden="true">' +
      '<div class="cortina-faixa b"></div>' +
      '<div class="cortina-faixa"></div>' +
      '<p class="cortina-titulo">' + seguro + "</p>" +
    "</div>"
  );
  window.setTimeout(function () {
    var cortina = document.querySelector(".cortina");
    if (!cortina || cortina.dataset.saindo === "1") return;
    cortina.classList.remove("ativa", "cobre");
    try { sessionStorage.removeItem("derossi-transicao"); } catch (erro) {}
  }, 2500);
})();
