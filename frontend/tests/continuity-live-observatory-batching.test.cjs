'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const src = fs.readFileSync(
  path.join(__dirname, '..', 'assets', 'js',
    'continuity-live-observatory.js'), 'utf8');

class Node {
  constructor(tag = 'div') {
    this.tagName = tag;
    this.children = [];
    this.listeners = {};
    this.attributes = {};
    this.className = '';
    this.dataset = {};
    this.value = '';
    this.textContent = '';
    this.hidden = false;
    this.style = {};
  }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  addEventListener(k, fn) { this.listeners[k] = fn; }
  click() { this.listeners.click?.({ target: this }); }
  querySelectorAll(selector) {
    return walk(this, n =>
      selector === '.lo-node[aria-pressed="true"]' &&
      n.className.split(' ').includes('lo-node') &&
      n.attributes['aria-pressed'] === 'true');
  }
}

function walk(node, predicate) {
  const found = [];
  function visit(current) {
    if (predicate(current)) found.push(current);
    for (const child of current.children) visit(child);
  }
  visit(node);
  return found;
}

function setup() {
  const names = [
    'liveObservatory', 'observatoryProjectSelect',
    'observatoryCanvas', 'observatoryInspector',
    'observatoryProjectTitle', 'observatoryProjectSummary',
    'observatoryOpenProject', 'observatoryRecordCount'
  ];
  const byId = Object.fromEntries(names.map(k => [k, new Node()]));
  const doc = {
    getElementById: id => byId[id] || null,
    createElement: tag => new Node(tag)
  };
  const root = { document: doc };
  const context = {
    module: { exports: {} }, window: root,
    Date, Number, String, Object, Array, RegExp, Math
  };
  vm.runInNewContext(src, context, { filename: 'observatory.js' });
  return { api: context.module.exports, byId, root };
}

function events(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    title: `Decision ${i + 1}`,
    dateMs: Date.UTC(2026, 0, 1) + i * 86400000
  }));
}

const rows = canvas => walk(canvas, n => n.className === 'lo-node');
const more = canvas => walk(canvas,
  n => n.className.includes('lo-load-earlier'));

test('Timeline reveals older records in bounded batches', () => {
  const { api, byId, root } = setup();
  const projects = {
    P: { id: 'P', name: 'QA', events: events(205), actions: [] }
  };

  api.mount(root.document, root);
  root.ContinuityLiveObservatory.render(projects);

  const canvas = byId.observatoryCanvas;
  assert.equal(rows(canvas).length, 80);
  assert.equal(rows(canvas)[0].children
    .find(n => n.className === 'lo-node-title').textContent,
    'Decision 126');

  const button = more(canvas)[0];
  button.click();
  assert.equal(rows(canvas).length, 160);
  button.click();
  assert.equal(rows(canvas).length, 205);
  assert.equal(button.hidden, true);

  rows(canvas)[0].click();
  assert.equal(
    byId.observatoryInspector.children
      .find(n => n.tagName === 'h3').textContent,
    'Decision 1'
  );
  assert.equal(byId.observatoryRecordCount.textContent, '205 records');
});

test('very large histories generate only 80 initial DOM rows', () => {
  const { api, byId, root } = setup();
  api.mount(root.document, root);

  root.ContinuityLiveObservatory.render({
    P: {
      id: 'P', name: 'Large',
      events: events(200001), actions: []
    }
  });

  const canvas = byId.observatoryCanvas;
  assert.equal(rows(canvas).length, 80);
  assert.equal(byId.observatoryRecordCount.textContent, '200001 records');
  assert.match(more(canvas)[0].textContent, /199921 remaining/);
});

test('changing projects clears previously expanded rows', () => {
  const { api, byId, root } = setup();
  api.mount(root.document, root);

  root.ContinuityLiveObservatory.render({
    A: { id: 'A', name: 'A', events: events(100), actions: [] }
  });

  more(byId.observatoryCanvas)[0].click();
  assert.equal(rows(byId.observatoryCanvas).length, 100);

  root.ContinuityLiveObservatory.render({
    B: { id: 'B', name: 'B', events: events(2), actions: [] }
  });

  assert.equal(rows(byId.observatoryCanvas).length, 2);
  assert.equal(more(byId.observatoryCanvas).length, 0);
});

test('scheduled and undated lanes page independently', () => {
  const { api, byId, root } = setup();
  api.mount(root.document, root);

  const actions = Array.from({ length: 93 }, (_, i) => ({
    id: i + 1, title: `Undated task ${i + 1}`
  }));
  actions.push(...Array.from({ length: 85 }, (_, i) => ({
    id: 1000 + i,
    title: `Scheduled task ${i + 1}`,
    dueDate: '2026-11-02'
  })));

  root.ContinuityLiveObservatory.render({
    P: { id: 'P', name: 'QA', events: events(2), actions }
  });

  const canvas = byId.observatoryCanvas;
  assert.equal(rows(canvas).length, 162);
  assert.equal(more(canvas).length, 2);
  assert.match(more(canvas)[0].textContent, /earlier schedule/);
  assert.match(more(canvas)[1].textContent, /more undated/);

  more(canvas)[1].click();
  assert.equal(rows(canvas).length, 175);
  assert.equal(byId.observatoryRecordCount.textContent, '180 records');
});
