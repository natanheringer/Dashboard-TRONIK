/**
 * Preview v2 — fila de prospecção REE
 * GET /api/prospeccao/candidatos
 */
(function () {
  "use strict";

  var API_URL = "/api/prospeccao/candidatos";
  var TOP_MOTIVOS = 3;

  function $(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function prioridadeBadge(prioridade) {
    var p = (prioridade || "media").toLowerCase();
    var cls = "neutral";
    if (p === "alta") cls = "crit";
    else if (p === "media") cls = "warn";
    var label = p.charAt(0).toUpperCase() + p.slice(1);
    return '<span class="badge ' + cls + '">' + esc(label) + "</span>";
  }

  function formatScore(score) {
    if (score == null || Number.isNaN(Number(score))) return "—";
    return Number(score).toFixed(4);
  }

  function topMotivos(motivos) {
    if (!Array.isArray(motivos) || !motivos.length) {
      return '<span class="prosp-empty" style="padding:0;">—</span>';
    }
    var items = motivos.slice(0, TOP_MOTIVOS).map(function (m) {
      var texto = typeof m === "string" ? m : (m.reason || m.feature || "");
      return "<li>" + esc(texto) + "</li>";
    });
    return '<ul class="prosp-motivos">' + items.join("") + "</ul>";
  }

  function mapLink(local) {
    if (!local) return "—";
    var lat = local.latitude;
    var lon = local.longitude;
    if (lat == null || lon == null) return "—";
    var url =
      "https://www.openstreetmap.org/?mlat=" +
      encodeURIComponent(lat) +
      "&mlon=" +
      encodeURIComponent(lon) +
      "#map=17/" +
      encodeURIComponent(lat) +
      "/" +
      encodeURIComponent(lon);
    return (
      '<a class="prosp-map-link" href="' +
      esc(url) +
      '" target="_blank" rel="noopener noreferrer">Ver mapa</a>'
    );
  }

  function empresaCell(item) {
    var empresa = item.empresa || {};
    var nome = empresa.razao_social || empresa.nome_fantasia || "—";
    var sub = [];
    if (empresa.cnpj) sub.push(empresa.cnpj);
    if (empresa.bairro) sub.push(empresa.bairro);
    var subHtml = sub.length ? "<span>" + esc(sub.join(" · ")) + "</span>" : "";
    return (
      '<div class="prosp-empresa"><strong>' +
      esc(nome) +
      "</strong>" +
      subHtml +
      "</div>"
    );
  }

  function scoreCell(item) {
    var pct =
      item.score_percentil != null
        ? '<span class="prosp-score-pct">P' + esc(String(item.score_percentil)) + "</span>"
        : "";
    return (
      '<span class="prosp-score">' +
      esc(formatScore(item.score)) +
      "</span>" +
      pct
    );
  }

  function setLoading(loading) {
    var spin = $("prosp-spin");
    if (spin) spin.style.display = loading ? "block" : "none";
  }

  function renderRows(candidatos) {
    var tbody = $("prosp-tbody");
    if (!tbody) return;

    if (!candidatos.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="prosp-empty">Nenhum candidato na fila com os filtros atuais.</td></tr>';
      return;
    }

    tbody.innerHTML = candidatos
      .map(function (item) {
        return (
          "<tr>" +
          "<td>" +
          empresaCell(item) +
          "</td>" +
          "<td>" +
          scoreCell(item) +
          "</td>" +
          "<td>" +
          prioridadeBadge(item.prioridade) +
          "</td>" +
          '<td class="prosp-qid">' +
          esc(item.qid || "—") +
          "</td>" +
          "<td>" +
          topMotivos(item.motivos) +
          "</td>" +
          "<td>" +
          mapLink(item.local) +
          "</td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function updateMeta(candidatos) {
    var countEl = $("prosp-count");
    var heroEl = $("prosp-hero-text");
    var updatedEl = $("prosp-updated");
    var n = candidatos.length;

    if (countEl) {
      countEl.textContent =
        n === 1 ? "1 candidato na fila" : n + " candidatos na fila";
    }

    if (heroEl) {
      if (!n) {
        heroEl.textContent =
          "Nenhum candidato publicado ainda. Execute o pipeline de scoring ou ajuste os filtros.";
      } else {
        var alta = candidatos.filter(function (c) {
          return (c.prioridade || "").toLowerCase() === "alta";
        }).length;
        heroEl.innerHTML =
          "Exibindo <strong>" +
          n +
          "</strong> candidato(s)" +
          (alta ? ", sendo <strong>" + alta + "</strong> com prioridade alta." : ".");
      }
    }

    if (updatedEl) {
      var now = new Date();
      updatedEl.textContent =
        "Atualizado às " +
        now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    }
  }

  function buildQuery() {
    var form = $("form-prosp-filtros");
    if (!form) return "";
    var params = new URLSearchParams(new FormData(form));
    var prioridade = params.get("prioridade");
    if (!prioridade) params.delete("prioridade");
    return params.toString();
  }

  async function carregarFila() {
    setLoading(true);
    var tbody = $("prosp-tbody");
    if (tbody) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="prosp-empty">Carregando…</td></tr>';
    }

    try {
      var qs = buildQuery();
      var url = API_URL + (qs ? "?" + qs : "");
      var resp = await fetch(url, { credentials: "same-origin" });
      var body = await resp.json();

      if (!resp.ok || !body.ok) {
        var msg =
          (body.erros && body.erros[0] && body.erros[0].mensagem) ||
          "Não foi possível carregar a fila.";
        throw new Error(msg);
      }

      var candidatos = body.dados || [];
      renderRows(candidatos);
      updateMeta(candidatos);
    } catch (err) {
      if (tbody) {
        tbody.innerHTML =
          '<tr><td colspan="6" class="prosp-empty">' +
          esc(err.message || "Erro ao carregar candidatos.") +
          "</td></tr>";
      }
      if (window.previewToast) {
        window.previewToast(err.message || "Erro ao carregar prospecção.", "warn");
      }
    } finally {
      setLoading(false);
    }
  }

  function setBootstrapBanner(visible) {
    var banner = $("prosp-bootstrap-banner");
    if (!banner) return;
    banner.classList.toggle("is-visible", !!visible);
  }

  function algoritmoLabel(algoritmo) {
    if (algoritmo === "xgboost_ranker") return "XGBoost ranker";
    if (algoritmo === "heuristic_bootstrap") return "Heurístico (bootstrap)";
    return algoritmo || "—";
  }

  function renderAlgoritmoBadge(algoritmo) {
    var badge = $("prosp-algoritmo-badge");
    var subtitle = $("prosp-subtitle");
    if (!badge) return;
    if (!algoritmo) {
      badge.hidden = true;
      if (subtitle) subtitle.textContent = "Fila ranqueada de candidatos · sem modelo ativo";
      return;
    }
    var isBootstrap = algoritmo === "heuristic_bootstrap";
    badge.hidden = false;
    badge.textContent = algoritmoLabel(algoritmo);
    badge.className =
      "ml-tag prosp-algo-badge " +
      (isBootstrap ? "prosp-algo-badge--heuristic" : "prosp-algo-badge--xgb");
    if (subtitle) {
      subtitle.textContent = isBootstrap
        ? "Fila ranqueada por regras heurísticas (bootstrap) até treino listwise"
        : "Fila ranqueada por modelo XGBoost listwise treinado";
    }
  }

  async function carregarModelo() {
    var el = $("prosp-modelo");
    try {
      var resp = await fetch("/api/prospeccao/modelo-ativo", {
        credentials: "same-origin",
      });
      var body = await resp.json();
      if (!resp.ok || !body.ok || !body.dados) {
        if (el) {
          el.textContent = "Sem modelo ativo";
          el.classList.remove("prosp-modelo--warn");
        }
        renderAlgoritmoBadge("");
        setBootstrapBanner(false);
        return;
      }
      var d = body.dados;
      var m = d.metricas || {};
      var ndcg = m.validation_ndcg_mean;
      var algoritmo = d.algoritmo || "";
      var isBootstrap = algoritmo === "heuristic_bootstrap";
      renderAlgoritmoBadge(algoritmo);
      setBootstrapBanner(isBootstrap);
      if (el) {
        el.classList.toggle("prosp-modelo--warn", isBootstrap);
        var meta = [d.versao || "—"];
        if (ndcg != null) meta.push("NDCG " + ndcg);
        if (isBootstrap) meta.push("scores indicativos");
        el.textContent = meta.filter(Boolean).join(" · ");
        el.classList.add("prosp-model-meta");
      }
    } catch (_e) {
      if (el) {
        el.textContent = "";
        el.classList.remove("prosp-modelo--warn");
      }
      renderAlgoritmoBadge("");
      setBootstrapBanner(false);
    }
  }

  function init() {
    var form = $("form-prosp-filtros");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        carregarFila();
      });
    }
    carregarModelo();
    carregarFila();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
