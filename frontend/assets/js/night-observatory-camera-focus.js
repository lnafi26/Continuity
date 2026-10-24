/*
 * Night Observatory — Event-Focused Canvas Camera
 * Pans the Canvas without scrolling the surrounding page.
 */
(function (root, factory) {
  "use strict";

  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (!root || !root.document) return;

  const view = document.getElementById("view-continuity");
  const stage = document.getElementById("noCanvasStage");

  if (!view || !stage) return;

  function findScroller() {
    let node = stage.parentElement;
    let fallback = null;

    while (node && node !== view && node !== document.body) {
      const style = getComputedStyle(node);
      const overflow = style.overflowX + " " + style.overflowY;

      if (/(auto|scroll)/.test(overflow)) return node;

      if (/no-canvas-(viewport|scroll)/.test(
        String(node.className)
      )) {
        fallback ||= node;
      }

      node = node.parentElement;
    }

    return fallback || stage.parentElement;
  }

  const scroller = findScroller();

  if (!scroller) return;

  // Preserve existing padding and add navigable camera space.
  const initial = getComputedStyle(scroller);
  const sides = ["Left", "Right", "Top", "Bottom"];
  const basePadding = Object.fromEntries(
    sides.map(side => [
      side,
      parseFloat(initial["padding" + side]) || 0
    ])
  );

  let lastGutterX = -1;
  let lastGutterY = -1;

  function updateGutters() {
    const width = scroller.clientWidth;
    const height = scroller.clientHeight;

    if (!width || !height) return;

    const gutter = api.gutterSize(width, height);

    if (
      gutter.x === lastGutterX &&
      gutter.y === lastGutterY
    ) return;

    const before = stage.getBoundingClientRect();

    scroller.style.paddingLeft =
      `${basePadding.Left + gutter.x}px`;
    scroller.style.paddingRight =
      `${basePadding.Right + gutter.x}px`;
    scroller.style.paddingTop =
      `${basePadding.Top + gutter.y}px`;
    scroller.style.paddingBottom =
      `${basePadding.Bottom + gutter.y}px`;

    lastGutterX = gutter.x;
    lastGutterY = gutter.y;

    // Keep the currently viewed Canvas position stationary
    // while the gutters are first added or resized.
    const after = stage.getBoundingClientRect();

    if (before.width && after.width) {
      scroller.scrollLeft += after.left - before.left;
      scroller.scrollTop += after.top - before.top;
    }
  }

  let gutterScheduled = false;

  function scheduleGutters() {
    if (gutterScheduled) return;
    gutterScheduled = true;

    root.requestAnimationFrame(() => {
      gutterScheduled = false;
      updateGutters();
    });
  }

  if ("ResizeObserver" in root) {
    const resizeObserver = new ResizeObserver(scheduleGutters);
    resizeObserver.observe(scroller);
  }

  const visibilityObserver = new MutationObserver(
    scheduleGutters
  );

  visibilityObserver.observe(view, {
    attributes: true,
    attributeFilter: ["hidden", "style", "class"]
  });

  root.addEventListener("resize", scheduleGutters);
  scheduleGutters();

  function focusEvent(eventId) {
    const node = Array.from(
      stage.querySelectorAll(
        ".no-canvas-node[data-no-event]"
      )
    ).find(item => item.dataset.noEvent === eventId);

    if (!node || view.hidden) return;

    const anchor = api.eventAnchor(
      node,
      stage.getBoundingClientRect()
    );

    const delta = api.centerDelta(
      scroller.getBoundingClientRect(),
      anchor
    );

    if (Math.abs(delta.x) < 2 && Math.abs(delta.y) < 2) {
      return;
    }

    const reducedMotion = root.matchMedia?.(
      "(prefers-reduced-motion: reduce)"
    )?.matches;

    scroller.scrollTo({
      left: scroller.scrollLeft + delta.x,
      top: scroller.scrollTop + delta.y,
      behavior: reducedMotion ? "auto" : "smooth"
    });
  }

  // The existing event controller handles selection first.
  // We move the camera on the next animation frame.
  view.addEventListener("click", event => {
    const button = event.target.closest?.(
      ".no-timeline-event[data-no-event]"
    );

    if (!button || !view.contains(button)) return;

    const id = button.dataset.noEvent;

    root.requestAnimationFrame(() => {
      focusEvent(id);
    });
  });

})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function centerDelta(viewport, target) {
    return {
      x: target.x - (viewport.left + viewport.width / 2),
      y: target.y - (viewport.top + viewport.height / 2)
    };
  }

  function eventAnchor(node, stageRect) {
    const left = node.style.left;
    const top = node.style.top;

    // Canvas nodes are positioned by percentages of the stage.
    // Use the actual historical marker position, not the
    // center of its potentially wider text label.
    if (
      left.endsWith("%") &&
      top.endsWith("%") &&
      Number.isFinite(parseFloat(left)) &&
      Number.isFinite(parseFloat(top))
    ) {
      return {
        x: stageRect.left +
          (parseFloat(left) / 100) * stageRect.width,
        y: stageRect.top +
          (parseFloat(top) / 100) * stageRect.height
      };
    }

    // Fallback for future renderers.
    const rect = node.getBoundingClientRect();

    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2
    };
  }

  function gutterSize(width, height) {
    return {
      x: Math.ceil(Math.max(0, width) / 2),
      y: Math.ceil(Math.max(0, height) / 2)
    };
  }

  return Object.freeze({
    centerDelta,
    eventAnchor,
    gutterSize
  });
});
