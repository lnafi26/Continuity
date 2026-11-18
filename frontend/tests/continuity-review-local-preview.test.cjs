'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(
  path.join(__dirname, '../assets/js/continuity-live-observatory.js'),
  'utf8'
);

const marker = '/* B4.6d contextual review: local preview, no persistence.';
assert.equal(source.split(marker).length, 2);
const code = marker + source.split(marker)[1];

const PROJECT = '33333333-3333-4333-8333-333333333333';
const FIRST = '1';
const SECOND = '2';

function environment(
  origin = 'http://127.0.0.1:8000',
  backend = 'http://127.0.0.1:8765'
) {
  function element(tag) {
    return {
      tag,
      id: '',
      textContent: '',
      className: '',
      children: [],
      handlers: {},
      attributes: {},
      value: '',
      disabled: false,
      append(...items) { this.children.push(...items); },
      setAttribute(key, value) { this.attributes[key] = value; },
      addEventListener(key, fn) { this.handlers[key] = fn; }
    };
  }

  const shell = element('section');
  shell.id = 'liveObservatory';

  function find(node, id) {
    if (node.id === id) return node;
    for (const child of node.children) {
      const match = find(child, id);
      if (match) return match;
    }
    return null;
  }

  const document = {
    readyState: 'complete',
    createElement: element,
    getElementById(id) { return find(shell, id); },
    addEventListener() {}
  };

  const handlers = {};
  const window = {
    document,
    location: { origin },
    CONTINUITY_MEMORY_API_BASE: backend,
    addEventListener(key, fn) { handlers[key] = fn; }
  };

  vm.runInNewContext(code, { window });

  function flatten(node) {
    return [node, ...node.children.flatMap(flatten)];
  }

  return {
    shell,
    handlers,
    nodes: () => flatten(shell)
  };
}

function selection(env, id = FIRST, title = 'Canvas review') {
  env.handlers['continuity:memory-record-selected']({
    detail: {
      recordId: id,
      recordKind: 'action',
      projectId: PROJECT,
      title
    }
  });
}

test('review UI restricted to exact local preview', () => {
  assert.equal(environment().shell.children.length, 1);
  assert.equal(
    environment('https://example.org').shell.children.length, 0
  );
  assert.equal(
    environment('http://localhost:8000').shell.children.length, 0
  );
  assert.equal(
    environment('http://127.0.0.1:8000',
      'https://example.org').shell.children.length, 0
  );
});

test('no existing proposal can be confirmed', () => {
  const env = environment();
  const buttons = env.nodes().filter(n => n.tag === 'button');
  const text = env.nodes().map(n => n.textContent).join(' ');

  assert.equal(buttons.length, 5);
  assert.ok(buttons.slice(2).every(b => b.disabled));
  assert.match(text, /No persisted proposal/);
  assert.match(text, /Review an existing proposal/);
});

test('record ID, type and project distinguish duplicate titles', () => {
  const env = environment();

  const identity = env.nodes().find(
    n => n.className === 'crrp-identity'
  );
  const draft = env.nodes().find(n => n.tag === 'textarea');

  selection(env, FIRST, 'Same title');
  assert.match(identity.textContent, new RegExp(FIRST));
  assert.match(identity.textContent, /Record type: action/);
  assert.match(identity.textContent, new RegExp(PROJECT));

  draft.value = 'A correction';
  draft.handlers.input();

  selection(env, SECOND, 'Same title');

  assert.match(identity.textContent, new RegExp(SECOND));
  assert.equal(draft.value, '');
});

