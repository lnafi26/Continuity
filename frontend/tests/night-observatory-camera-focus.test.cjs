const assert = require("node:assert/strict");
const { centerDelta, eventAnchor, gutterSize } = require(
  "../assets/js/night-observatory-camera-focus.js"
);

// Event right of center: move camera right.
assert.deepEqual(
  centerDelta(
    { left: 0, top: 0, width: 800, height: 400 },
    { x: 650, y: 200 }
  ),
  { x: 250, y: 0 }
);

// Event above center: move camera upward.
assert.deepEqual(
  centerDelta(
    { left: 0, top: 0, width: 800, height: 400 },
    { x: 400, y: 50 }
  ),
  { x: 0, y: -150 }
);

// Event already centered: no movement needed.
assert.deepEqual(
  centerDelta(
    { left: 20, top: 40, width: 600, height: 300 },
    { x: 320, y: 190 }
  ),
  { x: 0, y: 0 }
);

// Stage percentages map correctly to screen coordinates.
const fakeNode = {
  style: { left: "75%", top: "25%" }
};

assert.deepEqual(
  eventAnchor(fakeNode, {
    left: 100,
    top: 200,
    width: 1000,
    height: 500
  }),
  { x: 850, y: 325 }
);

// Gutters permit centering nodes at both Canvas boundaries.
assert.deepEqual(
  gutterSize(800, 400),
  { x: 400, y: 200 }
);

assert.deepEqual(
  gutterSize(801, 401),
  { x: 401, y: 201 }
);

const viewportWidth = 800;
const stageWidth = 1000;
const gutter = gutterSize(viewportWidth, 400);

// At the left edge, the desired scroll position is zero.
// At the right edge, it equals the available scroll range.
const totalWidth = stageWidth + gutter.x * 2;
const maxScroll = totalWidth - viewportWidth;

const leftCenter =
  gutter.x - viewportWidth / 2;
const rightCenter =
  gutter.x + stageWidth - viewportWidth / 2;

assert.equal(leftCenter, 0);
assert.equal(rightCenter, maxScroll);

console.log("Event-focused camera geometry checks passed.");
console.log("Camera gutter boundary checks passed.");
