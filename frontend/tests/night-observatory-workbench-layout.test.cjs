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
assert.match(css, /max-width: 1280px/);
assert.match(
  css,
  /grid-template-columns: minmax\(0, 1fr\) minmax\(290px, 340px\)/
);

console.log("C2.3 historical workbench invariants passed.");


// Compact exploration controls and independent Inspector.
const navCss = read("assets/css/night-observatory-navigator.css");

assert.match(
  navCss,
  /C2\.3 compact exploration toolbar/
);

assert.match(
  navCss,
  /grid-template-columns: minmax\(0, 1fr\)/
);

assert.match(
  css,
  /C2\.3 scrollable desktop Inspector/
);

assert.match(
  css,
  /max-height: calc\(100dvh - 40px\)/
);
