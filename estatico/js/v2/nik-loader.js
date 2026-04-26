(function () {
  "use strict";

  var NIK_API = "/api/nik";

  function esc(value) {
    if (value === null || value === undefined) return "";
    var div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
  }

  async function carregarNikOps(endpoint, containerId, opts) {
    var container = document.getElementById(containerId);
    if (!container) return;

    opts = opts || {};
    if (opts.showLoader !== false) {
      container.innerHTML = '<div class="nik-loading">Nik analisando o contexto...</div>';
    }

    try {
      var resp = await fetch(NIK_API + endpoint, { credentials: "same-origin" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      var texto = data.texto || opts.fallbackText || "";
      if (!texto) {
        container.innerHTML = "";
        return;
      }
      container.innerHTML =
        '<section class="nik-card nik-card-ops nik-chat-assistant">' +
        '<div class="nik-card-head">' +
        '<span class="nik-badge">Nik</span>' +
        (data.fonte === "fallback" || data.fonte === "desabilitada"
          ? '<span class="nik-status">dados de exemplo</span>'
          : "") +
        "</div>" +
        '<p class="nik-card-text">' + esc(texto) + "</p>" +
        "</section>";
    } catch (err) {
      if (opts.fallbackText) {
        container.innerHTML =
          '<section class="nik-card nik-card-ops nik-chat-assistant">' +
          '<div class="nik-card-head"><span class="nik-badge">Nik</span></div>' +
          '<p class="nik-card-text">' + esc(opts.fallbackText) + "</p>" +
          "</section>";
      } else {
        container.innerHTML = "";
      }
    }
  }

  async function carregarNikLanding(tipoBloco, containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '<div class="nik-loading">Nik preparando...</div>';
    try {
      var resp = await fetch(NIK_API + "/landing/" + tipoBloco, { credentials: "same-origin" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      if (!data.bloco) {
        container.innerHTML = "";
        return;
      }
      renderizarBlocoLanding(container, tipoBloco, data.bloco);
    } catch (err) {
      container.innerHTML = "";
    }
  }

  function renderizarBlocoLanding(container, tipo, bloco) {
    var html = "";
    if (tipo === "fala_nik") {
      html = "<h3>" + esc(bloco.titulo) + "</h3><p>" + esc(bloco.corpo) + "</p>" +
        (bloco.destaque ? '<p class="nik-card-subtle">' + esc(bloco.destaque) + "</p>" : "");
    } else if (tipo === "fato_reciclagem") {
      html = '<h3>Fato rápido</h3><blockquote>' + esc(bloco.fato) + "</blockquote>" +
        (bloco.fonte ? "<cite>" + esc(bloco.fonte) + "</cite>" : "");
    } else if (tipo === "impacto_tronik") {
      html = "<h3>" + esc(bloco.titulo) + '</h3><div class="nik-metric">' + esc(bloco.metrica) +
        "</div><p>" + esc(bloco.explicacao || "") + "</p>";
    } else if (tipo === "pergunta_guiada") {
      html = "<h3>" + esc(bloco.pergunta) + "</h3><p>" + esc(bloco.resposta_curta) + "</p>";
    } else if (tipo === "nik_explica") {
      html = "<h3>" + esc(bloco.titulo) + "</h3><p>" + esc(bloco.corpo) + "</p>" +
        (bloco.analogia ? '<p class="nik-card-subtle">' + esc(bloco.analogia) + "</p>" : "");
    }

    container.innerHTML =
      '<section class="nik-card nik-card-landing nik-chat-assistant nik-card-' + esc(tipo) + '">' +
      html +
      "</section>";
  }

  window.NikLoader = {
    carregarNikOps: carregarNikOps,
    carregarNikLanding: carregarNikLanding
  };
})();
