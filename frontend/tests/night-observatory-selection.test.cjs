const assert = require("node:assert/strict");
const { toggleSelection } = require(
  "../assets/js/night-observatory-selection.js"
);

// First click selects an event.
const event = toggleSelection(null, "event", "recovered");
assert.deepEqual(event, {
  kind: "event",
  id: "recovered"
});

// Second click on the same event deselects everything.
assert.equal(
  toggleSelection(event, "event", "recovered"),
  null
);

// Selecting another event replaces the first.
assert.deepEqual(
  toggleSelection(event, "event", "architecture"),
  { kind: "event", id: "architecture" }
);

// Selecting a relationship replaces the event.
const link = toggleSelection(
  event, "relationship", "synthetic-handoff-1"
);

assert.deepEqual(link, {
  kind: "relationship",
  id: "synthetic-handoff-1"
});

// Clicking the same relationship again deselects everything.
assert.equal(
  toggleSelection(link, "relationship", "synthetic-handoff-1"),
  null
);

// A relationship can be replaced directly by an event.
assert.deepEqual(
  toggleSelection(link, "event", "evidence-start"),
  { kind: "event", id: "evidence-start" }
);

// Invalid selections are rejected.
assert.throws(
  () => toggleSelection(null, "unknown", "x"),
  /Invalid selection/
);

assert.throws(
  () => toggleSelection(null, "event", ""),
  /Invalid selection/
);

// Switching event -> relationship -> none must not
// resurrect the previously selected historical event.
let state = null;

state = toggleSelection(state, "event", "recovered");

state = toggleSelection(
  state, "relationship", "synthetic-handoff-1"
);

assert.deepEqual(state, {
  kind: "relationship",
  id: "synthetic-handoff-1"
});

state = toggleSelection(
  state, "relationship", "synthetic-handoff-1"
);

assert.equal(state, null);

state = toggleSelection(
  state, "event", "evidence-start"
);

assert.deepEqual(state, {
  kind: "event",
  id: "evidence-start"
});

state = toggleSelection(
  state, "event", "evidence-start"
);

assert.equal(state, null);

console.log("Selection lifecycle regression checks passed.");

console.log("Unified selection toggle checks passed.");
