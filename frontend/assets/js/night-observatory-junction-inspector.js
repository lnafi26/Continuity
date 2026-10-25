/*
 * C2.2 — Historical junction Inspector presentation.
 * Accepts only evidence-validated junction inspection data.
 * Does not own selection, camera state, or existing Inspector DOM.
 */
(function (root, factory) {
  "use strict";

  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (root) root.ContinuityJunctionInspector = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function describe(item) {
    if (
      item?.selectionKind !== "junction" ||
      item?.sourceType !== "documented" ||
      !item.id ||
      !item.anchor?.eventId ||
      !Array.isArray(item.supportingEvidence) ||
      item.supportingEvidence.length === 0 ||
      !item.supportingEvidence.every(proof =>
        proof.reviewState === "accepted" &&
        typeof proof.sourceItemId === "string" &&
        proof.sourceItemId.trim()
      )
    ) {
      throw new Error(
        "Documented, validated junction inspection data required."
      );
    }

    const sections = [
      {
        heading: "Historical anchor",
        lines: [
          `${item.anchor.eventTitle} — ${item.occurredAt}`,
          `Workstream: ${item.anchor.strandLabel}`
        ]
      },
      {
        heading: "Involved workstreams",
        lines: item.involvedStrands.map(strand =>
          strand.label
        )
      }
    ];

    if (item.branches.length) {
      sections.push({
        heading: "Historical branches",
        lines: item.branches.map(branch =>
          `${branch.eventTitle} — ${branch.occurredAt} ` +
          `(${branch.strandLabel})`
        )
      });
    }

    if (item.supportingRelationships.length) {
      sections.push({
        heading: "Validated relationships",
        lines: item.supportingRelationships.map(link =>
          `${link.kind}: ${link.from.eventTitle} → ` +
          `${link.to.eventTitle}`
        )
      });
    }

    sections.push({
      heading: "Accepted supporting evidence",
      lines: item.supportingEvidence.map(proof =>
        `${proof.sourceItemId} (${proof.reviewState})`
      )
    });

    return {
      id: item.id,
      kind: item.kind,
      title: item.title,
      statement: item.statement,
      synthetic: item.synthetic === true,
      sections
    };
  }

  function render(container, item) {
    if (!container?.ownerDocument) {
      throw new Error("Inspector container required.");
    }

    const view = describe(item);
    const doc = container.ownerDocument;

    function element(tag, text, className) {
      const node = doc.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    }

    const panel = element(
      "article", undefined, "no-junction-inspector-view"
    );

    panel.setAttribute("data-no-junction-inspection", view.id);

    if (view.synthetic) {
      panel.append(
        element(
          "p",
          "Synthetic demonstration — not real project history",
          "no-junction-inspector-notice"
        )
      );
    }

    panel.append(
      element("h3", view.title),
      element("p", view.statement)
    );

    for (const section of view.sections) {
      const group = element(
        "section", undefined, "no-junction-inspector-section"
      );

      group.append(element("h4", section.heading));

      const list = element("ul");

      for (const line of section.lines) {
        list.append(element("li", line));
      }

      group.append(list);
      panel.append(group);
    }

    // Return a detached panel. The unified selection controller
    // will decide when to attach, hide, or remove it.
    return panel;
  }

  return Object.freeze({ describe, render });
});
