const assert = require("node:assert/strict");
const { plan } = require(
  "../assets/js/night-observatory-timeline-layout.js"
);

const base = {
  events: [
    { id: "oct", occurredAt: "2026-10-12", role: "decision" },
    { id: "sep", occurredAt: "2026-09-18", role: "milestone" }
  ],
  strands: [{
    id: "primary",
    kind: "historical",
    eventIds: ["oct", "sep"]
  }]
};

// 1. Existing historical strand remains chronological.
const first = plan(base);
assert.equal(first.strands.length, 1);
assert.deepEqual(
  first.strands[0].nodes.map(x => x.eventId),
  ["sep", "oct"]
);
assert.match(first.strands[0].path, /^M /);

// 2. Parallel workstreams get separate lanes.
const parallel = plan({
  events: [
    ...base.events,
    { id: "third", occurredAt: "2026-09-20" },
    { id: "future", temporalClass: "proposal" }
  ],
  strands: [
    ...base.strands,
    {
      id: "other",
      kind: "historical",
      eventIds: ["third"]
    },
    {
      id: "possibility",
      kind: "proposal",
      eventIds: ["future"]
    }
  ]
});

assert.equal(parallel.strands.length, 2);
assert.ok(
  parallel.strands[1].nodes[0].y >
  parallel.strands[0].nodes[0].y
);

// 3. Proposals are excluded from historical rendering.
assert.equal(parallel.excludedProposalStrands, 1);
assert.ok(!JSON.stringify(parallel.strands).includes("future"));

// 4. Crowded events receive minimum spacing.
const crowded = plan({
  events: Array.from({ length: 4 }, (_, i) => ({
    id: String(i),
    occurredAt: "2026-10-12"
  })),
  strands: [{
    id: "primary",
    kind: "historical",
    eventIds: ["0", "1", "2", "3"]
  }]
});

for (let i = 1; i < 4; i++) {
  assert.ok(
    crowded.strands[0].nodes[i].x -
    crowded.strands[0].nodes[i - 1].x >= 160
  );
}

// 5. Missing dates are reported, not invented.
const missing = plan({
  events: [{ id: "unknown" }],
  strands: [{
    id: "p",
    kind: "historical",
    eventIds: ["unknown"]
  }]
});

assert.deepEqual(missing.undated, [{
  eventId: "unknown",
  strandId: "p"
}]);

// 6. Unknown event references fail validation.
assert.throws(() => plan({
  events: [],
  strands: [{
    id: "p",
    kind: "historical",
    eventIds: ["absent"]
  }]
}), /Unknown/);

// 7. Impossible historical dates fail validation.
assert.throws(() => plan({
  events: [{ id: "a", occurredAt: "2026-02-30" }],
  strands: [{
    id: "p",
    kind: "historical",
    eventIds: ["a"]
  }]
}), /Invalid/);

// 8. Duplicate membership and proposed historical events fail.
assert.throws(() => plan({
  events: [{ id: "a", occurredAt: "2026-10-12" }],
  strands: [
    { id: "one", kind: "historical", eventIds: ["a"] },
    { id: "two", kind: "historical", eventIds: ["a"] }
  ]
}), /Repeated/);

assert.throws(() => plan({
  events: [{ id: "a", temporalClass: "proposal" }],
  strands: [{
    id: "one",
    kind: "historical",
    eventIds: ["a"]
  }]
}), /Proposed/);

console.log("Historical layout planner: 8 checks passed.");
