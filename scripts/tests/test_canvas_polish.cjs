'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const canvas = require('../../frontend/assets/js/continuity-live-canvas.js');
const root = path.resolve(__dirname, '../..');

test('Fit frames the left-side strand headings as well as the nodes', () => {
  const model = {nodes: [
    {key: 'history:1', kind: 'history', x: 108, y: 122},
    {key: 'schedule:2', kind: 'schedule', x: 1058, y: 348}
  ]};
  const view = canvas.fitCanvasView(model, 750, 475);
  assert.ok(view.fitsAll);
  assert.ok(34 * view.zoom - view.left >= 0, 'Lane headings must not clip');
  assert.ok(108 * view.zoom - view.left >= 0, 'First node must remain visible');
  assert.ok((1058 + 182) * view.zoom - view.left <= 750,
    'Last node must remain visible');
});

test('New Project form hides task-only and decision-only fields', () => {
  const html = fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8');
  const css = fs.readFileSync(path.join(root, 'frontend/assets/css/styles.css'), 'utf8');
  for (const id of ['manualRecordFields', 'manualDecisionFields', 'manualTaskFields']) {
    assert.match(html, new RegExp(`<div[^>]*id="${id}"[^>]*\\bhidden\\b`));
  }
  assert.match(css, /\.form-grid\[hidden\]\s*,\s*\.form-grid \[hidden\]\s*\{\s*display:\s*none\s*!important;/);
});
