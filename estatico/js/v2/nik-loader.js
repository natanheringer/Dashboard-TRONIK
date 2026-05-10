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
    container.innerHTML =
      '<div class="nik-loading">' +
      '<span class="nik-loading-dot"></span>' +
      '<span class="nik-loading-dot"></span>' +
      '<span class="nik-loading-dot"></span>' +
      '</div>';
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

  function streamText(el, text, speedMs, onDone) {
    var i = 0;
    var cursor = document.createElement("span");
    cursor.className = "nik-stream-cursor";
    cursor.setAttribute("aria-hidden", "true");
    el.appendChild(cursor);
    function step() {
      if (i <= text.length) {
        el.firstChild.nodeValue = text.slice(0, i);
        i++;
        setTimeout(step, speedMs);
        return;
      }
      if (cursor.parentNode) cursor.parentNode.removeChild(cursor);
      if (onDone) onDone();
    }
    el.insertBefore(document.createTextNode(""), cursor);
    step();
  }

  function renderizarBlocoLanding(container, tipo, bloco) {
    var titulo = "";
    var corpo = "";
    var extra = "";

    if (tipo === "fala_nik") {
      titulo = esc(bloco.titulo);
      corpo = bloco.corpo || "";
      extra = bloco.destaque ? '<p class="nik-card-subtle">' + esc(bloco.destaque) + "</p>" : "";
    } else if (tipo === "fato_reciclagem") {
      titulo = "Fato rápido";
      corpo = bloco.fato || "";
      extra = bloco.fonte ? "<cite>" + esc(bloco.fonte) + "</cite>" : "";
    } else if (tipo === "impacto_tronik") {
      titulo = esc(bloco.titulo);
      corpo = bloco.explicacao || "";
      extra = bloco.metrica ? '<div class="nik-metric">' + esc(bloco.metrica) + "</div>" : "";
    } else if (tipo === "pergunta_guiada") {
      titulo = esc(bloco.pergunta);
      corpo = bloco.resposta_curta || "";
    } else if (tipo === "nik_explica") {
      titulo = esc(bloco.titulo);
      corpo = bloco.corpo || "";
      extra = bloco.analogia ? '<p class="nik-card-subtle">' + esc(bloco.analogia) + "</p>" : "";
    }

    var bodyId = "nik-stream-body-" + tipo;
    var isFato = tipo === "fato_reciclagem";
    var bodyTag = isFato ? "blockquote" : "p";

    container.innerHTML =
      '<section class="nik-card nik-card-landing nik-chat-assistant nik-card-' + esc(tipo) + ' is-streaming">' +
      "<h3>" + titulo + "</h3>" +
      (tipo === "impacto_tronik" && extra ? extra : "") +
      "<" + bodyTag + ' id="' + bodyId + '" class="nik-stream-body"></' + bodyTag + ">" +
      '<span class="nik-card-extra-slot"></span>' +
      "</section>";

    var bodyEl = document.getElementById(bodyId);
    if (!bodyEl) return;

    streamText(bodyEl, corpo, 14, function () {
      var card = container.querySelector(".nik-card");
      if (card) card.classList.remove("is-streaming");
      var slot = container.querySelector(".nik-card-extra-slot");
      if (slot && extra && tipo !== "impacto_tronik") slot.outerHTML = extra;
    });
  }

  window.NikLoader = {
    carregarNikOps: carregarNikOps,
    carregarNikLanding: carregarNikLanding
  };
})();
