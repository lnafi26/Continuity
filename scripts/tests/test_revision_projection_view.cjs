'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { execFileSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '../..');
const modulePath = path.join(ROOT, 'frontend/assets/js/continuity-revision-history.js');
const { normalizeProjection, renderRevisionHistory } = require(modulePath);
const projection = JSON.parse(execFileSync('python3', [
  path.join(ROOT, 'scripts/revision_projection_fixture.py')
], {
  cwd: ROOT,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  encoding: 'utf8',
  timeout: 10000
}));
const clone = value => JSON.parse(JSON.stringify(value));

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attributes = {};
    this.handlers = {};
    this.textContent = '';
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(type, callback) { this.handlers[type] = callback; }
  click() { this.handlers.click?.(); }
}
const doc = { createElement: tag => new FakeNode(tag) };
function flatten(node) {
  return [node.textContent, ...node.children.flatMap(flatten)].join(' ');
}
function findNodes(node, tag) {
  return [ ...(node.tag === tag ? [node] : []),
    ...node.children.flatMap(child => findNodes(child, tag)) ];
}

test('fixture comes from real synthetic-only Python revision projector', () => {
  assert.equal(projection.kind, 'synthetic_revision_projection');
  assert.equal(projection.persisted, false);
  assert.equal(projection.visible_revisions.length, 4);
  assert.deepEqual(
    projection.visible_revisions.map(row => row.derived_state),
    ['superseded', 'proposed', 'current', 'proposed']
  );
  assert.equal(projection.current_confirmed.id, 'fictional-revision-3');
  assert.deepEqual(projection.open_review_revision_ids, ['fictional-revision-4']);
  assert.equal(projection.has_current_contradictory_evidence, true);
  assert.ok(projection.evidence.every(row => row.evidence_verification === 'not_verified'));
});

test('validated view retains provenance without changing the projection', () => {
  const before = clone(projection);
  const normalized = normalizeProjection(projection);
  assert.equal(normalized.current_id, 'fictional-revision-3');
  assert.equal(normalized.visible_revisions[2].actor_type, 'user');
  assert.equal(normalized.evidence[1].role, 'contradicts');
  assert.deepEqual(projection, before);
});

test('rejects durable, authoritative, mismatched or fabricated flags', () => {
  for (const patch of [
    { persisted: true },
    { kind: 'derived_read_only' },
    { schema_version: 2 },
    { has_current_contradictory_evidence: false }
  ]) assert.throws(() => normalizeProjection({ ...projection, ...patch }));
});

test('rejects forged user confirmation and broken predecessor links', () => {
  const forged = clone(projection);
  forged.visible_revisions[2].actor_type = 'agent';
  assert.throws(() => normalizeProjection(forged));
  const broken = clone(projection);
  broken.visible_revisions[2].supersedes_revision_id = null;
  assert.throws(() => normalizeProjection(broken));
});

test('rejects false verified evidence and unreviewed current selection', () => {
  const forgedEvidence = clone(projection);
  forgedEvidence.evidence[0].evidence_verification = 'verified';
  assert.throws(() => normalizeProjection(forgedEvidence));
  const forgedCurrent = clone(projection);
  forgedCurrent.current_confirmed = forgedCurrent.visible_revisions[3];
  assert.throws(() => normalizeProjection(forgedCurrent));
});

test('renders selectable history with truthful warnings and no HTML injection', () => {
  const container = new FakeNode('container');
  const view = renderRevisionHistory(container, projection, doc);
  assert.equal(view.selectedId, 'fictional-revision-3');
  assert.ok(flatten(container).includes('Demo data only'));
  assert.ok(flatten(container).includes('NOT VERIFIED'));
  const buttons = findNodes(container, 'button');
  assert.equal(buttons.length, 4);
  buttons[3].click();
  assert.equal(view.selectedId, 'fictional-revision-4');
  assert.equal(buttons[3].attributes['aria-pressed'], 'true');
  assert.equal(buttons[2].attributes['aria-pressed'], 'false');
  assert.ok(flatten(container).includes('New fictional proposal'));
  const payload = clone(projection);
  payload.visible_revisions[0].structured_value.decision = '<img src=x onerror=alert(1)>';
  const next = new FakeNode('container');
  renderRevisionHistory(next, payload, doc).select('fictional-revision-1');
  assert.ok(flatten(next).includes('<img src=x onerror=alert(1)>'));
  const source = fs.readFileSync(modulePath, 'utf8');
  assert.ok(!source.includes('innerHTML'));
  assert.ok(!source.includes('localStorage'));
  assert.ok(!source.includes('fetch('));
});

test('module is not included in the live Observatory HTML', () => {
  const index = fs.readFileSync(path.join(ROOT, 'frontend/index.html'), 'utf8');
  assert.ok(!index.includes('continuity-revision-history.js'));
});
