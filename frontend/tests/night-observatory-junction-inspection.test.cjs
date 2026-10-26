const assert = require("node:assert/strict");

const { build } = require(
  "../assets/js/night-observatory-branching-demo.js"
);
const relationships = require(
  "../assets/js/night-observatory-relationships.js"
);
const semantics = require(
  "../assets/js/night-observatory-junction-semantics.js"
);
const { prepare } = require(
  "../assets/js/night-observatory-junction-inspection.js"
);

const model = build();
const before = JSON.stringify(model);
const result = prepare(model, relationships, semantics);

// 1. Three distinct selectable junction objects.
assert.equal(result.items.length, 3);
assert.deepEqual(
  result.items.map(item => item.selectionKind),
  ["junction", "junction", "junction"]
);

// 2. Each junction retains its own unique identity.
assert.equal(
  new Set(result.items.map(item => item.id)).size,
  3
);

// 3. Divergence refers to the real pivot event.
const divergence = result.find({
  kind: "junction",
  id: "j-div"
});

assert.equal(divergence.anchor.eventId, "pivot");
assert.equal(divergence.occurredAt, "2026-09-18");
assert.equal(divergence.branches.length, 2);

// 4. Convergence has two source branches.
const convergence = result.find({
  kind: "junction",
  id: "j-con"
});

assert.equal(convergence.anchor.eventId, "merge");
assert.equal(convergence.branches.length, 2);
assert.equal(convergence.supportingRelationships.length, 2);

// 5. Shared milestone references two strands and one event.
const shared = result.find({
  kind: "junction",
  id: "j-shared"
});

assert.equal(shared.involvedStrands.length, 2);
assert.equal(shared.anchor.eventId, "pivot");
assert.equal(model.events.length, 4);

// 6. Divergence and shared milestone are distinct objects
// even though they reference the same historical anchor.
assert.notEqual(divergence.id, shared.id);
assert.equal(divergence.anchor.eventId, shared.anchor.eventId);

// 7. Inspection exposes accepted source provenance.
for (const item of result.items) {
  assert.ok(item.supportingEvidence.length > 0);

  for (const proof of item.supportingEvidence) {
    assert.equal(proof.reviewState, "accepted");
    assert.ok(proof.sourceItemId.startsWith("synthetic-source-"));
  }
}

// 8. Only junction selections resolve junction details.
assert.equal(
  result.find({ kind: "event", id: "pivot" }),
  null
);
assert.equal(
  result.find({ kind: "junction", id: "unknown" }),
  null
);
assert.equal(result.find(null), null);

// 9. Withheld evidence cannot produce an inspection item.
const pending = build();

pending.evidence.find(
  item => item.id === "e-j-div"
).reviewState = "pending";

const pendingResult = prepare(
  pending, relationships, semantics
);

assert.equal(
  pendingResult.find({ kind: "junction", id: "j-div" }),
  null
);
assert.equal(pendingResult.withheld.length, 1);

// 10. Unvalidated relationships cannot support a junction.
const unverified = build();

unverified.relationships.find(
  item => item.id === "r-con-operations"
).state = "proposed";

const unverifiedResult = prepare(
  unverified, relationships, semantics
);

assert.equal(
  unverifiedResult.find({ kind: "junction", id: "j-con" }),
  null
);

// 11. No explicit junctions means no inspectable junctions.
const empty = build();
empty.junctions = [];

assert.equal(
  prepare(empty, relationships, semantics).items.length,
  0
);

// 12. Inspection does not alter the historical model.
assert.equal(JSON.stringify(model), before);

console.log(
  "First-class historical junction inspection: 12 checks passed."
);
