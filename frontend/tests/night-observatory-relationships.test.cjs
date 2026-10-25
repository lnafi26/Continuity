const assert = require("node:assert/strict");
const { classify } = require(
  "../assets/js/night-observatory-relationships.js"
);

function fixture() {
  return {
    dataset: "synthetic",
    events: [
      { id: "first", occurredAt: "2026-09-18" },
      { id: "second", occurredAt: "2026-10-06" }
    ],
    strands: [
      {
        id: "primary",
        kind: "historical",
        eventIds: ["first"]
      },
      {
        id: "evidence",
        kind: "historical",
        eventIds: ["second"]
      }
    ],
    evidence: [{
      id: "proof-1",
      sourceItemId: "fictional-source-record",
      reviewState: "accepted",
      relationshipIds: ["rel-1"]
    }],
    relationships: [{
      id: "rel-1",
      kind: "handoff",
      state: "documented",
      from: { strandId: "primary", eventId: "first" },
      to: { strandId: "evidence", eventId: "second" },
      statement: "Fictional documented handoff.",
      evidenceIds: ["proof-1"]
    }]
  };
}

// 1. An explicitly supported relationship is eligible.
const valid = classify(fixture());
assert.equal(valid.drawable.length, 1);
assert.equal(valid.withheld.length, 0);

// 2. No automatic relationship inference.
const unrelated = fixture();
unrelated.relationships = [];
assert.equal(classify(unrelated).drawable.length, 0);

// 3. Proposed relationships do not enter historical view.
const proposed = fixture();
proposed.relationships[0].state = "proposed";
assert.equal(classify(proposed).drawable.length, 0);

// 4. Disputed relationships are withheld.
const disputed = fixture();
disputed.relationships[0].state = "disputed";
assert.equal(classify(disputed).withheld.length, 1);

// 5. Missing and unreviewed evidence cannot authorize drawing.
const missingEvidence = fixture();
missingEvidence.evidence = [];
assert.equal(classify(missingEvidence).drawable.length, 0);

const unreviewed = fixture();
unreviewed.evidence[0].reviewState = "pending";
assert.equal(classify(unreviewed).drawable.length, 0);

// 6. Evidence must explicitly support the relationship.
const unlinked = fixture();
unlinked.evidence[0].relationshipIds = [];
assert.equal(classify(unlinked).drawable.length, 0);

// 7. Historical endpoints must exist and belong to
// their declared workstreams.
const invalid = fixture();
invalid.relationships[0].to.eventId = "missing";
assert.equal(classify(invalid).drawable.length, 0);

const mismatched = fixture();
mismatched.relationships[0].to.strandId = "primary";
assert.equal(classify(mismatched).drawable.length, 0);

// 8. Proposed events cannot become historical junctions.
const future = fixture();
future.events[1].temporalClass = "proposal";
assert.equal(classify(future).drawable.length, 0);

// 9. Duplicate relationship identities are rejected.
const duplicate = fixture();
duplicate.relationships.push({
  ...duplicate.relationships[0]
});
assert.throws(
  () => classify(duplicate),
  /duplicate relationship ID/
);

console.log("Historical relationship validation: 9 checks passed.");
