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

const marker = '/* B4.6b: isolated local-only human-review interaction preview.';
assert.equal(source.split(marker).length, 2);
const code = marker + source.split(marker)[1];

function makeDoc() {
  function element(tag) {
    return {
      tag,
      children: [],
      handlers: {},
      attributes: {},
      textContent: '',
      className: '',
      id: '',
      append(...items) { this.children.push(...items); },
      setAttribute(key, value) { this.attributes[key] = value; },
      addEventListener(name, handler) { this.handlers[name] = handler; }
    };
  }

  const shell = element('section');
  shell.id = 'liveObservatory';

  function find(root, id) {
    if (root.id === id) return root;
    for (const child of root.children) {
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

  return { shell, doc };
}

function flatten(node) {
  return [node, ...node.children.flatMap(flatten)];
}

function run(origin, backend) {
  const { doc, shell } = makeDoc();
  vm.runInNewContext(code, {
    window: {
      location: { origin },
      CONTINUITY_MEMORY_API_BASE: backend,
      document: doc
    }
  });
  return { shell, nodes: flatten(shell) };
}

test('never mounts outside exact local memory preview', () => {
  for (const [origin, backend] of [
    ['https://continuity.example', 'http://127.0.0.1:8765'],
    ['http://127.0.0.1:8000', 'https://example.com'],
    ['http://127.0.0.1:9999', 'http://127.0.0.1:8765'],
    ['http://localhost:8000', 'http://127.0.0.1:8765']
  ]) {
    assert.equal(run(origin, backend).shell.children.length, 0);
  }
});

test('shows fictional comparison and working preview controls', () => {
  const { nodes } = run(
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8765'
  );

  const text = nodes.map(n => n.textContent).join(' ');
  assert.match(text, /FICTIONAL EXAMPLE/);
  assert.match(text, /source not verified/);

  const actions = nodes.filter(n => n.tag === 'button');
  assert.equal(actions.length, 4);

  const status = nodes.find(n => n.attributes.role === 'status');
  assert.ok(status);

  actions[0].handlers.click();
  assert.match(status.textContent, /No confirmation was recorded/);
  assert.match(status.textContent, /revision was saved/);

  actions[1].handlers.click();
  assert.match(status.textContent, /dispute/);

  actions[2].handlers.click();
  assert.match(status.textContent, /reject/);

  actions[3].handlers.click();
  assert.match(status.textContent, /Awaiting your preview choice/);
});

test('prototype contains no network, storage or HTML injection', () => {
  assert.doesNotMatch(
    code,
    /\bfetch\s*\(|\bXMLHttpRequest\b|\blocalStorage\b|\bsessionStorage\b|\binnerHTML\b|sendBeacon/
  );
});
