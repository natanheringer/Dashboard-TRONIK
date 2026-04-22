/* Preview v2 — sidebar mobile, toasts, animação de barras, HTMX hooks */
(function () {
  const rotas = {
    home: "/preview/",
    monit: "/preview/monitoramento",
    mapa: "/preview/mapa",
    relatorios: "/preview/relatorios",
    parceiro: "/preview/parceiro",
  };

  window.ativarView = function (id) {
    const destino = rotas[id];
    if (destino) window.location.href = destino;
  };

  window.togglePreviewSidebar = function () {
    const sidebar = document.querySelector(".sidebar");
    const backdrop = document.querySelector(".sidebar-backdrop");
    sidebar && sidebar.classList.toggle("open");
    backdrop && backdrop.classList.toggle("open");
  };

  function closeSidebarMobile() {
    if (!window.matchMedia("(max-width: 768px)").matches) return;
    document.querySelector(".sidebar")?.classList.remove("open");
    document.querySelector(".sidebar-backdrop")?.classList.remove("open");
  }

  document.querySelectorAll(".nav-item[data-view]").forEach(function (item) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      window.ativarView(item.dataset.view);
    });
  });

  document.querySelectorAll(".sidebar a.nav-item[href]").forEach(function (a) {
    a.addEventListener("click", function () {
      closeSidebarMobile();
    });
  });

  /* ---------- Toasts ---------- */
  function ensureToastStack() {
    let el = document.getElementById("preview-toast-stack");
    if (!el) {
      el = document.createElement("div");
      el.id = "preview-toast-stack";
      el.className = "preview-toast-stack";
      el.setAttribute("aria-live", "polite");
      document.body.appendChild(el);
    }
    return el;
  }

  window.previewToast = function (message, variant) {
    const stack = ensureToastStack();
    const t = document.createElement("div");
    t.className = "preview-toast";
    if (variant === "ok") t.classList.add("preview-toast--ok");
    if (variant === "warn") t.classList.add("preview-toast--warn");
    t.textContent = message;
    stack.appendChild(t);
    setTimeout(function () {
      t.style.opacity = "0";
      t.style.transform = "translateY(6px)";
      t.style.transition = "opacity 0.25s ease, transform 0.25s ease";
      setTimeout(function () {
        t.remove();
      }, 280);
    }, 2600);
  };

  /* ---------- Barras (nível + relatórios) ---------- */
  function animarBarras(root) {
    const scope = root || document;
    scope.querySelectorAll(".level-fill[data-pct]").forEach(function (el) {
      const pct = parseFloat(el.getAttribute("data-pct"), 10);
      const w = Number.isFinite(pct) ? Math.min(100, Math.max(0, pct)) : 0;
      el.style.width = "0%";
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          el.style.width = w + "%";
        });
      });
    });
    scope.querySelectorAll(".preview-databar[data-pct]").forEach(function (el) {
      const pct = parseFloat(el.getAttribute("data-pct"), 10);
      const w = Number.isFinite(pct) ? Math.min(100, Math.max(0, pct)) : 0;
      el.style.width = "0%";
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          el.style.width = w + "%";
        });
      });
    });
  }

  window.previewSetRelRange = function (dias) {
    const fim = document.getElementById("rel-fim");
    const ini = document.getElementById("rel-inicio");
    if (!fim || !ini) return;
    const hoje = new Date();
    const f = new Date(hoje);
    const i = new Date(hoje);
    i.setDate(i.getDate() - (dias - 1));
    fim.value = f.toISOString().slice(0, 10);
    ini.value = i.toISOString().slice(0, 10);
    const form = document.getElementById("form-rel");
    if (form && window.htmx) {
      htmx.trigger(form, "submit");
    } else if (form) {
      form.submit();
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    animarBarras(document);
  });

  document.body.addEventListener("htmx:afterSwap", function (e) {
    animarBarras(document);
    const id = e.detail && e.detail.target && e.detail.target.id;
    if (id === "preview-swap-monit" || id === "preview-swap-relatorios-block") {
      window.previewToast("Atualizado", "ok");
    }
  });

  document.body.addEventListener("htmx:responseError", function () {
    window.previewToast("Não foi possível atualizar. Tente de novo.", "warn");
  });

  /* ---------- WebSocket Real-time Updates ---------- */
  window.PreviewSocket = {
    socket: null,
    isConnected: false,
    isPublicPreview: false,
    currentView: null,

    init: function () {
      // Detectar se é preview público (sem autenticação)
      const body = document.querySelector("body");
      this.isPublicPreview = body && body.classList.contains("preview-public");

      // Não conectar ao WebSocket em preview público
      if (this.isPublicPreview) {
        console.log("[Preview] Public preview mode - WebSocket disabled");
        return;
      }

      // Conectar apenas se Socket.IO estiver disponível
      if (typeof io === "undefined") {
        console.warn("[Preview] Socket.IO not available");
        return;
      }

      try {
        this.socket = io("/", {
          reconnection: true,
          reconnectionDelay: 1000,
          reconnectionDelayMax: 5000,
          reconnectionAttempts: 5,
          transports: ["websocket", "polling"],
        });

        this.attachHandlers();
      } catch (e) {
        console.error("[Preview] WebSocket init failed:", e);
      }
    },

    attachHandlers: function () {
      if (!this.socket) return;

      const self = this;

      this.socket.on("connect", function () {
        self.isConnected = true;
        console.log("[Preview] WebSocket connected");
        self.subscribeToCurrentView();
      });

      this.socket.on("disconnect", function () {
        self.isConnected = false;
        console.log("[Preview] WebSocket disconnected");
      });

      this.socket.on("coletor_atualizado", function (data) {
        self.onColetorUpdate(data);
      });

      this.socket.on("sensor_atualizado", function (data) {
        self.onSensorUpdate(data);
      });

      this.socket.on("nova_notificacao", function (data) {
        self.onNewNotification(data);
      });

      this.socket.on("error", function (err) {
        console.error("[Preview] WebSocket error:", err);
      });
    },

    subscribeToCurrentView: function () {
      if (!this.socket || !this.isConnected) return;

      const view = this.getCurrentView();
      if (view === "monit") {
        this.socket.emit("subscribe_lixeiras");
        console.log("[Preview] Subscribed to coletores updates");
      } else if (view === "mapa") {
        this.socket.emit("subscribe_lixeiras");
        console.log("[Preview] Subscribed to coletores updates (mapa)");
      }
    },

    getCurrentView: function () {
      const activeView = document.querySelector(".view.active");
      if (!activeView) return null;
      const match = activeView.id.match(/view-(.+)/);
      return match ? match[1] : null;
    },

    onColetorUpdate: function (data) {
      const view = this.getCurrentView();
      if (!view || (view !== "monit" && view !== "mapa")) return;

      // Update KPI stats if visible
      if (view === "monit") {
        this.updateKpiIfVisible("monit", data);
        this.updateColetorCard(data);
      } else if (view === "mapa") {
        this.updateMapMarker(data);
      }
    },

    updateKpiIfVisible: function (view, coletorData) {
      // Re-fetch stats and update KPI bars
      // This is conservative - only update if coletor belongs to current filters
      if (view === "monit") {
        const q = document.querySelector('input[name="q"]');
        const nivel = document.querySelector('button.filter-chip.active[name="nivel"]');
        const shouldUpdate =
          !q ||
          !q.value ||
          this.matchesFilter(coletorData, q.value, nivel ? nivel.value : "todos");
        if (shouldUpdate) {
          console.log("[Preview] Coletor matches filter, triggering refresh");
          const form = document.getElementById("form-monit");
          if (form && window.htmx) {
            htmx.trigger(form, "submit");
          }
        }
      }
    },

    matchesFilter: function (coletorData, searchText, nivelFilter) {
      const blob = (
        coletorData.localizacao +
        " " +
        (coletorData.parceiro || "") +
        " " +
        coletorData.id +
        " L" +
        String(coletorData.id).padStart(3, "0")
      ).toLowerCase();
      if (searchText && !blob.includes(searchText.toLowerCase())) {
        return false;
      }
      if (nivelFilter !== "todos") {
        // Would need nivel classification - for now accept
      }
      return true;
    },

    updateColetorCard: function (coletorData) {
      // Find and update card element if visible
      const card = document.querySelector(`[data-coletor-id="${coletorData.id}"]`);
      if (card) {
        // Update nivel percentage and bar
        const levelValue = card.querySelector(".level-value");
        const levelFill = card.querySelector(".level-fill");
        if (levelValue) {
          levelValue.textContent = Math.round(coletorData.nivel_preenchimento) + "%";
        }
        if (levelFill) {
          levelFill.setAttribute("data-pct", coletorData.nivel_preenchimento);
          levelFill.style.width = Math.min(100, coletorData.nivel_preenchimento) + "%";
        }
        // Update status badge
        const badge = card.querySelector(".badge");
        if (badge && coletorData.status_classe) {
          badge.classList.remove("crit", "warn", "ok", "neutral");
          badge.classList.add(coletorData.status_classe);
          badge.textContent = this.getBadgeLabel(coletorData.status_classe);
        }
      }
    },

    updateMapMarker: function (coletorData) {
      // Update map marker if mapa-preview.js available
      if (window.PreviewMapa && window.PreviewMapa.updateMarker) {
        window.PreviewMapa.updateMarker(coletorData);
      }
    },

    onSensorUpdate: function (data) {
      // Update sensor battery info in cards
      const card = document.querySelector(`[data-sensor-id="${data.id}"]`);
      if (card) {
        const batteryText = card.querySelector(".sensor-battery");
        if (batteryText) {
          batteryText.textContent = Math.round(data.bateria) + "%";
        }
      }
    },

    onNewNotification: function (data) {
      previewToast("Nova notificação: " + data.titulo, data.tipo === "lixeira_cheia" ? "warn" : "ok");
      // Optionally trigger refresh of alerts
    },

    getBadgeLabel: function (classe) {
      return {
        crit: "Crítico",
        warn: "Atenção",
        ok: "Normal",
        neutral: "Manutenção",
      }[classe] || "Normal";
    },
  };

  // Initialize WebSocket on page load
  document.addEventListener("DOMContentLoaded", function () {
    window.PreviewSocket.init();
  });

  // Re-subscribe when view changes via HTMX
  document.body.addEventListener("htmx:afterSwap", function () {
    window.PreviewSocket.subscribeToCurrentView();
  });
})();
