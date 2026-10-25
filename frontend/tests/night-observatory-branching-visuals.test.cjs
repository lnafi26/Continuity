const assert = require("node:assert/strict");

const { build, evaluate } = require(
  "../assets/js/night-observatory-branching-demo.js"
);
const relationships = require(
  "../assets/js/night-observatory-relationships.js"
);
const semantics = require(
  "../assets/js/night-observatory-junction-semantics.js"
);
const { plan } = require(
  "../assets/js/night-observatory-timeline-layout.js"
);
const { annotations } = require(
  "../assets/js/night-observatory-branching-visuals.js"
);

const model = build();
const validated = evaluate(
  model, relationships, semantics
);
const layout = plan(model);

const groups = annotations(
  layout, validated.junctions.drawable
);

// Divergence and shared milestone use one actual pivot event.
assert.equal(groups.length, 2);

const pivot = groups.find(x => x.eventId === "pivot");
const merge = groups.find(x => x.eventId === "merge");

assert.ok(pivot);
assert.ok(merge);

assert.deepEqual(
  pivot.items.map(x => x.kind),
  ["divergence", "shared-milestone"]
);

assert.deepEqual(
  merge.items.map(x => x.kind),
  ["convergence"]
);

// All annotations use real, normalized layout positions.
for (const group of groups) {
  assert.ok(group.x >= 0 && group.x <= 1);
  assert.ok(group.y >= 0 && group.y <= 1);
}

// Unaccepted junction evidence removes its annotation.
const pending = build();
pending.evidence.find(
  item => item.id === "e-j-shared"
).reviewState = "pending";

const eligible = evaluate(
  pending, relationships, semantics
);
const filtered = annotations(
  plan(pending), eligible.junctions.drawable
);

assert.equal(
  filtered.find(x => x.eventId === "pivot")
    .items.some(x => x.kind === "shared-milestone"),
  false
);

// No explicit junction: no annotation.
assert.deepEqual(annotations(layout, []), []);

// Rendering plans never add fictional event records.
assert.equal(model.events.length, 4);

console.log("Branching annotation checks passed.");
