"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const read = file => fs.readFileSync(
  path.join(root, file), "utf8"
);

const html = read("night-observatory-preview.html");
const js = read("assets/js/night-observatory-events.js");
const css = read("assets/css/night-observatory-shell.css");

assert.match(html, /id="view-atlas"/);
assert.match(html, /id="noAtlasOpen"/);
assert.match(html, /Synthetic demonstration/);
assert.match(html, /No real sources are connected/);
assert.match(js, /getElementById\("noAtlasOpen"\)/);
assert.match(js, /section.hidden = section !== continuity/);
assert.match(js, /\.no-canvas-region/);
assert.match(css, /\.no-atlas-entry/);
assert.match(html, /id="noCanvasViewport"/);
assert.match(html, /id="noEventInspector"/);

console.log("C2 Atlas entry invariants passed.");
