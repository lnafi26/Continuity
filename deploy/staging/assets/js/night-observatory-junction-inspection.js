/*
 * C2.2 — First-class historical junction inspection data.
 *
 * Junctions remain distinct objects referencing existing events.
 * This module never modifies history or renders unvalidated claims.
 */
(function (root, factory) {
  "use strict";

  const api = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (root) root.ContinuityJunctionInspection = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const titles = Object.freeze({
    divergence: "Documented divergence",
    convergence: "Documented convergence",
    "shared-milestone": "Shared historical milestone"
  });

  function prepare(model, relationshipValidator, junctionValidator) {
    if (
      !model ||
      typeof relationshipValidator?.classify !== "function" ||
      typeof junctionValidator?.classify !== "function"
    ) {
      throw new Error(
        "Historical model and both validators are required."
      );
    }

    // Relationships must pass validation before junctions.
    const relationships = relationshipValidator.classify(model);
    const junctions = junctionValidator.classify(
      model, relationships.drawable
    );

    const events = new Map(
      model.events.map(event => [event.id, event])
    );

    const strands = new Map(
      model.strands.map(strand => [strand.id, strand])
    );

    const evidence = new Map(
      (model.evidence || []).map(item => [item.id, item])
    );

    const eligibleLinks = new Map(
      relationships.drawable.map(link => [link.id, link])
    );

    function describeEndpoint(endpoint) {
      const event = events.get(endpoint.eventId);
      const strand = strands.get(endpoint.strandId);

      if (!event || !strand) {
        throw new Error(
          "Validated junction has an invalid historical endpoint."
        );
      }

      return {
        eventId: event.id,
        eventTitle: event.title || event.id,
        occurredAt: event.occurredAt,
        strandId: strand.id,
        strandLabel: strand.label || strand.id
      };
    }

    const items = junctions.drawable.map(junction => {
      const anchor = describeEndpoint(junction.anchor);

      const branches = (junction.branches || [])
        .map(describeEndpoint);

      const linkedStrandIds =
        junction.kind === "shared-milestone"
          ? junction.strandIds
          : [
              anchor.strandId,
              ...branches.map(item => item.strandId)
            ];

      const involvedStrands = [
        ...new Set(linkedStrandIds)
      ].map(id => {
        const strand = strands.get(id);

        if (!strand) {
          throw new Error("Junction references missing strand.");
        }

        return {
          id,
          label: strand.label || id
        };
      });

      const supportingRelationships =
        (junction.relationshipIds || []).map(id => {
          const relation = eligibleLinks.get(id);

          if (!relation) {
            throw new Error(
              "Junction references unvalidated relationship."
            );
          }

          return {
            id: relation.id,
            kind: relation.kind,
            statement: relation.statement || "",
            from: describeEndpoint(relation.from),
            to: describeEndpoint(relation.to)
          };
        });

      const supportingEvidence =
        junction.evidenceIds.map(id => {
          const record = evidence.get(id);

          if (
            record?.reviewState !== "accepted" ||
            !record.sourceItemId ||
            !record.junctionIds?.includes(junction.id)
          ) {
            throw new Error(
              "Junction evidence has not been validated."
            );
          }

          return {
            id: record.id,
            sourceItemId: record.sourceItemId,
            reviewState: "accepted"
          };
        });

      return {
        id: junction.id,
        selectionKind: "junction",
        kind: junction.kind,
        title: titles[junction.kind],
        statement: junction.statement,
        anchor,
        occurredAt: anchor.occurredAt,
        involvedStrands,
        branches,
        supportingRelationships,
        supportingEvidence,
        sourceType: "documented",
        synthetic: model.dataset === "synthetic"
      };
    });

    const index = new Map(items.map(item => [item.id, item]));

    if (index.size !== items.length) {
      throw new Error("Duplicate inspectable junction identity.");
    }

    return Object.freeze({
      items,
      withheld: [...junctions.withheld],
      relationshipsWithheld: [...relationships.withheld],

      find(selection) {
        if (
          selection?.kind !== "junction" ||
          typeof selection.id !== "string"
        ) {
          return null;
        }

        return index.get(selection.id) || null;
      }
    });
  }

  return Object.freeze({ prepare });
});
