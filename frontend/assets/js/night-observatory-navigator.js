/*
 * Night Observatory — Historical Timeline Navigator.
 * Standalone preview only; no network or data mutations.
 */
(function (root, factory) {
  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (!root || !root.document) return;

  const view = document.getElementById("view-continuity");
  const stage = document.getElementById("noCanvasStage");
  const model = root.ContinuityTimelineData;
  const planner = root.ContinuityTimelineLayout;

  if (!view || !stage || !model || !planner) return;

  let layout;
  try {
    layout = planner.plan(model);
  } catch (error) {
    console.error("Timeline Navigator layout rejected:", error);
    return;
  }

  const NS = "http://www.w3.org/2000/svg";

  function svgElement(tag, attrs = {}) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) {
      node.setAttribute(key, String(value));
    }
    return node;
  }

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

  const navigator = document.createElement("section");
  navigator.className = "no-timeline-navigator";
  navigator.setAttribute("aria-label", "Timeline Navigator");

  const heading = document.createElement("div");
  heading.className = "no-navigator-heading";

  const title = document.createElement("strong");
  title.textContent = "Timeline Navigator";

  const count = document.createElement("span");
  const n = layout.strands.length;
  count.textContent = `${n} historical workstream${n === 1 ? "" : "s"}`;

  heading.append(title, count);

  const map = document.createElement("div");
  map.className = "no-navigator-map";

  const svg = svgElement("svg", {
    viewBox: `0 0 ${layout.width} ${layout.height}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true"
  });

  const colors = ["#a4c4ff", "#83cddd", "#a8dfc9"];

  for (let i = 0; i < layout.strands.length; i++) {
    const strand = layout.strands[i];
    const color = colors[i % colors.length];

    if (strand.nodes.length >= 2) {
      svg.append(svgElement("path", {
        d: strand.path,
        fill: "none",
        stroke: color,
        "stroke-width": 2,
        "vector-effect": "non-scaling-stroke",
        "stroke-linecap": "round"
      }));
    }

    for (const node of strand.nodes) {
      const dot = svgElement("circle", {
        cx: node.x,
        cy: node.y,
        r: 7,
        fill: color
      });

      const tooltip = svgElement("title");
      tooltip.textContent = node.eventId;
      dot.append(tooltip);
      svg.append(dot);
    }
  }

  const windowMarker = document.createElement("div");
  windowMarker.className = "no-navigator-window";
  windowMarker.hidden = true;

  const hitTarget = document.createElement("button");
  hitTarget.type = "button";
  hitTarget.className = "no-navigator-hit";
  hitTarget.setAttribute(
    "aria-label",
    "Pan Timeline. Click or drag to navigate; " +
    "use arrow keys to move through history."
  );

  const selectedMarker = document.createElement("div");
  selectedMarker.className = "no-navigator-selected";
  selectedMarker.hidden = true;
  selectedMarker.setAttribute("aria-hidden", "true");

  map.append(svg, windowMarker, selectedMarker, hitTarget);

  const hint = document.createElement("p");
  hint.className = "no-navigator-hint";
  hint.textContent =
    "Click or drag to pan · Arrow keys for precise movement";

  navigator.append(heading, map, hint);

  const anchor = view.querySelector(".no-canvas-region")
    || scroller;

  anchor.after(navigator);

  const eventPositions = new Map(
    layout.strands.flatMap(strand =>
      strand.nodes.map(node => [
        node.eventId,
        { x: node.x, y: node.y }
      ])
    )
  );

  function updateSelectedMarker() {
    const selected = stage.querySelector(
      '.no-canvas-node[aria-pressed="true"]'
    );

    const position = selected
      ? eventPositions.get(selected.dataset.noEvent)
      : null;

    if (!position) {
      selectedMarker.hidden = true;
      return;
    }

    selectedMarker.style.left =
      `${position.x / layout.width * 100}%`;
    selectedMarker.style.top =
      `${position.y / layout.height * 100}%`;

    selectedMarker.hidden = false;
  }

  let scheduled = false;

  function updateWindow() {
    scheduled = false;
    updateSelectedMarker();

    const viewportRect = scroller.getBoundingClientRect();
    const stageRect = stage.getBoundingClientRect();

    if (
      viewportRect.width <= 0 || viewportRect.height <= 0 ||
      stageRect.width <= 0 || stageRect.height <= 0
    ) {
      windowMarker.hidden = true;
      return;
    }

    const visible = api.visibleWindow(viewportRect, stageRect);

    windowMarker.style.left = `${visible.left * 100}%`;
    windowMarker.style.top = `${visible.top * 100}%`;
    windowMarker.style.width = `${visible.width * 100}%`;
    windowMarker.style.height = `${visible.height * 100}%`;
    windowMarker.hidden = false;
  }

  function scheduleUpdate() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(updateWindow);
  }

  function panToPointer(event) {
    const fraction = api.mapPoint(
      event.clientX,
      event.clientY,
      hitTarget.getBoundingClientRect()
    );

    const viewportRect = scroller.getBoundingClientRect();
    const stageRect = stage.getBoundingClientRect();

    if (!stageRect.width || !stageRect.height) return;

    // Move the point indicated on the miniature map to
    // the center of the currently visible Canvas.
    const targetX =
      stageRect.left + fraction.x * stageRect.width;
    const targetY =
      stageRect.top + fraction.y * stageRect.height;

    scroller.scrollLeft += targetX -
      (viewportRect.left + viewportRect.width / 2);

    scroller.scrollTop += targetY -
      (viewportRect.top + viewportRect.height / 2);

    scheduleUpdate();
  }

  let dragging = false;

  hitTarget.addEventListener("pointerdown", event => {
    if (event.button !== 0) return;

    dragging = true;
    hitTarget.focus({ preventScroll: true });
    hitTarget.setPointerCapture(event.pointerId);
    panToPointer(event);
    event.preventDefault();
  });

  hitTarget.addEventListener("pointermove", event => {
    if (dragging) panToPointer(event);
  });

  function endDrag() {
    dragging = false;
  }

  hitTarget.addEventListener("pointerup", endDrag);
  hitTarget.addEventListener("pointercancel", endDrag);
  hitTarget.addEventListener("lostpointercapture", endDrag);

  hitTarget.addEventListener("keydown", event => {
    const stepX = Math.max(40, scroller.clientWidth * 0.2);
    const stepY = Math.max(40, scroller.clientHeight * 0.2);

    switch (event.key) {
      case "ArrowLeft":
        scroller.scrollLeft -= stepX;
        break;
      case "ArrowRight":
        scroller.scrollLeft += stepX;
        break;
      case "ArrowUp":
        scroller.scrollTop -= stepY;
        break;
      case "ArrowDown":
        scroller.scrollTop += stepY;
        break;
      case "Home":
        scroller.scrollLeft = 0;
        break;
      case "End":
        scroller.scrollLeft = scroller.scrollWidth;
        break;
      default:
        return;
    }

    event.preventDefault();
    scheduleUpdate();
  });

  scroller.addEventListener(
    "scroll", scheduleUpdate, { passive: true }
  );
  root.addEventListener("resize", scheduleUpdate);

  if ("ResizeObserver" in root) {
    const observer = new ResizeObserver(scheduleUpdate);
    observer.observe(scroller);
    observer.observe(stage);
  }

  const changes = new MutationObserver(scheduleUpdate);
  changes.observe(stage, {
    attributes: true,
    attributeFilter: ["style", "class"]
  });
  changes.observe(view, {
    attributes: true,
    attributeFilter: ["hidden", "style", "class"]
  });

  // Selection changes are separate from camera movement.
  const selectionObserver = new MutationObserver(scheduleUpdate);

  selectionObserver.observe(stage, {
    subtree: true,
    attributes: true,
    attributeFilter: ["aria-pressed"]
  });

  scheduleUpdate();
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function clamp(value) {
    return Math.max(0, Math.min(1, value));
  }

  function visibleWindow(viewport, stage) {
    const left = clamp(
      (viewport.left - stage.left) / stage.width
    );
    const right = clamp(
      (viewport.left + viewport.width - stage.left) /
      stage.width
    );
    const top = clamp(
      (viewport.top - stage.top) / stage.height
    );
    const bottom = clamp(
      (viewport.top + viewport.height - stage.top) /
      stage.height
    );

    return {
      left,
      top,
      width: Math.max(0, right - left),
      height: Math.max(0, bottom - top)
    };
  }

  function mapPoint(clientX, clientY, rect) {
    return {
      x: clamp((clientX - rect.left) / rect.width),
      y: clamp((clientY - rect.top) / rect.height)
    };
  }

  return Object.freeze({
    visibleWindow,
    mapPoint
  });
});
