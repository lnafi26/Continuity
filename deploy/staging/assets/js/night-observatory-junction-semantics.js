/*
 * C2.2 — Explicit historical junction semantics.
 * No UI or inference. Input relationships must already have
 * passed the historical relationship validator.
 */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) root.ContinuityJunctionSemantics = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const KINDS = new Set([
    "shared-milestone", "divergence", "convergence"
  ]);

  function uniqueMap(items, label) {
    if (!Array.isArray(items)) {
      throw new Error(label + " must be an array.");
    }

    const map = new Map();

    for (const item of items) {
      if (
        !item ||
        typeof item.id !== "string" ||
        !item.id ||
        map.has(item.id)
      ) {
        throw new Error("Invalid or duplicate " + label + " ID.");
      }
      map.set(item.id, item);
    }

    return map;
  }

  function timestamp(value) {
    if (
      typeof value !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)
    ) {
      return null;
    }

    const time = Date.parse(value + "T00:00:00Z");

    return Number.isFinite(time) &&
      new Date(time).toISOString().slice(0, 10) === value
      ? time
      : null;
  }

  function classify(model, eligibleRelationships) {
    if (!model || !Array.isArray(eligibleRelationships)) {
      throw new Error(
        "Model and validated historical relationships required."
      );
    }

    const events = uniqueMap(model.events, "event");
    const strands = uniqueMap(model.strands, "strand");
    const evidence = uniqueMap(model.evidence || [], "evidence");
    const relations = uniqueMap(
      eligibleRelationships, "eligible relationship"
    );
    const junctions = uniqueMap(model.junctions || [], "junction");

    const drawable = [];
    const withheld = [];

    const endpointValid = endpoint => {
      const strand = strands.get(endpoint?.strandId);
      const event = events.get(endpoint?.eventId);

      return Boolean(
        strand?.kind === "historical" &&
        Array.isArray(strand.eventIds) &&
        strand.eventIds.includes(endpoint.eventId) &&
        event &&
        !["proposal", "planned", "hypothetical"]
          .includes(event.temporalClass) &&
        timestamp(event.occurredAt) !== null
      );
    };

    for (const junction of junctions.values()) {
      const reject = reason =>
        withheld.push({ id: junction.id, reason });

      if (
        !KINDS.has(junction.kind) ||
        junction.state !== "documented"
      ) {
        reject("not-documented-or-unsupported");
        continue;
      }

      if (!endpointValid(junction.anchor)) {
        reject("invalid-historical-anchor");
        continue;
      }

      if (
        typeof junction.statement !== "string" ||
        !junction.statement.trim()
      ) {
        reject("missing-statement");
        continue;
      }

      if (
        !Array.isArray(junction.evidenceIds) ||
        !junction.evidenceIds.length ||
        new Set(junction.evidenceIds).size !==
          junction.evidenceIds.length ||
        !junction.evidenceIds.every(id => {
          const record = evidence.get(id);

          return (
            record?.reviewState === "accepted" &&
            typeof record.sourceItemId === "string" &&
            Boolean(record.sourceItemId.trim()) &&
            Array.isArray(record.junctionIds) &&
            record.junctionIds.includes(junction.id)
          );
        })
      ) {
        reject("evidence-not-accepted-or-unlinked");
        continue;
      }

      const entry = {
        id: junction.id,
        kind: junction.kind,
        anchor: { ...junction.anchor },
        statement: junction.statement,
        evidenceIds: [...junction.evidenceIds]
      };

      if (junction.kind === "shared-milestone") {
        const ids = junction.strandIds;

        if (
          !Array.isArray(ids) ||
          ids.length < 2 ||
          new Set(ids).size !== ids.length ||
          !ids.includes(junction.anchor.strandId) ||
          !ids.every(id =>
            strands.get(id)?.kind === "historical"
          ) ||
          ids.some(id =>
            id !== junction.anchor.strandId &&
            strands.get(id).eventIds?.includes(
              junction.anchor.eventId
            )
          )
        ) {
          reject("invalid-shared-membership");
          continue;
        }

        entry.strandIds = [...ids];
        drawable.push(entry);
        continue;
      }

      const ids = junction.relationshipIds;

      if (
        !Array.isArray(ids) ||
        ids.length < 2 ||
        new Set(ids).size !== ids.length
      ) {
        reject("insufficient-relationship-branches");
        continue;
      }

      const links = ids.map(id => relations.get(id));

      const origin =
        junction.kind === "divergence" ? "from" : "to";

      const destination =
        junction.kind === "divergence" ? "to" : "from";

      const anchorTime = timestamp(
        events.get(junction.anchor.eventId).occurredAt
      );

      const branches = links.map(link => link?.[destination]);

      const eligible = links.every((link, index) => {
        if (!link || link.kind !== junction.kind) return false;

        const common = link[origin];
        const branch = branches[index];

        if (
          common?.eventId !== junction.anchor.eventId ||
          common?.strandId !== junction.anchor.strandId ||
          !endpointValid(branch) ||
          branch.strandId === junction.anchor.strandId
        ) {
          return false;
        }

        const branchTime = timestamp(
          events.get(branch.eventId).occurredAt
        );

        return junction.kind === "divergence"
          ? branchTime >= anchorTime
          : branchTime <= anchorTime;
      });

      if (
        !eligible ||
        new Set(branches.map(x => x?.eventId)).size !==
          branches.length ||
        new Set(branches.map(x => x?.strandId)).size !==
          branches.length
      ) {
        reject("invalid-or-unsupported-branch-topology");
        continue;
      }

      entry.relationshipIds = [...ids];
      entry.branches = branches.map(branch => ({ ...branch }));

      drawable.push(entry);
    }

    return { drawable, withheld };
  }

  return Object.freeze({ classify });
});
