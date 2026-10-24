const assert = require("node:assert/strict");
const { buildMulti } = require(
  "../assets/js/night-observatory-multi-demo.js"
);
const { plan } = require(
  "../assets/js/night-observatory-timeline-layout.js"
);

const base = {
  dataset: "synthetic",
  continuity: { id: "example", title: "Example Continuity" },
  events: [
    {
      id: "recovered",
      occurredAt: "2026-09-18",
      role: "milestone"
    },
    {
      id: "architecture",
      occurredAt: "2026-10-12",
      role: "decision"
    }
  ],
  strands: [{
    id: "primary",
    label: "Primary historical strand",
    kind: "historical",
    eventIds: ["recovered", "architecture"]
  }]
};

const multi = buildMulti(base);
const layout = plan(multi);

// Baseline remains unchanged.
assert.equal(base.events.length, 2);
assert.equal(base.strands.length, 1);

// The new fixture has four unique events in two strands.
assert.equal(multi.events.length, 4);
assert.equal(multi.strands.length, 2);
assert.equal(
  new Set(multi.events.map(e => e.id)).size,
  4
);

// Both historical workstreams have two dated nodes.
assert.deepEqual(
  layout.strands.map(s => s.nodes.length),
  [2, 2]
);

// Separate workstreams occupy distinct vertical lanes.
assert.ok(
  layout.strands[1].nodes[0].y >
  layout.strands[0].nodes[0].y
);

// Every node refers to a known event.
const ids = new Set(multi.events.map(e => e.id));
for (const strand of layout.strands) {
  for (const node of strand.nodes) {
    assert.ok(ids.has(node.eventId));
  }
}

// The expanded Canvas requires more vertical space.
assert.ok(layout.height > plan(base).height);
assert.equal(layout.undated.length, 0);
assert.equal(layout.excludedProposalStrands, 0);

console.log("Multi-workstream fixture checks passed.");
