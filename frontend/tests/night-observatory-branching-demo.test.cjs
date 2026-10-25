const assert = require("node:assert/strict");

const { build, evaluate } = require(
  "../assets/js/night-observatory-branching-demo.js"
);
const relationshipsApi = require(
  "../assets/js/night-observatory-relationships.js"
);
const junctionsApi = require(
  "../assets/js/night-observatory-junction-semantics.js"
);
const layoutApi = require(
  "../assets/js/night-observatory-timeline-layout.js"
);

const model = build();
const result = evaluate(
  model, relationshipsApi, junctionsApi
);

// 1. The fixture is explicitly fictional and independently built.
assert.equal(model.dataset, "synthetic");
assert.equal(model.events.length, 4);
assert.equal(model.strands.length, 3);

// 2. Each historical event exists once in the underlying model.
assert.equal(
  new Set(model.events.map(item => item.id)).size,
  model.events.length
);

// The shared milestone does not duplicate the historical event.
assert.equal(
  model.strands.filter(strand =>
    strand.eventIds.includes("pivot")
  ).length,
  1
);

// 3. All four relationship claims pass the evidence gate.
assert.equal(result.relationships.drawable.length, 4);
assert.equal(result.relationships.withheld.length, 0);

// 4. All three explicit junction claims pass.
assert.equal(result.junctions.drawable.length, 3);
assert.equal(result.junctions.withheld.length, 0);
assert.deepEqual(
  result.junctions.drawable.map(item => item.kind),
  ["divergence", "convergence", "shared-milestone"]
);

// 5. The existing planner can position all historical lanes.
const layout = layoutApi.plan(model);
assert.equal(layout.strands.length, 3);
assert.deepEqual(
  layout.strands.map(strand => strand.nodes.length),
  [2, 1, 1]
);
assert.equal(layout.undated.length, 0);

// 6. Withhold a relationship if its evidence is not accepted.
// The dependent divergence junction must also be withheld.
const pending = JSON.parse(JSON.stringify(model));

pending.evidence.find(item =>
  item.id === "e-r-div-research"
).reviewState = "pending";

const pendingResult = evaluate(
  pending, relationshipsApi, junctionsApi
);

assert.equal(pendingResult.relationships.drawable.length, 3);
assert.equal(
  pendingResult.junctions.drawable.some(item =>
    item.id === "j-div"
  ),
  false
);
assert.equal(
  pendingResult.junctions.drawable.length,
  2
);

// 7. Withhold the convergence if its own evidence is pending.
const pendingJunction = JSON.parse(JSON.stringify(model));

pendingJunction.evidence.find(item =>
  item.id === "e-j-con"
).reviewState = "pending";

const pendingJunctionResult = evaluate(
  pendingJunction, relationshipsApi, junctionsApi
);

assert.equal(
  pendingJunctionResult.relationships.drawable.length,
  4
);
assert.equal(
  pendingJunctionResult.junctions.drawable.some(item =>
    item.id === "j-con"
  ),
  false
);

// 8. Never invent junctions from existing relationships.
const noJunctions = JSON.parse(JSON.stringify(model));
noJunctions.junctions = [];

const noJunctionResult = evaluate(
  noJunctions, relationshipsApi, junctionsApi
);

assert.equal(noJunctionResult.relationships.drawable.length, 4);
assert.equal(noJunctionResult.junctions.drawable.length, 0);

// 9. Proposed relationships do not authorize divergence.
const proposed = JSON.parse(JSON.stringify(model));

proposed.relationships.find(item =>
  item.id === "r-div-operations"
).state = "proposed";

const proposedResult = evaluate(
  proposed, relationshipsApi, junctionsApi
);

assert.equal(proposedResult.relationships.drawable.length, 3);
assert.equal(
  proposedResult.junctions.drawable.some(item =>
    item.id === "j-div"
  ),
  false
);

// 10. The validator does not mutate the original fixture.
assert.equal(model.relationships.length, 4);
assert.equal(model.junctions.length, 3);
assert.equal(
  model.evidence.every(item =>
    item.reviewState === "accepted"
  ),
  true
);

console.log(
  "Synthetic branching validation bridge: 10 checks passed."
);
