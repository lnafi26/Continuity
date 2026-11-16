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
    schema_version: 1,
    kind: 'derived_read_only',
    persisted: false,
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

  assert.ok(panel.includes('button.textContent = entry.title'));
  assert.ok(panel.includes("cache: 'no-store'"));
  assert.ok(!panel.includes('innerHTML'));
  assert.ok(!panel.includes('localStorage'));
});


test('memory records retain actual provenance metadata', () => {
  const model = localMemoryPanel.viewModel({
    schema_version: 1,
    kind: 'derived_read_only',
    persisted: false,
    as_of: '2026-11-16T12:00:00Z',
    project: { name: 'QA', summary: 'Existing summary' },
    recent_events: [{
      id: 'event-1',
      title: 'Approved Canvas QA plan',
      type: 'decision',
      occurred_at: '2026-11-02T00:00:00Z',
      source_item_id: null,
      source_link_status: 'no_source',
      evidence_verification: 'not_verified',
      user_edited: true
    }],
    open_actions: [{
      id: 'task-1',
      title: 'Review Canvas visualization',
      status: 'not_started',
      due_date: '2026-11-09'
    }]
  });

  assert.equal(model.historyRecords[0].id, 'event-1');
  assert.equal(model.historyRecords[0].type, 'decision');
  assert.equal(model.historyRecords[0].sourceItemId, '');
  assert.equal(model.historyRecords[0].sourceLinkStatus, 'no_source');
  assert.equal(
    model.historyRecords[0].evidenceVerification,
    'not_verified'
  );
  assert.equal(model.historyRecords[0].userEdited, true);
  assert.equal(model.actionRecords[0].status, 'not_started');
  assert.equal(model.actionRecords[0].dueDate, '2026-11-09');
});

test('unsupported or authoritative memory claims are rejected', () => {
  const context = {
    schema_version: 1,
    kind: 'derived_read_only',
    persisted: false,
    project: {},
    recent_events: [],
    open_actions: []
  };

  assert.throws(() =>
    localMemoryPanel.viewModel({ ...context, persisted: true })
  );

  assert.throws(() =>
    localMemoryPanel.viewModel({
      ...context,
      kind: 'generated_authoritative_memory'
    })
  );

  assert.throws(() =>
    localMemoryPanel.viewModel({ ...context, schema_version: 2 })
  );
});

test('evidence inspector uses selectable plain-text records', () => {
  const contents = fs.readFileSync(source, 'utf8');
  const panel = contents.slice(
    contents.indexOf(
      '/* Continuity: opt-in, local-only Project Memory panel.'
    )
  );

  assert.ok(panel.includes("button.className = 'lo-memory-record'"));
  assert.ok(panel.includes("button.setAttribute('aria-pressed'"));
  assert.ok(panel.includes("content.textContent = value"));
  assert.ok(panel.includes(
    'A source reference or link status does not verify a claim.'
  ));
  assert.ok(!panel.includes('innerHTML'));
});
