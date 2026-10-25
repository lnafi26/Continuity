const assert = require("node:assert/strict");
const { toggleSelection } = require(
  "../assets/js/night-observatory-selection.js"
);
const { build } = require(
  "../assets/js/night-observatory-branching-demo.js"
);
const relationships = require(
  "../assets/js/night-observatory-relationships.js"
);
const semantics = require(
  "../assets/js/night-observatory-junction-semantics.js"
);
const inspection = require(
  "../assets/js/night-observatory-junction-inspection.js"
);
const inspector = require(
  "../assets/js/night-observatory-junction-inspector.js"
);
const { plan } = require(
  "../assets/js/night-observatory-timeline-layout.js"
);
const { annotations } = require(
  "../assets/js/night-observatory-branching-visuals.js"
);

const model = build();
const allowed = inspection.prepare(model, relationships, semantics);
const groups = annotations(plan(model),
  semantics.classify(model, relationships.classify(model).drawable).drawable);
const ids = groups.flatMap(group => group.items.map(item => item.id));
assert.deepEqual(ids, ["j-div", "j-shared", "j-con"]);
for (const id of ids) {
  const item = allowed.find({ kind: "junction", id });
  assert.ok(item);
  assert.ok(inspector.describe(item).sections.length >= 3);
}
let state = toggleSelection(null, "event", "pivot");
state = toggleSelection(state, "junction", "j-div");
assert.deepEqual(state, { kind: "junction", id: "j-div" });
state = toggleSelection(state, "junction", "j-div");
assert.equal(state, null);
state = toggleSelection(state, "junction", "j-shared");
assert.deepEqual(state, { kind: "junction", id: "j-shared" });
state = toggleSelection(state, "relationship", "r-div-research");
assert.equal(state.kind, "relationship");
state = toggleSelection(state, "junction", "j-con");
assert.equal(state.kind, "junction");
assert.equal(toggleSelection(state, "junction", "j-con"), null);
assert.throws(() => toggleSelection(null, "invalid", "x"),
  /Invalid selection/);
const pending = build();
pending.evidence.find(item => item.id === "e-j-shared")
  .reviewState = "pending";
const accepted = inspection.prepare(pending, relationships, semantics);
assert.equal(accepted.find({kind:"junction",id:"j-shared"}), null);
console.log("Unified first-class junction selection checks passed.");
