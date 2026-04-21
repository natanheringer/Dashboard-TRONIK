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
})();
