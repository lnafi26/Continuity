const test = require('node:test');
const assert = require('node:assert/strict');
const contract = require('../assets/js/continuity-record-relationships.js');
const visuals = require('../assets/js/continuity-record-relationship-visuals.js');
const model = { width: 1200, height: 475, nodes: [
  { key: 'history:11', kind: 'history', x: 108, y: 122,
    record: { id: 11, project_id: 'p1' } },
  { key: 'schedule:22', kind: 'schedule', x: 820, y: 348,
    record: { id: 22, project_id: 'p1' } },
  { key: 'history:33', kind: 'history', x: 400, y: 122,
    record: { id: 33, project_id: 'p1' } }
] };
const r = () => ({ id: 'rel1', userId: 'u1', projectId: 'p1',
  kind: 'dependency', state: 'documented',
  from: { type: 'event', id: 11 }, to: { type: 'action', id: 22 },
  statement: 'Task depends on recorded decision',
  proof: { mode: 'user-confirmed', confirmedBy: 'u1',
    confirmedAt: '2026-11-01T12:00:00Z' }
});
const project = (relationships, overrides={}) => ({
  id: 'p1', user_id: 'u1',
  canvasRelationshipBundle: { projectId: 'p1', userId: 'u1', relationships },
  ...overrides
});

test('ordinary existing projects render zero relationships', () => {
  assert.deepEqual(visuals.plan({id:'p1', user_id:'u1'}, model, contract).links, []);
  assert.deepEqual(visuals.plan(null, model, contract).links, []);
});
test('a documented user-confirmed relationship produces a real path', () => {
  const result = visuals.plan(project([r()]), model, contract);
  assert.equal(result.links.length, 1);
  assert.equal(result.withheld.length, 0);
  assert.match(result.links[0].path, /^M 199 162 C /);
  assert.doesNotMatch(result.links[0].path, /NaN|Infinity/);
});
test('historical same-lane relationships receive curved paths', () => {
  const input = r(); input.to = {type:'event', id:33};
  const result = visuals.plan(project([input]), model, contract);
  assert.equal(result.links.length, 1);
  assert.match(result.links[0].path, /C 199 70, 491 70/);
});
test('every permitted relationship kind has a bounded path', () => {
  for (const kind of ['dependency','handoff','divergence','convergence']) {
    const relationship = {...r(), kind};
    assert.equal(visuals.plan(project([relationship]), model, contract).links[0].kind, kind);
  }
});
test('undocumented, unconfirmed, and out-of-project rows cannot draw', () => {
  assert.equal(visuals.plan(project([{...r(),state:'proposed'}]),model,contract).links.length,0);
  assert.equal(visuals.plan(project([{...r(),proof:null}]),model,contract).links.length,0);
  assert.equal(visuals.plan(project([{...r(),projectId:'p2'}]),model,contract).links.length,0);
});
test('bundle must match actual project and authenticated identity scope', () => {
  const other = project([r()], { id:'p2' });
  assert.deepEqual(visuals.plan(other, model, contract).links, []);
  const altered = project([r()], { user_id:'u2' });
  assert.deepEqual(visuals.plan(altered, model, contract).links, []);
});
test('invalid or missing endpoints have no visible lines', () => {
  const bad = {...r(),to:{type:'action',id:999}};
  assert.equal(visuals.plan(project([bad]),model,contract).links.length,0);
  assert.equal(visuals.plan(project([r()]),{...model,nodes:[]},contract).links.length,0);
});
test('invalid relationships fail closed without throwing in the Canvas', () => {
  assert.deepEqual(visuals.plan(project(null),model,contract).links, []);
  assert.deepEqual(visuals.plan(project([r()]),model,{classify(){throw Error('bad')}}).links, []);
});
test('connection planning does not mutate project, model or input relationships', () => {
  const p=project([r()]); const before=JSON.stringify({p,model});
  visuals.plan(p,model,contract);
  assert.equal(JSON.stringify({p,model}),before);
});
test('render creates safe SVG markup, without inserting relation statements as HTML', () => {
  const items=[];
  const doc={ createElementNS(ns,tag) {
    assert.equal(ns,'http://www.w3.org/2000/svg');
    return {tag,attributes:{},childNodes:[],setAttribute(k,v){this.attributes[k]=v;},append(child){this.childNodes.push(child);}};
  }};
  const stage={ append(el){items.push(el);}};
  const links=visuals.plan(project([r()]),model,contract).links;
  const result=visuals.render(doc,stage,model,links);
  assert.equal(result.tag,'svg');
  assert.equal(result.childNodes.length,1);
  assert.match(result.childNodes[0].attributes.d,/^M /);
  assert.equal(items.length,1);
  assert.equal(visuals.render(doc,stage,model,[]),null);
  assert.equal(items.length,1);
});

test('parallel and reciprocal documented links use stable distinct curves', () => {
  const relation = r();
  const others = [
    {...r(), id: 'rel2', kind: 'handoff'},
    {...r(), id: 'rel3', kind: 'convergence',
      from: {type: 'action', id: 22},
      to: {type: 'event', id: 11}}
  ];
  const all = [relation, ...others];
  const a = visuals.plan(project(all), model, contract).links;
  const b = visuals.plan(project([...all].reverse()), model, contract).links;
  assert.equal(a.length, 3);
  assert.equal(new Set(a.map(link => link.path)).size, 3);
  const byId = links => links.map(link => [link.id, link.path])
    .sort((x, y) => x[0].localeCompare(y[0]));
  assert.deepEqual(byId(a), byId(b));
  assert.equal(
    visuals.plan(project([relation]), model, contract).links[0].path,
    visuals.geometry(model,
      visuals.plan(project([relation]), model, contract).links[0]).path
  );
});

test('parallel curves do not alter an unrelated connection', () => {
  const other = {...r(), id: 'other', to: {type: 'event', id: 33}};
  const alone = visuals.plan(project([other]), model, contract).links[0].path;
  const combined = visuals.plan(
    project([r(), {...r(), id: 'rel2', kind: 'handoff'}, other]),
    model, contract
  ).links;
  assert.equal(combined.find(link => link.id === 'other').path, alone);
});
