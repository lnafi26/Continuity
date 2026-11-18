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

const marker =
  '/* B4.6b: isolated local-only human-review interaction preview.';

assert.equal(source.split(marker).length, 2);
const code = marker + source.split(marker)[1];

function environment(
  origin = 'http://127.0.0.1:8000',
  backend = 'http://127.0.0.1:8765'
) {
  function element(tag) {
    return {
      tag, id: '', className: '', textContent: '',
      children: [], handlers: {}, attributes: {},
      value: '', disabled: false,
      append(...items) { this.children.push(...items); },
      setAttribute(k, v) { this.attributes[k] = v; },
      addEventListener(k, v) { this.handlers[k] = v; }
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

  const doc = {
    readyState: 'complete',
    createElement: element,
    getElementById(id) { return find(shell, id); },
    addEventListener() {}
  };

  const handlers = {};
  const host = {
    location: { origin },
    CONTINUITY_MEMORY_API_BASE: backend,
    document: doc,
    addEventListener(name, fn) { handlers[name] = fn; }
  };

  vm.runInNewContext(code, { window: host });

  function flatten(node) {
    return [node, ...node.children.flatMap(flatten)];
  }

  return {
    shell, handlers,
    nodes: () => flatten(shell)
  };
}

test('workbench mounts only in exact local preview', () => {
  assert.equal(environment().shell.children.length, 1);

  for (const [origin, backend] of [
    ['https://continuity.example', 'http://127.0.0.1:8765'],
    ['http://localhost:8000', 'http://127.0.0.1:8765'],
    ['http://127.0.0.1:8000', 'https://example.org']
  ]) {
    assert.equal(
      environment(origin, backend).shell.children.length,
      0
    );
  }
});

test('no fabricated revision appears before selection', () => {
  const env = environment();
  const nodes = env.nodes();
  const text = nodes.map(n => n.textContent).join(' ');
  const draft = nodes.find(n => n.tag === 'textarea');
  const actions = nodes.filter(n => n.tag === 'button');

  assert.match(text, /No memory item selected/);
  assert.match(text, /not revision history/);
  assert.doesNotMatch(text, /Project Cedar/);
  assert.equal(draft.disabled, true);
  assert.ok(actions.slice(0, 3).every(n => n.disabled));
});

test('selection enables a meaningful unsaved draft', () => {
  const env = environment();
  const nodes = env.nodes();
  const draft = nodes.find(n => n.tag === 'textarea');
  const actions = nodes.filter(n => n.tag === 'button');
  const status = nodes.find(n => n.attributes.role === 'status');

  env.handlers['continuity:memory-record-selected']({
    detail: { title: 'Review Canvas visualization' }
  });

  assert.equal(draft.disabled, false);
  assert.equal(actions[0].disabled, true);

  draft.value = 'Review Canvas visualization';
  draft.handlers.input();
  assert.equal(actions[0].disabled, true);

  draft.value = 'Review revised Canvas visualization';
  draft.handlers.input();
  assert.equal(actions[0].disabled, false);

  actions[0].handlers.click();
  assert.match(status.textContent, /No revision was created/);

  actions[1].handlers.click();
  assert.match(status.textContent, /dispute/);

  actions[2].handlers.click();
  assert.match(status.textContent, /reject/);
});

test('switching records and resetting clears drafts', () => {
  const env = environment();
  const draft = env.nodes().find(n => n.tag === 'textarea');
  const actions = env.nodes().filter(n => n.tag === 'button');

  env.handlers['continuity:memory-record-selected']({
    detail: { title: 'First record' }
  });

  draft.value = 'Edited first record';
  draft.handlers.input();

  env.handlers['continuity:memory-record-selected']({
    detail: { title: 'Second record' }
  });

  assert.equal(draft.value, '');
  assert.equal(actions[0].disabled, true);

  env.handlers['continuity:memory-review-reset']();

  assert.equal(draft.disabled, true);
  assert.equal(draft.value, '');
  assert.equal(actions[0].disabled, true);
});

test('selection and reset are wired into authenticated memory panel', () => {
  const before = source.split(marker)[0];

  assert.match(before, /showEvidence\(entry, button\)/);
  assert.match(before, /continuity:memory-record-selected/);
  assert.equal(
    before.split('continuity:memory-review-reset').length - 1,
    2
  );
});

test('prototype has no network, storage or HTML injection', () => {
  assert.doesNotMatch(
    code,
    /\bfetch\s*\(|\bXMLHttpRequest\b|\blocalStorage\b|\bsessionStorage\b|\binnerHTML\b|sendBeacon/
  );
});
