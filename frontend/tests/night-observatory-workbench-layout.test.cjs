"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const read = file => fs.readFileSync(
  path.join(root, file), "utf8"
);

const html = read("night-observatory-preview.html");
const css = read("assets/css/night-observatory-shell.css");

const count = marker => html.split(marker).length - 1;

assert.equal(count('id="noEventInspector"'), 1);
assert.equal(count('id="noCanvasViewport"'), 1);

const workbench = html.indexOf('class="no-workbench"');
const canvas = html.indexOf(
  'class="no-panel no-canvas-region"', workbench
);
const aside = html.indexOf(
  'class="no-workbench-inspector"', canvas
);
const inspector = html.indexOf('id="noEventInspector"', aside);
const list = html.indexOf(
  'class="no-timeline-layout"', inspector
);

assert.ok(workbench >= 0);
assert.ok(workbench < canvas);
assert.ok(canvas < aside);
assert.ok(aside < inspector);
assert.ok(inspector < list);

assert.match(html, /id="noInspectorTitle"/);
assert.match(html, /id="noInspectorEvidence"/);
assert.match(html, /class="no-panel no-timeline-list"/);
assert.match(css, /\.no-workbench\s*\{/);
assert.match(css, /max-width: 1500px/);

console.log("C2.3 historical workbench invariants passed.");
