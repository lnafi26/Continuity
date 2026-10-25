/*
 * Continuity C2.2 — Historical relationship eligibility.
 * This is a presentation guard, not an authorization system
 * or an automatic verification of historical truth.
 */
(function (root, factory) {
  "use strict";
  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (root) root.ContinuityHistoricalRelationships = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const KINDS = new Set([
    "dependency", "handoff", "divergence", "convergence"
  ]);

  const NONHISTORICAL = new Set([
    "proposal", "planned", "hypothetical"
  ]);

  function indexUnique(items, label) {
    const index = new Map();

    for (const item of items) {
      if (
        !item ||
        typeof item.id !== "string" ||
        !item.id ||
        index.has(item.id)
      ) {
        throw new Error("Invalid or duplicate " + label + " ID.");
      }

      index.set(item.id, item);
    }

    return index;
  }

  function classify(model) {
    if (
      !model ||
      !Array.isArray(model.events) ||
      !Array.isArray(model.strands)
    ) {
      throw new Error("Events and strands are required.");
    }

    const events = indexUnique(model.events, "event");
    const strands = indexUnique(model.strands, "strand");
    const evidence = indexUnique(model.evidence || [], "evidence");

    const relations = model.relationships || [];

    if (!Array.isArray(relations)) {
      throw new Error("Relationships must be an array.");
    }

    indexUnique(relations, "relationship");

    const drawable = [];
    const withheld = [];

    function reject(relation, reason) {
      withheld.push({ id: relation.id, reason });
    }

    function validEndpoint(endpoint) {
      if (!endpoint || typeof endpoint !== "object") {
        return false;
      }

      const event = events.get(endpoint.eventId);
      const strand = strands.get(endpoint.strandId);

      return Boolean(
        event &&
        strand &&
        strand.kind === "historical" &&
        Array.isArray(strand.eventIds) &&
        strand.eventIds.includes(event.id) &&
        !NONHISTORICAL.has(event.temporalClass)
      );
    }

    for (const relation of relations) {
      if (!KINDS.has(relation.kind)) {
        reject(relation, "unsupported-kind");
        continue;
      }

      if (relation.state !== "documented") {
        reject(relation, "not-documented");
        continue;
      }

      if (
        !validEndpoint(relation.from) ||
        !validEndpoint(relation.to) ||
        relation.from.strandId === relation.to.strandId ||
        relation.from.eventId === relation.to.eventId
      ) {
        reject(relation, "invalid-historical-endpoints");
        continue;
      }

      if (
        typeof relation.statement !== "string" ||
        !relation.statement.trim()
      ) {
        reject(relation, "missing-relationship-statement");
        continue;
      }

      if (
        !Array.isArray(relation.evidenceIds) ||
        !relation.evidenceIds.length ||
        new Set(relation.evidenceIds).size !==
          relation.evidenceIds.length
      ) {
        reject(relation, "missing-or-duplicate-evidence");
        continue;
      }

      const fullySupported = relation.evidenceIds.every(id => {
        const record = evidence.get(id);

        return Boolean(
          record &&
          typeof record.sourceItemId === "string" &&
          record.sourceItemId.trim() &&
          record.reviewState === "accepted" &&
          Array.isArray(record.relationshipIds) &&
          record.relationshipIds.includes(relation.id)
        );
      });

      if (!fullySupported) {
        reject(relation, "evidence-not-accepted-or-unlinked");
        continue;
      }

      drawable.push({
        id: relation.id,
        kind: relation.kind,
        from: {
          strandId: relation.from.strandId,
          eventId: relation.from.eventId
        },
        to: {
          strandId: relation.to.strandId,
          eventId: relation.to.eventId
        },
        statement: relation.statement,
        evidenceIds: [...relation.evidenceIds]
      });
    }

    return { drawable, withheld };
  }

  return Object.freeze({ classify });
});
