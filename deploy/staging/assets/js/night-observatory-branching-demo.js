/*
 * C2.2 — Synthetic historical branching fixture.
 *
 * No real history, source connections, or inference.
 * Validation runs relationships BEFORE junction semantics.
 */
(function (root, factory) {
  "use strict";

  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (root) root.ContinuityBranchingDemo = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  function build() {
    const endpoint = (strandId, eventId) => ({
      strandId, eventId
    });

    const event = (id, role, occurredAt, title) => ({
      id,
      role,
      type: role === "decision" ? "Decision" : "Milestone",
      temporalClass: "historical",
      occurredAt,
      title,
      shortTitle: title,
      narrative:
        `Synthetic historical demonstration: ${title}. ` +
        "No real project activity is represented.",
      evidence: "Fictional demonstration record."
    });

    const events = [
      event(
        "pivot", "milestone", "2026-09-18",
        "Project milestone documented"
      ),
      event(
        "research", "milestone", "2026-10-01",
        "Research workstream established"
      ),
      event(
        "operations", "milestone", "2026-10-02",
        "Operations workstream established"
      ),
      event(
        "merge", "decision", "2026-10-10",
        "Joint outcome documented"
      )
    ];

    const strands = [
      {
        id: "primary",
        kind: "historical",
        label: "Primary historical strand",
        eventIds: ["pivot", "merge"]
      },
      {
        id: "research-lane",
        kind: "historical",
        label: "Research workstream",
        eventIds: ["research"]
      },
      {
        id: "operations-lane",
        kind: "historical",
        label: "Operations workstream",
        eventIds: ["operations"]
      }
    ];

    function relationship(id, kind, from, to) {
      return {
        id,
        kind,
        state: "documented",
        from,
        to,
        statement:
          `Fictional documented ${kind} relationship: ` +
          `${from.eventId} to ${to.eventId}.`,
        evidenceIds: [`e-${id}`]
      };
    }

    const relationships = [
      relationship(
        "r-div-research", "divergence",
        endpoint("primary", "pivot"),
        endpoint("research-lane", "research")
      ),
      relationship(
        "r-div-operations", "divergence",
        endpoint("primary", "pivot"),
        endpoint("operations-lane", "operations")
      ),
      relationship(
        "r-con-research", "convergence",
        endpoint("research-lane", "research"),
        endpoint("primary", "merge")
      ),
      relationship(
        "r-con-operations", "convergence",
        endpoint("operations-lane", "operations"),
        endpoint("primary", "merge")
      )
    ];

    const junctions = [
      {
        id: "j-div",
        kind: "divergence",
        state: "documented",
        anchor: endpoint("primary", "pivot"),
        relationshipIds: [
          "r-div-research",
          "r-div-operations"
        ],
        statement:
          "Fictional documented divergence into research " +
          "and operations workstreams.",
        evidenceIds: ["e-j-div"]
      },
      {
        id: "j-con",
        kind: "convergence",
        state: "documented",
        anchor: endpoint("primary", "merge"),
        relationshipIds: [
          "r-con-research",
          "r-con-operations"
        ],
        statement:
          "Fictional documented convergence into a joint outcome.",
        evidenceIds: ["e-j-con"]
      },
      {
        id: "j-shared",
        kind: "shared-milestone",
        state: "documented",
        anchor: endpoint("primary", "pivot"),
        strandIds: ["primary", "research-lane"],
        statement:
          "Fictional evidence claims that this milestone " +
          "is relevant to both named workstreams.",
        evidenceIds: ["e-j-shared"]
      }
    ];

    const relationshipEvidence = relationships.map(item => ({
      id: `e-${item.id}`,
      sourceItemId: `synthetic-source-${item.id}`,
      reviewState: "accepted",
      relationshipIds: [item.id]
    }));

    const junctionEvidence = junctions.map(item => ({
      id: `e-${item.id}`,
      sourceItemId: `synthetic-source-${item.id}`,
      reviewState: "accepted",
      junctionIds: [item.id]
    }));

    return {
      dataset: "synthetic",
      continuity: {
        id: "branching-example",
        title: "Example Continuity — Historical Branching"
      },
      events,
      strands,
      evidence: [
        ...relationshipEvidence,
        ...junctionEvidence
      ],
      relationships,
      junctions
    };
  }

  function evaluate(
    model,
    relationshipValidator,
    junctionValidator
  ) {
    if (
      !relationshipValidator ||
      typeof relationshipValidator.classify !== "function" ||
      !junctionValidator ||
      typeof junctionValidator.classify !== "function"
    ) {
      throw new Error(
        "Both historical validators are required."
      );
    }

    // Crucial ordering: never accept arbitrary relationship
    // claims as eligible junction inputs.
    const relationships = relationshipValidator.classify(model);

    const junctions = junctionValidator.classify(
      model,
      relationships.drawable
    );

    return { relationships, junctions };
  }

  return Object.freeze({ build, evaluate });
});
