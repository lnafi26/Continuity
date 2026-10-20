
/*
 * Night Observatory — Event navigation demonstration.
 * Synthetic data only; no network or persistence.
 */
(() => {
  "use strict";

  const model = window.ContinuityTimelineData;
  if (!model || !Array.isArray(model.events)) {
    console.error("Historical event data unavailable.");
    return;
  }

  const records = Object.fromEntries(
    model.events.map(event => [
      event.id,
      {
        title: event.title,
        type: event.type,
        date: new Intl.DateTimeFormat("en-US", {
          month: "long",
          day: "numeric",
          year: "numeric",
          timeZone: "UTC"
        }).format(new Date(event.occurredAt + "T00:00:00Z")),
        narrative: event.narrative,
        evidence: event.evidence
      }
    ])
  );

  const continuity = document.getElementById("view-continuity");
  const inspector = document.getElementById("noEventInspector");
  const eventButtons = [
    ...document.querySelectorAll(".no-timeline-event")
  ];

  function showEvent(id) {
    const record = records[id];
    if (!record || !continuity || !inspector) return;

    const alreadyViewing = !continuity.hidden;

    // Enter the historical workspace only when necessary.
    if (!alreadyViewing) {
      for (const view of document.querySelectorAll(".no-preview-view")) {
        view.hidden = view !== continuity;
      }

      for (const button of document.querySelectorAll(
        ".no-navigation [data-view]"
      )) {
        if (button.dataset.view === "atlas") {
          button.setAttribute("aria-current", "page");
        } else {
          button.removeAttribute("aria-current");
        }
      }
    }

    document.getElementById("noInspectorType").textContent = record.type;
    document.getElementById("noInspectorTitle").textContent = record.title;
    document.getElementById("noInspectorDate").textContent = record.date;
    document.getElementById("noInspectorBody").textContent = record.narrative;
    document.getElementById("noInspectorEvidence").textContent =
      record.evidence;

    for (const button of eventButtons) {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.noEvent === id)
      );
    }

    if (!alreadyViewing) {
      // Cross-view navigation: bring the requested details into view.
      inspector.focus({ preventScroll: true });
      inspector.scrollIntoView({
        behavior: "auto",
        block: "nearest"
      });
    } else if (window.matchMedia("(max-width: 760px)").matches) {
      // Mobile has a vertically stacked Inspector.
      inspector.scrollIntoView({
        behavior: "auto",
        block: "start"
      });
    }

    // Desktop event-to-event selection deliberately never scrolls.
  }

  document.querySelectorAll("[data-no-event]").forEach(button => {
    button.addEventListener("click", () => {
      showEvent(button.dataset.noEvent);
    });
  });

  document.querySelectorAll("[data-no-destination]").forEach(button => {
    button.addEventListener("click", () => {
      const destination = button.dataset.noDestination;
      document.querySelector(
        `.no-navigation [data-view="${destination}"]`
      )?.click();
    });
  });

  document.getElementById("noBackToAtlas")?.addEventListener(
    "click", () => {
      document.querySelector(
        '.no-navigation [data-view="atlas"]'
      )?.click();
    }
  );

  document.getElementById("noBackToCatchup")?.addEventListener(
    "click", () => {
      document.querySelector(
        '.no-navigation [data-view="catchup"]'
      )?.click();
    }
  );
})();
