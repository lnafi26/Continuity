const assert = require("node:assert/strict");

const { buildMulti, buildJunction } = require(
  "../assets/js/night-observatory-multi-demo.js"
);

const { classify } = require(
  "../assets/js/night-observatory-relationships.js"
);

const { plan } = require(
  "../assets/js/night-observatory-timeline-layout.js"
);

const { connectorGeometry, describeRelationship } = require(
  "../assets/js/night-observatory-junctions.js"
);

const base = {
  dataset: "synthetic",
  continuity: { id: "example", title: "Example Continuity" },
  events: [
    { id: "recovered", occurredAt: "2026-09-18", role: "milestone" },
    { id: "architecture", occurredAt: "2026-10-12", role: "decision" }
  ],
  strands: [{
    id: "primary",
    label: "Primary historical strand",
    kind: "historical",
    eventIds: ["recovered", "architecture"]
  }]
};

const multi = buildMulti(base);
const junction = buildJunction(multi);

// Independent history remains independent.
assert.equal(classify(multi).drawable.length, 0);

// Junction scenario adds exactly one explicit relationship.
const accepted = classify(junction);
assert.equal(accepted.drawable.length, 1);
assert.equal(accepted.withheld.length, 0);

// No new fictional event nodes are needed for this connector.
assert.equal(junction.events.length, multi.events.length);
assert.equal(junction.strands.length, multi.strands.length);

// Both endpoints exist in the planned historical layout.
const layout = plan(junction);
const relation = accepted.drawable[0];

function nodeFor(endpoint) {
  return layout.strands
    .find(s => s.id === endpoint.strandId)
    ?.nodes.find(n => n.eventId === endpoint.eventId);
}

const from = nodeFor(relation.from);
const to = nodeFor(relation.to);

assert.ok(from);
assert.ok(to);
assert.notEqual(from.y, to.y);

// Connector geometry is finite and references actual nodes.
const details = describeRelationship(junction, relation);

assert.equal(details.id, "synthetic-handoff-1");
assert.equal(details.kind, "handoff");
assert.equal(details.from.eventId, "recovered");
assert.equal(details.to.eventId, "evidence-start");
assert.equal(details.evidence.length, 1);
assert.equal(
  details.evidence[0].sourceItemId,
  "fictional-source-record-1"
);
assert.equal(
  details.evidence[0].reviewState,
  "accepted"
);

const geometry = connectorGeometry(from, to);

assert.ok(geometry.path.startsWith(`M ${from.x} ${from.y}`));
assert.ok(geometry.path.endsWith(`${to.x} ${to.y}`));
assert.ok(Number.isFinite(geometry.midpoint.x));
assert.ok(Number.isFinite(geometry.midpoint.y));

// A pending source must prevent the link from being drawn.
const pending = JSON.parse(JSON.stringify(junction));
pending.evidence[0].reviewState = "pending";
assert.equal(classify(pending).drawable.length, 0);

// A proposed relationship must also remain outside history.
const proposed = JSON.parse(JSON.stringify(junction));
proposed.relationships[0].state = "proposed";
assert.equal(classify(proposed).drawable.length, 0);

console.log("Synthetic junction and connector checks passed.");
