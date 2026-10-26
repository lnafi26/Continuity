/*
 * Continuity — Historical Timeline Data
 * C2.1c demonstration dataset.
 * Fictional examples only. No real ingestion or evidence.
 */
(() => {
  "use strict";

  window.ContinuityTimelineData = {
    dataset: "synthetic",
    continuity: {
      id: "example",
      title: "Example Continuity"
    },
    strands: [
      {
        id: "primary",
        kind: "historical",
        label: "Primary historical strand",
        eventIds: ["recovered", "architecture"]
      }
    ],
    events: [
      {
        id: "recovered",
        role: "milestone",
        type: "Recovered History",
        occurredAt: "2026-09-18",
        discoveredAt: "2026-10-20",
        title: "Earlier milestone discovered",
        shortTitle: "Earlier milestone",
        narrative:
          "This fictional milestone occurred before it was discovered. " +
          "Its historical date remains September 18, while its " +
          "demonstration discovery date is October 20, 2026.",
        evidence:
          "Synthetic recovered record. Historical and discovery dates " +
          "are intentionally separate."
      },
      {
        id: "architecture",
        role: "decision",
        type: "Decision",
        occurredAt: "2026-10-12",
        title: "Architecture decision documented",
        shortTitle: "Architecture decision",
        narrative:
          "In this fictional example, a project team decided to " +
          "keep persistent historical memory separate from its AI " +
          "inference infrastructure.",
        evidence:
          "Synthetic example record. No external evidence is connected."
      }
    ]
  };
})();
