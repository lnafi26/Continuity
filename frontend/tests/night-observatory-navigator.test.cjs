const assert = require("node:assert/strict");
const { visibleWindow, mapPoint } = require(
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

console.log("Timeline Navigator geometry checks passed.");
