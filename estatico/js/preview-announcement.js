/**
 * Aviso modal: nova dashboard em demo (/preview).
 * "Ficar aqui" grava em sessionStorage até fechar o navegador.
 */
(function () {
  var STORAGE_KEY = "tronik_preview_demo_dismiss_session";

  function getOverlay() {
    return document.getElementById("preview-demo-overlay");
  }

  function shouldShow() {
    if (!getOverlay()) return false;
    if (sessionStorage.getItem(STORAGE_KEY)) return false;
    var path = window.location.pathname || "";
    if (path.indexOf("/preview") === 0) return false;
    return true;
  }

  function open() {
    var overlay = document.getElementById("preview-demo-overlay");
    if (!overlay) return;
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    var closeBtn = document.getElementById("preview-demo-close");
    if (closeBtn) closeBtn.focus();
    document.body.style.overflow = "hidden";
  }

  function close() {
    var overlay = document.getElementById("preview-demo-overlay");
    if (!overlay) return;
    overlay.classList.remove("is-visible");
    overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function stayHere() {
    sessionStorage.setItem(STORAGE_KEY, "1");
    close();
  }

  function goPreview() {
    var el = getOverlay();
    var url = (el && el.getAttribute("data-preview-url")) || "/preview/";
    window.location.href = url;
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!shouldShow()) return;
    requestAnimationFrame(function () {
      requestAnimationFrame(open);
    });

    var btnPreview = document.getElementById("preview-demo-btn-preview");
    var btnStay = document.getElementById("preview-demo-btn-stay");
    var btnClose = document.getElementById("preview-demo-close");
    var overlay = document.getElementById("preview-demo-overlay");

    if (btnPreview) btnPreview.addEventListener("click", goPreview);
    if (btnStay) btnStay.addEventListener("click", stayHere);
    if (btnClose) btnClose.addEventListener("click", stayHere);

    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) stayHere();
      });
    }

    document.addEventListener("keydown", function esc(e) {
      if (e.key !== "Escape") return;
      var o = document.getElementById("preview-demo-overlay");
      if (!o || !o.classList.contains("is-visible")) return;
      stayHere();
      document.removeEventListener("keydown", esc);
    });
  });
})();
