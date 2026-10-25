const assert = require("node:assert/strict");

const { classify } = require(
  "../assets/js/night-observatory-junction-semantics.js"
);

function fixture() {
  const point = (id, occurredAt) => ({ id, occurredAt });

  const edge = (id, kind, from, to) => ({
    id, kind, from, to
  });

  return {
    events: [
      point("pivot", "2026-09-18"),
      point("a", "2026-10-01"),
      point("b", "2026-10-02"),
      point("merge", "2026-10-10")
    ],
    strands: [
      {
        id: "primary",
        kind: "historical",
        eventIds: ["pivot", "merge"]
      },
      {
        id: "research",
        kind: "historical",
        eventIds: ["a"]
      },
      {
        id: "operations",
        kind: "historical",
        eventIds: ["b"]
      }
    ],
    evidence: [
      {
        id: "proof-div",
        sourceItemId: "fictional-junction-source-1",
        reviewState: "accepted",
        junctionIds: ["j-div"]
      },
      {
        id: "proof-con",
        sourceItemId: "fictional-junction-source-2",
        reviewState: "accepted",
        junctionIds: ["j-con"]
      },
      {
        id: "proof-shared",
        sourceItemId: "fictional-junction-source-3",
        reviewState: "accepted",
        junctionIds: ["j-shared"]
      }
    ],
    junctions: [
      {
        id: "j-div",
        kind: "divergence",
        state: "documented",
        anchor: {
          strandId: "primary",
          eventId: "pivot"
        },
        relationshipIds: ["r-da", "r-db"],
        statement: "Synthetic documented divergence.",
        evidenceIds: ["proof-div"]
      },
      {
        id: "j-con",
        kind: "convergence",
        state: "documented",
        anchor: {
          strandId: "primary",
          eventId: "merge"
        },
        relationshipIds: ["r-ca", "r-cb"],
        statement: "Synthetic documented convergence.",
        evidenceIds: ["proof-con"]
      },
      {
        id: "j-shared",
        kind: "shared-milestone",
        state: "documented",
        anchor: {
          strandId: "primary",
          eventId: "pivot"
        },
        strandIds: ["primary", "research"],
        statement: "Synthetic shared milestone claim.",
        evidenceIds: ["proof-shared"]
      }
    ],
    eligible: [
      edge(
        "r-da", "divergence",
        { strandId: "primary", eventId: "pivot" },
        { strandId: "research", eventId: "a" }
      ),
      edge(
        "r-db", "divergence",
        { strandId: "primary", eventId: "pivot" },
        { strandId: "operations", eventId: "b" }
      ),
      edge(
        "r-ca", "convergence",
        { strandId: "research", eventId: "a" },
        { strandId: "primary", eventId: "merge" }
      ),
      edge(
        "r-cb", "convergence",
        { strandId: "operations", eventId: "b" },
        { strandId: "primary", eventId: "merge" }
      )
    ]
  };
}

const base = fixture();
const result = classify(base, base.eligible);

// Explicitly documented topology produces three types.
assert.equal(result.drawable.length, 3);
assert.equal(result.withheld.length, 0);

assert.deepEqual(
  result.drawable.map(item => item.kind),
  ["divergence", "convergence", "shared-milestone"]
);

// Divergence and convergence retain their actual branches.
assert.deepEqual(
  result.drawable[0].branches.map(x => x.eventId),
  ["a", "b"]
);

assert.deepEqual(
  result.drawable[1].branches.map(x => x.eventId),
  ["a", "b"]
);

// No explicit junction means no inferred junction.
const empty = fixture();
empty.junctions = [];
assert.equal(classify(empty, empty.eligible).drawable.length, 0);

// Unreviewed evidence prevents junction eligibility.
const unreviewed = fixture();
unreviewed.evidence[0].reviewState = "pending";

assert.equal(
  classify(unreviewed, unreviewed.eligible).withheld[0].reason,
  "evidence-not-accepted-or-unlinked"
);

// An unavailable validated relationship prevents divergence.
const missingLink = fixture();
missingLink.eligible.splice(0, 1);

assert.equal(
  classify(missingLink, missingLink.eligible).drawable.length,
  2
);

// A junction cannot reverse known historical chronology.
const reversed = fixture();
reversed.events[1].occurredAt = "2026-09-01";

assert.equal(
  classify(reversed, reversed.eligible).drawable.filter(
    x => x.kind === "divergence"
  ).length,
  0
);

// A shared milestone must not duplicate a historical event.
const duplicateMember = fixture();
duplicateMember.strands[1].eventIds.push("pivot");

assert.equal(
  classify(
    duplicateMember, duplicateMember.eligible
  ).drawable.filter(x => x.kind === "shared-milestone").length,
  0
);

// Proposed junctions cannot appear as documented history.
const proposed = fixture();
proposed.junctions[0].state = "proposed";

assert.equal(
  classify(proposed, proposed.eligible).drawable.length,
  2
);

// Duplicate junction identities must fail validation.
const duplicate = fixture();
duplicate.junctions.push({ ...duplicate.junctions[0] });

assert.throws(
  () => classify(duplicate, duplicate.eligible),
  /duplicate junction ID/
);

console.log(
  "Historical junction semantic checks passed (9 groups)."
);
