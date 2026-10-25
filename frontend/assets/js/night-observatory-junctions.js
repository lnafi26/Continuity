/*
 * C2.2 — Evidence-linked historical connections.
 * Rendering requires explicit relationship eligibility.
 * This frontend check is not a backend permission boundary.
 */
(function (root, factory) {
  "use strict";

  const api = factory();
  if (root) root.ContinuityJunctionGeometry = api;

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (!root || !root.document) return;

  const model = root.ContinuityTimelineData;
  const layoutApi = root.ContinuityTimelineLayout;
  const validator = root.ContinuityHistoricalRelationships;
  const stage = document.getElementById("noCanvasStage");

  const inspector = document.getElementById("noEventInspector");

  if (!model || !layoutApi || !validator || !stage || !inspector) {
    console.error("Shared historical Inspector prerequisites missing.");
    return;
  }

  let layout;
  let result;

  try {
    layout = layoutApi.plan(model);
    result = validator.classify(model);
  } catch (error) {
    console.error("Historical relationship validation failed:", error);
    return;
  }

  // No link is drawn merely because two events coexist.
  if (!result.drawable.length) return;

  const positions = new Map();

  for (const strand of layout.strands) {
    for (const node of strand.nodes) {
      positions.set(
        `${strand.id}:${node.eventId}`,
        { x: node.x, y: node.y }
      );
    }
  }

  const NS = "http://www.w3.org/2000/svg";

  function svgElement(tag, attrs) {
    const element = document.createElementNS(NS, tag);

    for (const [name, value] of Object.entries(attrs)) {
      element.setAttribute(name, String(value));
    }

    return element;
  }

  const overlay = svgElement("svg", {
    class: "no-junction-overlay",
    viewBox: `0 0 ${layout.width} ${layout.height}`,
    preserveAspectRatio: "none",
    "aria-hidden": "true"
  });

  stage.append(overlay);

  const relationshipControls = [];

  function closeRelationships(except = null) {
    for (const control of relationshipControls) {
      if (control.marker !== except) {
        control.toggle(false);
      }
    }
  }

  const eventList = document.querySelector(
    "#view-continuity .no-timeline-list"
  );

  result.drawable.forEach((relation, index) => {
    const from = positions.get(
      `${relation.from.strandId}:${relation.from.eventId}`
    );

    const to = positions.get(
      `${relation.to.strandId}:${relation.to.eventId}`
    );

    if (!from || !to) return;

    const shape = api.connectorGeometry(from, to);

    const path = svgElement("path", {
      d: shape.path,
      class: "no-junction-path"
    });

    overlay.append(path);

    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "no-junction-marker";
    marker.dataset.noRelationship = relation.id;
    marker.textContent = "Link";
    marker.style.left =
      `${shape.midpoint.x / layout.width * 100}%`;
    marker.style.top =
      `${shape.midpoint.y / layout.height * 100}%`;

    marker.setAttribute(
      "aria-label",
      `Inspect documented ${relation.kind} relationship`
    );

    // Relationships are separate historical objects.
    const listButton = document.createElement("button");
    listButton.type = "button";
    listButton.className = "no-timeline-relationship";
    listButton.dataset.noRelationship = relation.id;
    listButton.setAttribute("aria-pressed", "false");

    const listTitle = document.createElement("strong");
    listTitle.textContent =
      `Documented ${relation.kind}`;

    const listDescription = document.createElement("small");
    const eventRecords = new Map(
      model.events.map(item => [item.id, item])
    );

    const fromEvent = eventRecords.get(relation.from.eventId);
    const toEvent = eventRecords.get(relation.to.eventId);

    listDescription.textContent =
      `${fromEvent?.title || relation.from.eventId} → ` +
      `${toEvent?.title || relation.to.eventId}`;

    listButton.append(listTitle, listDescription);

    // Place the relationship beside its historical origin.
    if (eventList) {
      const originDate = fromEvent?.occurredAt || "";
      const following = Array.from(
        eventList.querySelectorAll(
          ".no-timeline-event[data-no-event]"
        )
      ).find(button => {
        const item = eventRecords.get(button.dataset.noEvent);
        return item?.occurredAt > originDate;
      });

      eventList.insertBefore(listButton, following || null);
    }

    const panel = document.createElement("aside");
    panel.className = "no-junction-panel";
    panel.id = `no-junction-detail-${index}`;
    panel.hidden = true;
    panel.setAttribute(
      "aria-label", "Historical relationship evidence"
    );

    panel.style.left =
      `${Math.max(
        20,
        Math.min(80, shape.midpoint.x / layout.width * 100)
      )}%`;

    panel.style.top =
      `${shape.midpoint.y / layout.height * 100}%`;

    const title = document.createElement("strong");
    title.textContent = `Documented ${relation.kind}`;

    const statement = document.createElement("p");
    statement.textContent = relation.statement;

    const details = api.describeRelationship(model, relation);

    const endpoints = document.createElement("p");
    endpoints.className = "no-relationship-endpoints";
    endpoints.textContent =
      `${details.from.title} → ${details.to.title}`;

    const evidence = document.createElement("small");
    evidence.className = "no-relationship-evidence";
    evidence.textContent = details.evidence.map(record =>
      `Source ${record.sourceItemId || "unavailable"} ` +
      `(record ${record.id}; ${record.reviewState})`
    ).join(" · ") + ". Synthetic demonstration only.";

    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Close";
    close.className = "no-junction-close";

    panel.append(title, endpoints, statement, evidence, close);

    marker.setAttribute("aria-controls", panel.id);
    marker.setAttribute("aria-expanded", "false");

    function toggle(open) {
      // The event controller may reconstruct Inspector content.
      // Reattach the relationship panel when necessary.
      if (open && !inspector.contains(panel)) {
        inspector.append(panel);
      }

      panel.hidden = !open;
      inspector.classList.toggle(
        "no-relationship-inspecting", open
      );

      marker.setAttribute("aria-expanded", String(open));
      marker.setAttribute("aria-pressed", String(open));
      marker.classList.toggle("no-junction-active", open);
      listButton.setAttribute("aria-pressed", String(open));
    }

    marker.addEventListener("click", () => {
      const opening = panel.hidden;

      // Only one relationship may be actively inspected.
      closeRelationships(marker);
      toggle(opening);
    });

    close.addEventListener("click", () => {
      toggle(false);
      marker.focus({ preventScroll: true });
    });

    listButton.setAttribute("aria-controls", panel.id);

    // Reuse the existing Link click handler and camera logic.
    listButton.addEventListener("click", () => marker.click());

    relationshipControls.push({
      marker, panel, listButton, toggle
    });
    stage.append(marker);

    // Relationship details now live in the shared Inspector.
    panel.style.removeProperty("left");
    panel.style.removeProperty("top");
    inspector.append(panel);
  });

})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function connectorGeometry(from, to) {
    const direction = to.x >= from.x ? 1 : -1;
    const span = Math.abs(to.x - from.x);
    const bend = Math.max(55, Math.min(140, span * 0.45));

    const first = {
      x: from.x + direction * bend,
      y: from.y
    };

    const second = {
      x: to.x - direction * bend,
      y: to.y
    };

    const midpoint = {
      x: (from.x + 3 * first.x + 3 * second.x + to.x) / 8,
      y: (from.y + 3 * first.y + 3 * second.y + to.y) / 8
    };

    return {
      path:
        `M ${from.x} ${from.y}` +
        ` C ${first.x} ${first.y}` +
        ` ${second.x} ${second.y}` +
        ` ${to.x} ${to.y}`,
      midpoint
    };
  }

  function describeRelationship(model, relation) {
    const events = new Map(
      (model.events || []).map(event => [event.id, event])
    );

    const evidenceRecords = new Map(
      (model.evidence || []).map(record => [
        record.id, record
      ])
    );

    function endpoint(value) {
      const event = events.get(value.eventId);

      return {
        eventId: value.eventId,
        strandId: value.strandId,
        title: event?.title || value.eventId,
        occurredAt: event?.occurredAt || null
      };
    }

    return {
      id: relation.id,
      kind: relation.kind,
      statement: relation.statement,
      from: endpoint(relation.from),
      to: endpoint(relation.to),
      evidence: relation.evidenceIds.map(id => {
        const record = evidenceRecords.get(id);

        return {
          id,
          sourceItemId: record?.sourceItemId || null,
          reviewState: record?.reviewState || "unavailable"
        };
      })
    };
  }

  return Object.freeze({
    connectorGeometry,
    describeRelationship
  });
});
