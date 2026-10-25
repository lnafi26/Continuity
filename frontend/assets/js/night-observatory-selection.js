/*
 * Night Observatory — Unified selection coordinator.
 * DOM adapter for the existing event and relationship controllers.
 * No source access, inference, or backend mutations.
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
  const inspector = document.getElementById("noEventInspector");

  if (!view || !stage || !inspector) return;

  const eventSelector =
    ".no-timeline-event[data-no-event]";

  const relationshipSelector = [
    ".no-junction-marker[data-no-relationship]",
    ".no-timeline-relationship[data-no-relationship]",
    ".no-navigator-relationship[data-no-relationship]"
  ].join(", ");

  // List and Navigator relationship controls delegate
  // to the main Link marker.
  const selectableSelector =
    `${eventSelector}, .no-junction-marker[data-no-relationship]`;

  function activeSelection() {
    const activeRelationship = stage.querySelector(
      '.no-junction-marker[aria-pressed="true"]'
    );

    if (activeRelationship) {
      return {
        kind: "relationship",
        id: activeRelationship.dataset.noRelationship
      };
    }

    const activeEvent = view.querySelector(
      '.no-timeline-event[aria-pressed="true"]'
    );

    return activeEvent
      ? {
          kind: "event",
          id: activeEvent.dataset.noEvent
        }
      : null;
  }

  // Canonical selection state.
  let selected = activeSelection();

  function synchronize(selection) {
    // Historical event list and Canvas nodes.
    view.querySelectorAll(eventSelector).forEach(button => {
      const active = Boolean(
        selection?.kind === "event" &&
        selection.id === button.dataset.noEvent
      );

      button.setAttribute("aria-pressed", String(active));
    });

    // Relationship marker, list entry, and miniature arrow.
    view.querySelectorAll(relationshipSelector).forEach(button => {
      const active = Boolean(
        selection?.kind === "relationship" &&
        selection.id === button.dataset.noRelationship
      );

      button.setAttribute("aria-pressed", String(active));

      if (button.classList.contains("no-junction-marker")) {
        button.classList.toggle("no-junction-active", active);
        button.setAttribute("aria-expanded", String(active));
      }
    });

    // A historical event and a relationship may not both
    // own the shared Inspector.
    if (selection?.kind !== "relationship") {
      inspector.classList.remove(
        "no-relationship-inspecting"
      );

      inspector.querySelectorAll(
        ".no-junction-panel"
      ).forEach(panel => {
        panel.hidden = true;
      });
    }
  }

  function activeRelationshipMarker() {
    if (selected?.kind !== "relationship") return null;

    return Array.from(
      stage.querySelectorAll(
        ".no-junction-marker[data-no-relationship]"
      )
    ).find(marker =>
      marker.dataset.noRelationship === selected.id
    ) || null;
  }

  function clearSelection() {
    selected = null;
    synchronize(null);

    // Keep the Event Inspector's original DOM alive.
    // Legacy event handlers may hold references to its children.
    inspector.querySelector(
      ".no-inspector-empty-state"
    )?.remove();

    inspector.classList.add("no-selection-empty");

    const empty = document.createElement("div");
    empty.className = "no-inspector-empty-state";
    empty.setAttribute("role", "status");

    const heading = document.createElement("strong");
    heading.textContent = "Nothing selected";

    const description = document.createElement("p");
    description.textContent =
      "Select a historical event or documented relationship " +
      "to inspect its details and supporting evidence.";

    empty.append(heading, description);
    inspector.append(empty);
  }

  function clickedObject(target) {
    const button = target.closest?.(selectableSelector);

    if (!button || !view.contains(button)) return null;

    if (button.dataset.noEvent) {
      return {
        kind: "event",
        id: button.dataset.noEvent
      };
    }

    if (button.dataset.noRelationship) {
      return {
        kind: "relationship",
        id: button.dataset.noRelationship
      };
    }

    return null;
  }

  // Capture the interaction before the legacy controllers
  // implement their individual click behaviors.
  view.addEventListener("click", event => {
    const current = selected;

    const closeButton = event.target.closest?.(
      ".no-junction-close"
    );

    if (
      closeButton &&
      view.contains(closeButton) &&
      current?.kind === "relationship"
    ) {
      const returnFocus = activeRelationshipMarker();

      event.preventDefault();
      event.stopImmediatePropagation();
      clearSelection();

      returnFocus?.focus({ preventScroll: true });
      return;
    }

    const clicked = clickedObject(event.target);
    if (!clicked) return;

    const next = api.toggleSelection(
      current,
      clicked.kind,
      clicked.id
    );

    selected = next;

    if (next === null) {
      // A second click should NOT invoke the old behavior
      // that restores the previously selected event.
      event.preventDefault();
      event.stopImmediatePropagation();
      clearSelection();
      return;
    }

    // Reveal the preserved Inspector before older controllers
    // populate or update it.
    inspector.classList.remove("no-selection-empty");
    inspector.querySelector(
      ".no-inspector-empty-state"
    )?.remove();

    // Let the existing selection/camera handlers run.
    queueMicrotask(() => {
      synchronize(next);
    });
  }, true);

  // Escape also returns the Inspector to its empty state.
  view.addEventListener("keydown", event => {
    if (event.key !== "Escape" || !selected) return;

    const returnFocus = activeRelationshipMarker();

    event.preventDefault();
    event.stopImmediatePropagation();
    clearSelection();

    returnFocus?.focus({ preventScroll: true });
  }, true);

  // Reflect any event restored by the scenario-switching code.
  root.requestAnimationFrame(() => {
    synchronize(selected);
  });

})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function toggleSelection(current, kind, id) {
    if (
      !["event", "relationship"].includes(kind) ||
      typeof id !== "string" ||
      !id
    ) {
      throw new Error("Invalid selection.");
    }

    if (
      current?.kind === kind &&
      current.id === id
    ) {
      return null;
    }

    return { kind, id };
  }

  return Object.freeze({ toggleSelection });
});
