/**
 * Mapa Leaflet para preview v2 — marcadores a partir de window.__PREVIEW_MAP__.
 */
(function () {
  const data = window.__PREVIEW_MAP__ || [];
  const selectedRaw = window.__PREVIEW_SELECTED__;
  const selectedId =
    selectedRaw === null || selectedRaw === undefined ? null : Number(selectedRaw);

  function corPin(classe) {
    if (classe === "crit") return "#9b2a1f";
    if (classe === "warn") return "#b0661e";
    if (classe === "neutral") return "#6b6254";
    return "#1a5d3a";
  }

  const el = document.getElementById("leaflet-map");
  if (!el || typeof L === "undefined") return;

  const map = L.map(el, { scrollWheelZoom: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  const markers = [];
  let alvo = null;
  data.forEach(function (m) {
    const circle = L.circleMarker([m.lat, m.lng], {
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
    circle.addTo(map);
    markers.push(circle);
    if (selectedId !== null && Number(m.id) === selectedId) alvo = m;
  });

  function applyView() {
    if (data.length && markers.length) {
      try {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.15));
      } catch (_e) {
        map.setView([-15.793889, -47.882778], 11);
      }
    } else {
      map.setView([-15.793889, -47.882778], 11);
    }
    if (alvo) {
      map.setView([alvo.lat, alvo.lng], 14);
    }
  }

  applyView();

  function reflowMap() {
    map.invalidateSize();
    if (data.length && markers.length) {
      try {
        map.fitBounds(L.featureGroup(markers).getBounds().pad(0.15));
      } catch (_e) {
        /* ignore */
      }
    }
    if (alvo) {
      map.setView([alvo.lat, alvo.lng], 14);
    }
  }

  requestAnimationFrame(reflowMap);
  setTimeout(reflowMap, 250);
})();
