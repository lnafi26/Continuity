const assert = require("node:assert/strict");
const {
  visibleWindow,
  mapPoint,
  eventMarkerSpec
} = require(
  "../assets/js/night-observatory-navigator.js"
);

// Viewport covers the middle portion of a larger Canvas.
assert.deepEqual(
  visibleWindow(
    { left: 0, top: 0, width: 200, height: 100 },
    { left: -200, top: -50, width: 800, height: 400 }
  ),
  {
    left: 0.25,
    top: 0.125,
    width: 0.25,
    height: 0.25
  }
);

// Viewport bounds are clipped to the Canvas.
const clipped = visibleWindow(
  { left: 0, top: 0, width: 200, height: 100 },
  { left: 50, top: 20, width: 100, height: 50 }
);

assert.deepEqual(clipped, {
  left: 0,
  top: 0,
  width: 1,
  height: 1
});

// Click locations normalize to the map.
assert.deepEqual(
  mapPoint(150, 70, {
    left: 50, top: 20, width: 200, height: 100
  }),
  { x: 0.5, y: 0.5 }
);

// Pointer locations outside the map remain bounded.
assert.deepEqual(
  mapPoint(-100, 1000, {
    left: 0, top: 0, width: 200, height: 100
  }),
  { x: 0, y: 1 }
);

const { relationshipOverlays } = require(
  "../assets/js/night-observatory-navigator.js"
);
const { connectorGeometry } = require(
  "../assets/js/night-observatory-junctions.js"
);

const miniLayout = {
  strands: [
    {
      id: "first",
      nodes: [{ eventId: "a", x: 100, y: 150 }]
    },
    {
      id: "second",
      nodes: [{ eventId: "b", x: 400, y: 325 }]
    }
  ]
};

const eligible = [{
  id: "documented-1",
  kind: "handoff",
  from: { strandId: "first", eventId: "a" },
  to: { strandId: "second", eventId: "b" }
}];

const miniLinks = relationshipOverlays(
  miniLayout, eligible, connectorGeometry
);

assert.equal(miniLinks.length, 1);
assert.equal(miniLinks[0].id, "documented-1");
assert.ok(miniLinks[0].path.startsWith("M 100 150"));
assert.ok(Number.isFinite(miniLinks[0].midpoint.x));
assert.ok(Number.isFinite(miniLinks[0].midpoint.y));

assert.equal(
  relationshipOverlays(miniLayout, [], connectorGeometry).length,
  0
);

console.log("Navigator relationship overlay checks passed.");

// Milestones and decisions have distinct Navigator shapes.
const palette = ["#a4c4ff", "#83cddd"];

const milestone = eventMarkerSpec(
  "milestone", 0, palette
);
const decision = eventMarkerSpec(
  "decision", 1, palette
);

assert.deepEqual(milestone, {
  shape: "circle",
  color: "#a4c4ff"
});

assert.deepEqual(decision, {
  shape: "diamond",
  color: "#83cddd"
});

assert.equal(
  eventMarkerSpec("milestone", 2, palette).color,
  "#a4c4ff"
);

console.log("Historical Navigator marker checks passed.");

console.log("Timeline Navigator geometry checks passed.");
