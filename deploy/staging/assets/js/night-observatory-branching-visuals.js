/*
 * C2.2 — Evidence-gated historical junction annotations.
 * Annotations do not duplicate or alter historical events.
 */
(function (root, factory) {
  "use strict";

  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (!root?.document) return;

  function mount() {
    const model = root.ContinuityTimelineData;
    if (!model?.junctions?.length) return;

    const stage = document.getElementById("noCanvasStage");
    const mini = document.querySelector(
      "#view-continuity .no-navigator-map"
    );

    const planner = root.ContinuityTimelineLayout;
    const demo = root.ContinuityBranchingDemo;
    const relationships = root.ContinuityHistoricalRelationships;
    const semantics = root.ContinuityJunctionSemantics;

    if (
      !stage || !mini || !planner ||
      !demo || !relationships || !semantics
    ) {
      console.error("Branching Canvas prerequisites are missing.");
      return;
    }

    let groups;
    let result;

    try {
      const layout = planner.plan(model);

      // Claims pass the relationship evidence gate before
      // they are considered for historical junctions.
      result = demo.evaluate(
        model, relationships, semantics
      );

      groups = api.annotations(
        layout, result.junctions.drawable
      );
    } catch (error) {
      console.error(
        "Branching annotation validation failed:", error
      );
      return;
    }

    if (result.junctions.withheld.length) {
      console.info(
        "Some junctions were withheld by historical validation."
      );
    }

    for (const group of groups) {
      // One annotation group per real historical anchor.
      const tagGroup = document.createElement("div");
      tagGroup.className = "no-branch-tags";
      tagGroup.style.left = `${group.x * 100}%`;
      tagGroup.style.top = `${group.y * 100}%`;

      for (const junction of group.items) {
        const tag = document.createElement("button");
        tag.type = "button";
        tag.className = "no-branch-tag";
        tag.dataset.kind = junction.kind;
        tag.dataset.noJunction = junction.id;
        tag.setAttribute("aria-pressed", "false");
        tag.setAttribute("aria-label", `Inspect ${junction.label}`);
        tag.textContent = junction.label;
        tagGroup.append(tag);
      }

      stage.append(tagGroup);

      // Separate, interactive Navigator control for each junction.
      // Only the Canvas control owns selection, so this delegation
      // does not process a click twice.
      const miniTag = document.createElement("div");
      miniTag.className = "no-branch-mini-tag";
      miniTag.style.left = `${group.x * 100}%`;
      miniTag.style.top = `${group.y * 100}%`;

      for (const junction of group.items) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "no-branch-mini-button";
        button.dataset.kind = junction.kind;
        button.dataset.noJunction = junction.id;
        button.setAttribute("aria-pressed", "false");
        button.setAttribute(
          "aria-label", `Inspect ${junction.label} in historical Canvas`
        );
        button.textContent = junction.shortLabel;
        button.addEventListener("click", event => {
          event.stopPropagation();
          const canvasButton = Array.from(stage.querySelectorAll(
            ".no-branch-tag[data-no-junction]"
          )).find(item => item.dataset.noJunction === junction.id);
          canvasButton?.click();
        });
        miniTag.append(button);
      }

      mini.append(miniTag);
    }
  }

  root.document.addEventListener(
    "DOMContentLoaded", mount, { once: true }
  );

})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const labels = Object.freeze({
    divergence: ["Divergence", "D"],
    convergence: ["Convergence", "C"],
    "shared-milestone": ["Shared milestone", "S"]
  });

  function annotations(layout, junctions) {
    if (
      !layout ||
      !Array.isArray(layout.strands) ||
      !Array.isArray(junctions)
    ) {
      throw new Error(
        "Planned strands and validated junctions required."
      );
    }

    const positions = new Map();

    for (const strand of layout.strands) {
      for (const node of strand.nodes) {
        positions.set(
          `${strand.id}:${node.eventId}`, node
        );
      }
    }

    const groups = new Map();

    for (const junction of junctions) {
      const label = labels[junction.kind];
      const anchor = junction.anchor;

      const node = positions.get(
        `${anchor?.strandId}:${anchor?.eventId}`
      );

      // Never fabricate an anchor position.
      if (!label || !node) continue;

      const key =
        `${anchor.strandId}:${anchor.eventId}`;

      if (!groups.has(key)) {
        groups.set(key, {
          strandId: anchor.strandId,
          eventId: anchor.eventId,
          x: node.x / layout.width,
          y: node.y / layout.height,
          items: []
        });
      }

      groups.get(key).items.push({
        id: junction.id,
        kind: junction.kind,
        label: label[0],
        shortLabel: label[1]
      });
    }

    return [...groups.values()];
  }

  return Object.freeze({ annotations });
});
