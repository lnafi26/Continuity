'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const canvas = require(path.join(__dirname, '../../frontend/assets/js/continuity-live-canvas.js'));
const inspector = require(path.join(__dirname, '../../frontend/assets/js/continuity-relationship-inspector.js'));

const model = {nodes: [
  {key:'history:1', kind:'history', x:108, y:122, record:{title:'Approved plan'}},
  {key:'schedule:2', kind:'schedule', x:1058, y:348, record:{title:'Review Canvas'}}
]};

test('Fit frames both strands at a practical desktop viewport', () => {
  const result = canvas.fitCanvasView(model, 750, 475);
  assert.ok(result.fitsAll);
  assert.ok(result.zoom < 0.7); // Original minimum 70% cropped the records.
  assert.ok(result.zoom >= 0.25);
  assert.ok(108 * result.zoom - result.left >= 0);
  assert.ok(1240 * result.zoom - result.left <= 750);
  assert.ok(result.top >= 0);
});

test('Fit does not zoom a single node larger than 100%', () => {
  const result = canvas.fitCanvasView({nodes:[model.nodes[0]]}, 1200, 600);
  assert.equal(result.zoom, 1);
});

test('Tiny viewports stay navigable rather than zooming to zero', () => {
  const result = canvas.fitCanvasView(model, 250, 150);
  assert.equal(result.zoom, 0.25);
  assert.equal(result.fitsAll, false);
});

test('Empty/malformed Canvas safely has no framing', () => {
  assert.equal(canvas.fitCanvasView({nodes:[]}, 750, 475), null);
  assert.equal(canvas.fitCanvasView(model, 0, 475), null);
  assert.equal(canvas.fitCanvasView(null, 750, 475), null);
});

test('Inspector offers only explicitly validated links touching selected node', () => {
  const documented = {id:'link-1',kind:'dependency',statement:'Plan requires review',
    proofMode:'user-confirmed',fromKey:'history:1',toKey:'schedule:2'};
  const invalid = {id:'unproven',kind:'dependency',statement:'Unconfirmed',
    proofMode:'unverified',fromKey:'history:1',toKey:'schedule:2'};
  const links = inspector.forRecord([documented,invalid], model, 'history:1');
  assert.equal(links.length, 1);
  assert.equal(links[0].info.toTitle, 'Review Canvas');
  assert.equal(inspector.forRecord([documented], model, 'history:missing').length, 0);
});
