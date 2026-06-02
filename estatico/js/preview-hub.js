/**
 * Preview v2 — Hub operacional: atualiza KPIs via API.
 */
(function () {
  "use strict";

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) return null;
      return r.json();
    });
  }

  function refreshColetores() {
    return fetchJson("/api/coletores/resumo").then(function (body) {
      if (!body || body.total_coletores == null) return;
      setText("kpi-total-coletores", body.total_coletores);
      setText("kpi-alerta", body.alerta_nivel_alto);
      setText("kpi-sem-geo", body.sem_geocode);
    });
  }

  function refreshProspeccao() {
    return fetchJson("/api/prospeccao/modelo-ativo").then(function (body) {
      if (!body || !body.ok || !body.dados) return;
      var d = body.dados;
      var metricas = d.metricas || {};
      var total = metricas.rows || metricas.total_scores;
      if (total != null) setText("kpi-prosp-total", total);
      var meta = document.getElementById("kpi-prosp-meta");
      if (meta && d.versao) {
        var ndcg = metricas.validation_ndcg_mean;
        meta.textContent =
          d.algoritmo +
          (ndcg != null ? " · NDCG " + ndcg : "");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!document.querySelector(".hub-kpi-strip")) return;
    refreshColetores().catch(function () {});
    refreshProspeccao().catch(function () {});
  });
})();
