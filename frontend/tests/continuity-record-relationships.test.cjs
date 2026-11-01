const test = require('node:test');
const assert = require('node:assert/strict');
const { classify, endpointKey } = require('../assets/js/continuity-record-relationships.js');

const context = { projectId: 'project-a', userId: 'user-a' };
const model = { nodes: [
  { key: 'history:11', kind: 'history', record: { id: 11, project_id: 'project-a' } },
  { key: 'schedule:22', kind: 'schedule', record: { id: 22, project_id: 'project-a' } },
  { key: 'history:33', kind: 'history', record: { id: 33, project_id: 'project-a' } }
] };
function relation(overrides = {}) {
  return {
    id: 'rel-1', projectId: 'project-a', userId: 'user-a',
    kind: 'dependency', state: 'documented',
    from: { type: 'event', id: 11 }, to: { type: 'action', id: 22 },
    statement: 'User confirmed the task depends on this decision',
    proof: { mode: 'user-confirmed', confirmedBy: 'user-a', confirmedAt: '2026-11-01T12:00:00Z' },
    ...overrides
  };
}
function result(r, ctx = context, m = model) { return classify(m, [r], ctx); }

test('an explicit, user-confirmed dependency connects real history to planned work', () => {
  const res = result(relation());
  assert.equal(res.drawable.length, 1);
  assert.equal(res.withheld.length, 0);
  assert.deepEqual([res.drawable[0].fromKey, res.drawable[0].toKey], ['history:11', 'schedule:22']);
});
test('all four kinds are supported when independently documented', () => {
  for (const kind of ['dependency', 'handoff', 'divergence', 'convergence']) {
    assert.equal(result(relation({ kind })).drawable.length, 1);
  }
});
test('same-lane recorded relationships can be shown without fabricated cross-strand rules', () => {
  assert.equal(result(relation({ to: { type: 'event', id: 33 } })).drawable.length, 1);
});
test('empty relationship lists never invent links', () => {
  assert.deepEqual(classify(model, [], context), { drawable: [], withheld: [] });
});
test('proposals are withheld rather than shown as historical facts', () => {
  assert.equal(result(relation({ state: 'proposed' })).withheld[0].reason, 'not-documented');
});
test('unknown kinds are withheld', () => {
  assert.equal(result(relation({ kind: 'similarity' })).drawable.length, 0);
});
test('missing statement is withheld', () => {
  assert.equal(result(relation({ statement: '  ' })).withheld[0].reason, 'missing-statement');
});
test('unconfirmed relations and forged confirmation identity are withheld', () => {
  assert.equal(result(relation({ proof: null })).drawable.length, 0);
  assert.equal(result(relation({ proof: { mode: 'user-confirmed', confirmedBy: 'someone-else', confirmedAt: '2026-11-01' } })).drawable.length, 0);
});
test('cross-project and cross-user relationship rows are withheld', () => {
  assert.equal(result(relation({ projectId: 'project-b' })).withheld[0].reason, 'scope-mismatch');
  assert.equal(result(relation({ userId: 'user-b' })).withheld[0].reason, 'scope-mismatch');
  assert.equal(result(relation(), { userId: '', projectId: 'project-a' }).drawable.length, 0);
});
test('missing, self, invalid, and hidden endpoints never render', () => {
  for (const to of [
    { type: 'action', id: 999 }, { type: 'event', id: 11 },
    { type: 'action', id: 'abc' }, { type: 'source_item', id: 22 }
  ]) {
    assert.equal(result(relation({ to })).withheld[0].reason, 'invalid-or-unavailable-endpoints');
  }
  assert.equal(result(relation(), context, { nodes: [] }).drawable.length, 0);
});
test('source evidence must be accepted, linked, and explicitly referenced', () => {
  const r = relation({ proof: { mode: 'accepted-source', sourceItemIds: ['src-1'] } });
  assert.equal(result(r).drawable.length, 0);
  const acceptedEvidence = [{ sourceItemId: 'src-1', reviewState: 'accepted', relationshipIds: ['rel-1'] }];
  assert.equal(result(r, { ...context, acceptedEvidence }).drawable.length, 1);
  assert.equal(result(r, { ...context, acceptedEvidence: [{ ...acceptedEvidence[0], reviewState: 'pending' }] }).drawable.length, 0);
  assert.equal(result(r, { ...context, acceptedEvidence: [{ ...acceptedEvidence[0], relationshipIds: [] }] }).drawable.length, 0);
  assert.equal(result(relation({ proof: { mode: 'accepted-source', sourceItemIds: ['src-1', 'src-1'] } }), { ...context, acceptedEvidence }).drawable.length, 0);
});
test('duplicate IDs cannot create duplicate rendered links', () => {
  const res = classify(model, [relation(), relation()], context);
  assert.equal(res.drawable.length, 1);
  assert.equal(res.withheld[0].reason, 'invalid-or-duplicate-id');
});
test('unsafe numeric IDs are not accepted', () => {
  assert.equal(endpointKey({ type: 'event', id: Number.MAX_SAFE_INTEGER + 1 }), null);
  assert.equal(endpointKey({ type: 'action', id: '9007199254740993' }), 'schedule:9007199254740993');
});
test('project-specific nodes from other projects are excluded', () => {
  const changed = { nodes: model.nodes.map(n => n.key === 'schedule:22' ?
    { ...n, record: { ...n.record, project_id: 'project-b' } } : n) };
  assert.equal(result(relation(), context, changed).drawable.length, 0);
});
test('classification does not mutate caller records or relationships', () => {
  const input = [relation()];
  const before = JSON.stringify({ model, input, context });
  classify(model, input, context);
  assert.equal(JSON.stringify({ model, input, context }), before);
});
test('invalid relationship collections fail closed', () => {
  assert.throws(() => classify(model, null, context), /array/);
});
