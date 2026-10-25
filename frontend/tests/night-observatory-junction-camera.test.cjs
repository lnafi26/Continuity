const assert = require("node:assert/strict");
const {
  junctionAnchorForClick,
  eventAnchor,
  centerDelta
} = require("../assets/js/night-observatory-camera-focus.js");

// Canvas labels and miniature buttons must focus the actual
// historical anchor group, never the offset text label.
const anchor = {style: {left: "42%", top: "35%"}};
const label = {
  closest(selector) {
    if (selector === ".no-branch-tag[data-no-junction]") return this;
    if (selector === ".no-branch-tags") return anchor;
    return null;
  }
};
const nestedText = {
  closest(selector) {
    return selector === ".no-branch-tag[data-no-junction]"
      ? label : null;
  }
};

assert.equal(junctionAnchorForClick(label), anchor);
assert.equal(junctionAnchorForClick(nestedText), anchor);
assert.equal(junctionAnchorForClick(null), null);
assert.equal(junctionAnchorForClick({closest: () => null}), null);

const historicalPosition = eventAnchor(anchor, {
  left: 100, top: 40, width: 1000, height: 600
});
assert.deepEqual(historicalPosition, {x: 520, y: 250});
assert.deepEqual(centerDelta({
  left: 50, top: 20, width: 600, height: 400
}, historicalPosition), {x: 170, y: 30});

console.log("Historical junction camera delegation checks passed.");
