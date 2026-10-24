/*
 * Continuity — Synthetic Multi-Workstream Demonstration
 * No real project data, source access, or inference.
 */
(() => {
  "use strict";

  function buildMulti(base) {
    if (
      !base ||
      base.dataset !== "synthetic" ||
      !Array.isArray(base.events) ||
      !Array.isArray(base.strands)
    ) {
      throw new Error("A synthetic base Timeline is required.");
    }

    return {
      ...base,
      continuity: {
        ...base.continuity,
        title: "Example Continuity — Two Workstreams"
      },
      strands: [
        ...base.strands,
        {
          id: "evidence",
          kind: "historical",
          label: "Evidence processing",
          eventIds: ["evidence-start", "evidence-complete"]
        }
      ],
      events: [
        ...base.events,
        {
          id: "evidence-start",
          role: "milestone",
          type: "Milestone",
          temporalClass: "historical",
          occurredAt: "2026-09-26",
          title: "Evidence review initiated",
          shortTitle: "Evidence review",
          narrative:
            "In this fictional workstream, a team began " +
            "reviewing the traceability of its source records.",
          evidence:
            "Synthetic demonstration record. No real source connected."
        },
        {
          id: "evidence-complete",
          role: "decision",
          type: "Decision",
          temporalClass: "historical",
          occurredAt: "2026-10-06",
          title: "Provenance validation completed",
          shortTitle: "Provenance validated",
          narrative:
            "In this fictional workstream, the team documented " +
            "its decision to accept the reviewed provenance records.",
          evidence:
            "Synthetic demonstration record. This is not " +
            "independent verification of any real project."
        }
      ]
    };
  }

  // Permit deterministic Node tests without accessing browser APIs.
  if (typeof module === "object" && module.exports) {
    module.exports = { buildMulti };
  }

  if (typeof window === "undefined") return;

  const base = window.ContinuityTimelineData;
  if (!base || base.dataset !== "synthetic") return;

  const params = new URLSearchParams(window.location.search);
  const mode = params.get("timeline") === "multi"
    ? "multi"
    : "single";

  if (mode === "multi") {
    window.ContinuityTimelineData = buildMulti(base);
  }

  const model = window.ContinuityTimelineData;
  const view = document.getElementById("view-continuity");
  const list = view?.querySelector(".no-timeline-list");

  if (!view || !list) return;

  const heading = view.querySelector("h1");
  if (heading) heading.textContent = model.continuity.title;

  // Switching scenarios reloads only the standalone preview.
  const selector = document.createElement("div");
  selector.className = "no-demo-mode";
  selector.setAttribute("role", "group");
  selector.setAttribute(
    "aria-label", "Synthetic Timeline scenario"
  );

  for (const [value, label] of [
    ["single", "Single strand"],
    ["multi", "Two workstreams"]
  ]) {
    const link = document.createElement("a");
    const url = new URL(window.location.href);

    url.searchParams.set("timeline", value);
    url.searchParams.set("view", "continuity");
    url.searchParams.delete("event");

    link.href = url.href;
    link.textContent = label;

    // Preserve the current event when switching scenarios.
    link.addEventListener("click", () => {
      const selected = view.querySelector(
        '.no-timeline-event[aria-pressed="true"]'
      )?.dataset.noEvent;

      const destination = new URL(link.href);

      if (selected) {
        destination.searchParams.set("event", selected);
      } else {
        destination.searchParams.delete("event");
      }

      link.href = destination.href;
    });

    if (value === mode) {
      link.setAttribute("aria-current", "page");
    }

    selector.append(link);
  }

  const note = document.createElement("small");
  note.textContent =
    "Switching scenarios reloads the preview. " +
    "Reopen the Example Continuity afterward.";

  selector.append(note);

  view.querySelector(".no-canvas-description")
    ?.after(selector);

  // The alternative event list now uses the same event model
  // as the Canvas and Inspector.
  const listHeading = list.querySelector("h2");
  if (!listHeading) return;

  const eventsById = new Map(
    model.events.map(event => [event.id, event])
  );

  const ordered = model.strands
    .filter(strand => strand.kind === "historical")
    .flatMap(strand =>
      strand.eventIds.map(id => ({
        event: eventsById.get(id),
        strand: strand.label || strand.id
      }))
    )
    .filter(item => item.event)
    .sort((a, b) =>
      a.event.occurredAt.localeCompare(b.event.occurredAt) ||
      a.event.id.localeCompare(b.event.id)
    );

  const buttons = ordered.map(({ event, strand }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "no-timeline-event";
    button.dataset.noEvent = event.id;
    button.setAttribute("aria-pressed", "false");

    const title = document.createElement("strong");
    title.textContent = event.title;

    const details = document.createElement("small");
    const date = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC"
    }).format(new Date(event.occurredAt + "T00:00:00Z"));

    details.textContent = `${date} · ${strand}`;
    button.append(title, details);
    return button;
  });

  list.replaceChildren(listHeading, ...buttons);

  const legend = view.querySelectorAll(
    ".no-canvas-footer span"
  );

  if (legend.length >= 3) {
    legend[2].textContent = mode === "multi"
      ? "Two synthetic historical workstreams"
      : "Primary historical strand";
  }
})();
