/**
 * Mapa Leaflet preview v2 — cluster, sede opcional, fetch lazy de marcadores, WebSocket.
 */
(function () {
  var LIMIAR_ATENCAO = 80;
  var LIMIAR_CRITICO = 95;

  var selectedRaw = window.__PREVIEW_SELECTED__;
  var selectedId =
    selectedRaw === null || selectedRaw === undefined ? null : Number(selectedRaw);
  var sede = window.__PREVIEW_SEDE__ || null;
  var lazyLoad = !!window.__PREVIEW_MAP_LAZY__;

  function corPin(classe) {
    if (classe === "crit") return "#9b2a1f";
    if (classe === "warn") return "#b0661e";
    if (classe === "neutral") return "#6b6254";
    return "#1a5d3a";
  }

  function classFromPayload(row) {
    var st = (row.status || "OK").toString().toUpperCase();
    if (st === "QUEBRADA" || st === "MANUTENCAO" || st === "MANUTENÇÃO") return "neutral";
    var n = parseFloat(row.nivel_preenchimento);
    if (!Number.isFinite(n)) n = 0;
    if (n >= LIMIAR_CRITICO) return "crit";
    if (n >= LIMIAR_ATENCAO) return "warn";
    return "ok";
  }

  var el = document.getElementById("leaflet-map");
  if (!el || typeof L === "undefined") return;

  var map = L.map(el, { scrollWheelZoom: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  var cluster =
    typeof L.markerClusterGroup === "function"
      ? L.markerClusterGroup({
          maxClusterRadius: 52,
          spiderfyOnMaxZoom: true,
          showCoverageOnHover: false,
        })
      : null;

  if (cluster) {
    map.addLayer(cluster);
  }

  var data = [];
  var markersById = {};
  var markers = [];
  var alvo = null;

  function updateMarcadoresCount(filtrados, total) {
    var countEl = document.getElementById("mapa-marcadores-count");
    if (!countEl) return;
    if (total != null && filtrados !== total) {
      countEl.textContent = filtrados + " (" + total + " no total)";
    } else {
      countEl.textContent = String(filtrados);
    }
  }

  function loadMarkers(mapData) {
    data = mapData || [];
    markers = [];
    markersById = {};
    alvo = null;

    if (cluster) {
      cluster.clearLayers();
    }

    data.forEach(function (m) {
      var circle = L.circleMarker([m.lat, m.lng], {
        radius: 9,
        color: corPin(m.classe),
        fillColor: corPin(m.classe),
        fillOpacity: 0.85,
        weight: 2,
      });
      circle.bindPopup(
        "<strong>" +
          (m.label || "") +
          "</strong><br/>" +
          m.nivel +
          "% · " +
          (m.parceiro || "")
      );
      circle.on("click", function () {
        window.location.href =
          "/preview/mapa?coletor_id=" + encodeURIComponent(m.id);
      });
      if (cluster) {
        cluster.addLayer(circle);
      } else {
        circle.addTo(map);
      }
      markers.push(circle);
      markersById[m.id] = circle;
      if (selectedId !== null && Number(m.id) === selectedId) alvo = m;
    });

    applyView();
    reflowSoon();
  }

  function fetchMapData() {
    var f = window.__PREVIEW_MAP_FILTERS__ || {};
    var params = new URLSearchParams();
    if (f.nivel && f.nivel !== "todos") params.set("nivel", f.nivel);
    if (f.parceiro_id != null && f.parceiro_id !== "") {
      params.set("parceiro_id", String(f.parceiro_id));
    }
    if (f.q) params.set("q", f.q);
    var qs = params.toString();
    return fetch("/api/coletores/mapa" + (qs ? "?" + qs : ""), {
      credentials: "same-origin",
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (body) {
        updateMarcadoresCount(body.filtrados, body.total);
        return body.marcadores || [];
      });
  }

  if (sede && typeof sede.lat === "number" && typeof sede.lng === "number") {
    var sedeIcon = L.divIcon({
      className: "preview-sede-marker",
      html: '<span aria-hidden="true">🏢</span>',
      iconSize: [28, 28],
      iconAnchor: [14, 28],
    });
    L.marker([sede.lat, sede.lng], { icon: sedeIcon })
      .addTo(map)
      .bindPopup("<strong>" + (sede.label || "Sede") + "</strong>");
  }

  function boundsTargets() {
    var layers = [];
    if (cluster) {
      cluster.eachLayer(function (ly) {
        layers.push(ly);
      });
    } else {
      layers = markers;
    }
    return layers;
  }

  function applyView() {
    var layers = boundsTargets();
    if (data.length && layers.length) {
      try {
        var fg = L.featureGroup(layers);
        map.fitBounds(fg.getBounds().pad(0.15));
      } catch (_e) {
        map.setView([-15.793889, -47.882778], 11);
      }
    } else if (!window.__PROSPECCAO_PIN__) {
      map.setView([-15.793889, -47.882778], 11);
    }
    if (alvo) {
      map.setView([alvo.lat, alvo.lng], 14);
    }
  }

  function reflowMap() {
    map.invalidateSize();
    var layers = boundsTargets();
    if (data.length && layers.length) {
      try {
        map.fitBounds(L.featureGroup(layers).getBounds().pad(0.15));
      } catch (_e) {
        /* ignore */
      }
    }
    if (alvo) {
      map.setView([alvo.lat, alvo.lng], 14);
    }
  }

  function reflowSoon() {
    requestAnimationFrame(reflowMap);
    setTimeout(reflowMap, 250);
  }

  function updateMarker(row) {
    if (!row || row.id === undefined || row.id === null) return;
    var id = Number(row.id);
    var circle = markersById[id];
    if (!circle) return;

    var lat = parseFloat(row.latitude);
    var lng = parseFloat(row.longitude);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      circle.setLatLng([lat, lng]);
    }

    var cls = classFromPayload(row);
    var col = corPin(cls);
    circle.setStyle({ color: col, fillColor: col });

    var parc = row.parceiro && row.parceiro.nome ? row.parceiro.nome : "—";
    var nivel = Number.isFinite(parseFloat(row.nivel_preenchimento))
      ? Math.round(parseFloat(row.nivel_preenchimento) * 10) / 10
      : "—";
    circle.setPopupContent(
      "<strong>" +
        (row.localizacao || "") +
        "</strong><br/>" +
        nivel +
        "% · " +
        parc
    );

    if (cluster && typeof cluster.refreshClusters === "function") {
      cluster.refreshClusters();
    }
  }

  window.PreviewMapa = {
    map: map,
    cluster: cluster,
    markersById: markersById,
    updateMarker: updateMarker,
  };

  if (lazyLoad) {
    fetchMapData()
      .then(loadMarkers)
      .catch(function () {
        updateMarcadoresCount(0, 0);
        loadMarkers([]);
      });
  } else {
    var inline = window.__PREVIEW_MAP__ || [];
    updateMarcadoresCount(inline.length, inline.length);
    loadMarkers(inline);
  }

  var prospPin = window.__PROSPECCAO_PIN__;
  if (prospPin && typeof prospPin.lat === "number" && typeof prospPin.lon === "number") {
    var starIcon = L.divIcon({
      className: "",
      html: '<div style="width:20px;height:20px;background:#1a5d3a;border:3px solid #fff;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.4);"></div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
    L.marker([prospPin.lat, prospPin.lon], { icon: starIcon, zIndexOffset: 1000 })
      .addTo(map)
      .bindPopup(
        "<strong>" + (prospPin.label || "Candidato REE") + "</strong>" +
        "<br/><em style='color:#1a5d3a;font-size:11px;'>Prospecção REE</em>"
      )
      .openPopup();
    map.setView([prospPin.lat, prospPin.lon], 15);

    fetch("/api/prospeccao/candidatos?limite=50", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (body) {
        if (!body.ok || !Array.isArray(body.dados)) return;
        var prosp_cluster = typeof L.markerClusterGroup === "function"
          ? L.markerClusterGroup({ maxClusterRadius: 40, showCoverageOnHover: false })
          : null;
        body.dados.forEach(function (cand) {
          var loc = cand.local;
          if (!loc || loc.latitude == null || loc.longitude == null) return;
          var empresa = cand.empresa || {};
          var nome = empresa.razao_social || empresa.nome_fantasia || "Candidato REE";
          var isFocused = Math.abs(loc.latitude - prospPin.lat) < 0.0001 &&
                          Math.abs(loc.longitude - prospPin.lon) < 0.0001;
          if (isFocused) return;
          var smallIcon = L.circleMarker([loc.latitude, loc.longitude], {
            radius: 6,
            color: "#1a5d3a",
            fillColor: "#1a5d3a",
            fillOpacity: 0.45,
            weight: 1.5,
          });
          smallIcon.bindPopup(
            "<strong>" + nome + "</strong>" +
            "<br/><small>" + (empresa.bairro || cand.qid || "") + "</small>" +
            "<br/><a href='/preview/mapa?prosp_lat=" + loc.latitude +
            "&prosp_lon=" + loc.longitude +
            "&prosp_label=" + encodeURIComponent(nome) +
            "' style='color:#1a5d3a;font-size:11px;'>Focar aqui</a>"
          );
          if (prosp_cluster) {
            prosp_cluster.addLayer(smallIcon);
          } else {
            smallIcon.addTo(map);
          }
        });
        if (prosp_cluster) map.addLayer(prosp_cluster);
      })
      .catch(function () { /* sem candidatos — OK */ });
  }
})();
