
/*
 * Project Continuity — Timeline Viewport
 * C2.1c: Pan, zoom, and reset.
 * Synthetic visual demonstration only.
 */
(() => {
  "use strict";

  const viewport = document.getElementById("noCanvasViewport");
  const stage = viewport?.querySelector(".no-canvas-stage");
  const view = document.getElementById("view-continuity");
  const zoomLabel = document.getElementById("noZoomLevel");
  const zoomIn = document.getElementById("noZoomIn");
  const zoomOut = document.getElementById("noZoomOut");
  const reset = document.getElementById("noZoomReset");

  if (!viewport || !stage || !view || !zoomLabel) return;

  const MIN = 0.75;
  const MAX = 2;
  const STEP = 0.25;
  const BASE_HEIGHT =
    Number(stage.dataset.noBaseHeight) || 280;
  const BASE_WIDTH =
    Number(stage.dataset.noBaseWidth) || 1000;

  let zoom = 1;
  let drag = null;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function applyZoom(nextZoom, resetPosition = false) {
    const oldWidth = stage.offsetWidth || 1000;
    const oldHeight = stage.offsetHeight || BASE_HEIGHT;

    // Preserve the approximate viewport center when zooming.
    const centerX = clamp(
      (viewport.scrollLeft + viewport.clientWidth / 2) / oldWidth,
      0, 1
    );
    const centerY = clamp(
      (viewport.scrollTop + viewport.clientHeight / 2) / oldHeight,
      0, 1
    );

    zoom = clamp(nextZoom, MIN, MAX);

    const baseWidth = Math.max(BASE_WIDTH, viewport.clientWidth);

    stage.style.width = Math.round(baseWidth * zoom) + "px";
    stage.style.height = Math.round(BASE_HEIGHT * zoom) + "px";

    zoomLabel.textContent = Math.round(zoom * 100) + "%";
    if (zoomIn) zoomIn.disabled = zoom >= MAX;
    if (zoomOut) zoomOut.disabled = zoom <= MIN;

    if (resetPosition) {
      viewport.scrollLeft = 0;
      viewport.scrollTop = 0;
    } else {
      viewport.scrollLeft =
        Math.round(stage.offsetWidth * centerX - viewport.clientWidth / 2);
      viewport.scrollTop =
        Math.round(stage.offsetHeight * centerY - viewport.clientHeight / 2);
    }
  }

  zoomIn?.addEventListener("click", () => {
    applyZoom(zoom + STEP);
  });

  zoomOut?.addEventListener("click", () => {
    applyZoom(zoom - STEP);
  });

  reset?.addEventListener("click", () => {
    applyZoom(1, true);
  });

  // Mouse-drag on the background pans the viewport.
  // Event buttons retain their normal click behavior.
  viewport.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "mouse" || event.button !== 0) return;
    if (event.target.closest("button, a, input")) return;

    drag = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      left: viewport.scrollLeft,
      top: viewport.scrollTop
    };

    viewport.setPointerCapture(event.pointerId);
    viewport.classList.add("no-dragging");
  });

  viewport.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;

    viewport.scrollLeft = drag.left - (event.clientX - drag.x);
    viewport.scrollTop = drag.top - (event.clientY - drag.y);
  });

  function endDrag(event) {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null;
    viewport.classList.remove("no-dragging");
  }

  viewport.addEventListener("pointerup", endDrag);
  viewport.addEventListener("pointercancel", endDrag);
  viewport.addEventListener("lostpointercapture", endDrag);

  // The Continuity screen begins hidden. Recalculate its
  // dimensions when it first becomes visible.
  const observer = new MutationObserver(() => {
    if (!view.hidden) applyZoom(zoom);
  });

  observer.observe(view, {
    attributes: true,
    attributeFilter: ["hidden"]
  });

  window.addEventListener("resize", () => {
    if (!view.hidden) applyZoom(zoom);
  });

  applyZoom(1, true);
})();
