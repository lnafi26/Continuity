"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const read = rel => fs.readFileSync(
  path.join(root, rel), "utf8"
);

const html = read("night-observatory-preview.html");
const nav = read("assets/js/night-observatory-navigator.js");
const css = read("assets/css/night-observatory-navigator.css");
const shell = read("assets/css/night-observatory-shell.css");

assert.ok(!html.includes('canvas.css">\\n  <link'));
assert.ok(!html.includes('events.js" defer></script>\\n  <script'));
assert.match(html, /This preview uses fictional\s+records;/);
assert.match(nav, /tools\.append\(scenarioControls, navigator\)/);
assert.match(css, /\.no-explore-tools \.no-timeline-navigator\s*\{[^}]*position: static/s);
assert.match(shell, /#view-continuity > \.no-preview-heading/);
assert.match(html, /id="noCanvasViewport"/);
assert.match(html, /id="noEventInspector"/);

console.log("C2 interface layout invariants passed.");