test('only a meaningful correction can be previewed', () => {
  const env = environment();
  const draft = env.nodes().find(n => n.tag === 'textarea');
  const preview = env.nodes().find(n =>
    n.textContent === 'Preview correction proposal'
  );
  const status = env.nodes().find(n =>
    n.attributes.role === 'status'
  );

  assert.equal(preview.disabled, true);

  selection(env);
  draft.value = 'Canvas review';
  draft.handlers.input();
  assert.equal(preview.disabled, true);

  draft.value = 'Review the updated Canvas';
  draft.handlers.input();
  assert.equal(preview.disabled, false);

  preview.handlers.click();
  assert.match(status.textContent, /No proposal was submitted/);
  assert.match(status.textContent, /nothing was confirmed/);
});

test('invalid record identity fails closed', () => {
  const env = environment();
  const draft = env.nodes().find(n => n.tag === 'textarea');
  const status = env.nodes().find(n =>
    n.attributes.role === 'status'
  );

  selection(env, 'not-a-uuid');

  assert.equal(draft.disabled, true);
  assert.match(status.textContent, /identity unavailable/);
});

test('project refresh or sign-out resets draft', () => {
  const env = environment();
  const draft = env.nodes().find(n => n.tag === 'textarea');

  selection(env);
  draft.value = 'Unsaved private correction';
  draft.handlers.input();

  env.handlers['continuity:memory-review-reset']();

  assert.equal(draft.value, '');
  assert.equal(draft.disabled, true);
});

test('identity survives view-model projection without serialization', () => {
  const mod = require('../assets/js/continuity-live-observatory.js');

  const model = mod.localMemoryPanel.viewModel({
    schema_version: 1,
    kind: 'derived_read_only',
    persisted: false,
    project: { name: 'Test project' },
    recent_events: [{
      id: FIRST,
      title: 'Same title'
    }],
    open_actions: []
  });

  assert.equal(model.historyRecords.length, 1);
  assert.equal(model.historyRecords[0].__review.id, FIRST);
  assert.equal(
    Object.prototype.propertyIsEnumerable.call(
      model.historyRecords[0], '__review'
    ),
    false
  );
  assert.doesNotMatch(
    JSON.stringify(model.historyRecords),
    /__review/
  );
});

test('no network, storage, or HTML injection in review workbench', () => {
  assert.doesNotMatch(
    code,
    /\bfetch\s*\(|\bXMLHttpRequest\b|\blocalStorage\b|\bsessionStorage\b|\binnerHTML\b|sendBeacon/
  );
});


test('BIGINT record identity remains distinct from project UUID', () => {
  const env = environment();
  const draft = env.nodes().find(n => n.tag === 'textarea');
  const identity = env.nodes().find(
    n => n.className === 'crrp-identity'
  );

  selection(env, '9223372036854775807', 'Maximum BIGINT ID');

  assert.equal(draft.disabled, false);
  assert.match(
    identity.textContent,
    /Record ID: 9223372036854775807/
  );
  assert.match(identity.textContent, /Project ID:/);
});

test('malformed, overflowing and UUID record IDs fail closed', () => {
  const invalid = [
    '0',
    '-1',
    '01',
    '1.0',
    '1e3',
    '9223372036854775808',
    '44444444-4444-4444-8444-444444444444'
  ];

  for (const id of invalid) {
    const env = environment();
    const draft = env.nodes().find(n => n.tag === 'textarea');

    selection(env, id);

    assert.equal(draft.disabled, true, id);
  }
});

test('read-only memory model preserves a decimal record ID', () => {
  const mod = require('../assets/js/continuity-live-observatory.js');

  const model = mod.localMemoryPanel.viewModel({
    schema_version: 1,
    kind: 'derived_read_only',
    persisted: false,
    project: { name: 'Read-only test' },
    recent_events: [{ id: '123', title: 'Recorded event' }],
    open_actions: [{ id: '456', title: 'Recorded action' }]
  });

  assert.equal(model.historyRecords[0].__review.id, '123');
  assert.equal(model.actionRecords[0].__review.id, '456');
  assert.equal(model.historyRecords[0].__review.kind, 'event');
  assert.equal(model.actionRecords[0].__review.kind, 'action');
});
