'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = path.resolve(
  __dirname,
  '../../frontend/assets/js/continuity-live-observatory.js'
);

const { localMemoryPanel } = require(source);

test('local memory panel disabled without explicit configuration', () => {
  assert.equal(localMemoryPanel.enabled({
    location: { origin: 'http://127.0.0.1:8000' }
  }), false);
});

test('local memory panel enabled only for exact trusted origins', () => {
  const base = 'http://127.0.0.1:8765';

  assert.equal(localMemoryPanel.enabled({
    CONTINUITY_MEMORY_API_BASE: base,
    location: { origin: 'http://127.0.0.1:8000' }
  }), true);

  for (const origin of [
    'https://continuity.example',
    'http://localhost:8000',
    'http://127.0.0.1:8001'
  ]) {
    assert.equal(localMemoryPanel.enabled({
      CONTINUITY_MEMORY_API_BASE: base,
      location: { origin }
    }), false);
  }
});

test('memory projection displays only bounded record titles', () => {
  const context = {
    project: { name: 'QA', summary: 'Testing history' },
    recent_events: [
      { title: 'Approved Canvas QA plan' },
      { title: 'Review completed' }
    ],
    open_actions: [
      { title: 'Review Canvas visualization' }
    ]
  };

  const model = localMemoryPanel.viewModel(context);

  assert.equal(model.name, 'QA');
  assert.equal(model.history.length, 2);
  assert.equal(model.actions.length, 1);
  assert.equal(model.actions[0], 'Review Canvas visualization');
});

test('memory projection rejects malformed responses', () => {
  assert.throws(() => localMemoryPanel.viewModel(null));
  assert.throws(() => localMemoryPanel.viewModel([]));
});

test('memory UI does not render backend content as HTML', () => {
  const text = fs.readFileSync(source, 'utf8');
  const panel = text.slice(
    text.indexOf('/* Continuity: opt-in, local-only Project Memory panel.')
  );

  assert.ok(panel.includes('item.textContent = entry'));
  assert.ok(panel.includes("cache: 'no-store'"));
  assert.ok(!panel.includes('innerHTML'));
  assert.ok(!panel.includes('localStorage'));
});
