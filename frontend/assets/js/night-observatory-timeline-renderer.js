/*
 * Continuity — Data-Driven Timeline Renderer
 * C2.1c: Date-based primary strand visualization.
 * This is a flat Canvas foundation, not the final 2.5D engine.
 */
(() => {
  "use strict";

  const model = window.ContinuityTimelineData;
  const stage = document.getElementById("noCanvasStage");

  if (!stage || !model || model.dataset !== "synthetic") {
    console.error("Timeline demonstration data unavailable.");
    return;
  }

  const namespace = "http://www.w3.org/2000/svg";

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS(namespace, name);
    for (const [key, value] of Object.entries(attributes)) {
      element.setAttribute(key, String(value));
    }
    return element;
  }

  function dateLabel(date, options) {
    return new Intl.DateTimeFormat("en-US", {
      ...options,
      timeZone: "UTC"
    }).format(new Date(date + "T00:00:00Z"));
  }

  const eventsById = new Map(
    model.events.map(event => [event.id, event])
  );

  // Layout decisions belong to the planner, not the renderer.
  const layoutApi = window.ContinuityTimelineLayout;

  if (!layoutApi || typeof layoutApi.plan !== "function") {
    stage.textContent = "Historical layout planner unavailable.";
    return;
  }

  let layout;

  try {
    layout = layoutApi.plan(model);
  } catch (error) {
    console.error("Historical layout rejected:", error);
    stage.textContent = "Historical layout could not be generated.";
    return;
  }

  const visibleStrands = layout.strands.filter(
    strand => strand.nodes.length > 0
  );

  if (layout.undated.length || !visibleStrands.length) {
    stage.textContent =
      "This historical layout is not yet supported by the preview.";
    return;
  }

  const positions = visibleStrands.flatMap(strand =>
    strand.nodes.map(({ eventId, x, y }) => ({
      event: eventsById.get(eventId),
      x,
      y,
      strandId: strand.id
    }))
  );

  if (positions.some(({ event }) =>
    !event ||
    !["decision", "milestone"].includes(event.role)
  )) {
    stage.textContent = "Historical event roles are incomplete.";
    return;
  }

  const events = positions.map(({ event }) => event)
    .sort((a, b) =>
      a.occurredAt.localeCompare(b.occurredAt)
    );

  const svg = svgElement("svg", {
    class: "no-canvas-lines",
    viewBox: `0 0 ${layout.width} ${layout.height}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true"
  });

  const defs = svgElement("defs");
  const pattern = svgElement("pattern", {
    id: "noCanvasDynamicGrid",
    width: 50,
    height: 50,
    patternUnits: "userSpaceOnUse"
  });

  pattern.append(
    svgElement("path", {
      d: "M 50 0 L 0 0 0 50",
      fill: "none",
      stroke: "#27364a",
      "stroke-width": 0.6
    })
  );
  defs.append(pattern);
  svg.append(defs);

  svg.append(
    svgElement("rect", {
      width: layout.width,
      height: layout.height,
      fill: "url(#noCanvasDynamicGrid)"
    })
  );

  // Independent strands never acquire invented connections.
  const strandColors = ["#82adc5", "#83cddd", "#a8dfc9"];

  visibleStrands.forEach((strand, lane) => {
    const points = strand.nodes;
    if (points.length < 2) return;

    let pathData = `M ${points[0].x} ${points[0].y}`;

    for (let index = 1; index < points.length; index++) {
      const previous = points[index - 1];
      const current = points[index];
      const distance = current.x - previous.x;
      const lift = Math.min(
        36, Math.max(12, distance * 0.06)
      );

      pathData +=
        ` C ${previous.x + distance * 0.35} ${previous.y - lift}` +
        ` ${current.x - distance * 0.35} ${current.y + lift}` +
        ` ${current.x} ${current.y}`;
    }

    svg.append(
      svgElement("path", {
        d: pathData,
        fill: "none",
        stroke: strandColors[lane % strandColors.length],
        "stroke-width": 3,
        "stroke-linecap": "round"
      })
    );
  });

  const nodes = positions.map(({ event, x, y }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "no-timeline-event no-canvas-node";
    button.dataset.noEvent = event.id;
    button.setAttribute("aria-pressed", "false");
    button.setAttribute(
      "aria-label",
      `Inspect ${event.shortTitle}, ${dateLabel(event.occurredAt, {
        month: "long", day: "numeric", year: "numeric"
      })}`
    );

    button.style.left = (x / layout.width * 100) + "%";
    button.style.top = (y / layout.height * 100) + "%";

    // Align the marker itself with the underlying strand.
    button.style.transform = "translate(-50%, -23px)";

    const shape = document.createElement("span");
    shape.className = "no-canvas-shape " +
      (event.role === "decision"
        ? "no-canvas-decision"
        : "no-canvas-milestone");
    shape.setAttribute("aria-hidden", "true");

    const label = document.createElement("span");
    label.className = "no-canvas-node-label";

    const title = document.createElement("strong");
    title.textContent = event.shortTitle;

    const date = document.createElement("small");
    date.textContent = dateLabel(event.occurredAt, {
      month: "short", day: "numeric", year: "numeric"
    });

    label.append(title, date);
    button.append(shape, label);

    return button;
  });

  const labels = document.createElement("div");
  labels.className = "no-canvas-time-labels";
  labels.setAttribute("aria-hidden", "true");

  for (const event of [events[0], events[events.length - 1]]) {
    const label = document.createElement("span");
    label.textContent = dateLabel(event.occurredAt, {
      month: "long", year: "numeric"
    });
    labels.append(label);
  }

  const laneLabels = visibleStrands.map(strand => {
    const label = document.createElement("span");
    label.className = "no-canvas-lane-label";
    label.textContent = strand.label;
    label.style.top =
      ((strand.nodes[0].y - 80) / layout.height * 100) + "%";
    return label;
  });

  // The viewport reads these dimensions when applying zoom.
  stage.dataset.noBaseWidth = String(layout.width);
  stage.dataset.noBaseHeight = String(layout.height);

  stage.replaceChildren(svg, ...laneLabels, ...nodes, labels);

  console.info(
    `Continuity Timeline: rendered ${events.length} synthetic events.`
  );
})();
