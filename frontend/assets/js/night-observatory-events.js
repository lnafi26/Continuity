
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

  function showEvent(id, { restoringScenario = false } = {}) {
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

    // Scenario restoration must not scroll to the Inspector.
    // The Timeline itself will be revealed after page loading.
    if (restoringScenario) return;

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

  // Open the Canvas from the Atlas without fabricating an event
  // selection or scrolling directly past it to the Inspector.
  document.getElementById("noAtlasOpen")?.addEventListener(
    "click", () => {
      if (!continuity) return;

      for (const section of document.querySelectorAll(
        ".no-preview-view"
      )) {
        section.hidden = section !== continuity;
      }

      for (const navButton of document.querySelectorAll(
        ".no-navigation [data-view]"
      )) {
        if (navButton.dataset.view === "atlas") {
          navButton.setAttribute("aria-current", "page");
        } else {
          navButton.removeAttribute("aria-current");
        }
      }

      continuity.querySelector("h1")?.focus({
        preventScroll: true
      });

      requestAnimationFrame(() => {
        continuity.querySelector(".no-canvas-region")
          ?.scrollIntoView({
            behavior: "auto",
            block: "start"
          });
      });
    }
  );

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

  // Restore the Continuity workspace after scenario switching.
  const entryParams = new URLSearchParams(window.location.search);

  if (entryParams.get("view") === "continuity") {
    const requested = entryParams.get("event");

    // An event in the multi-strand example may not exist
    // in the single-strand example.
    const fallback = Object.hasOwn(records, "architecture")
      ? "architecture"
      : Object.keys(records)[0];

    const selected = requested && Object.hasOwn(records, requested)
      ? requested
      : fallback;

    if (selected) {
      showEvent(selected, { restoringScenario: true });

      const revealTimeline = () => {
        document.querySelector(
          "#view-continuity .no-canvas-region"
        )?.scrollIntoView({
          behavior: "auto",
          block: "start"
        });
      };

      if (document.readyState === "complete") {
        revealTimeline();
      } else {
        window.addEventListener(
          "load",
          revealTimeline,
          { once: true }
        );
      }
    }
  }

})();
