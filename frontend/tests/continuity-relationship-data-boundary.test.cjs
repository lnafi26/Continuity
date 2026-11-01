const test = require('node:test');
const assert = require('node:assert/strict');
const boundary = require('../assets/js/continuity-relationship-data-boundary.js');
const contract = require('../assets/js/continuity-record-relationships.js');
const bridge = require('../assets/js/continuity-record-relationship-visuals.js');
const project = () => ({ id: 'p1', user_id: 'u1', name: 'Test project' });
const rows = () => [{
  id: 'rel-1', user_id: 'u1', project_id: 'p1', kind: 'dependency', state: 'documented',
  from_event_id: 11, from_action_id: null, to_event_id: null, to_action_id: 22,
  statement: 'Decision creates a specific dependency', confirmed_by: 'u1',
  confirmed_at: '2026-11-01T12:00:00Z'
}];
const model = { width: 1400, height: 475, nodes: [
  { key:'history:11', kind:'history', x:108, y:122, record:{id:11,project_id:'p1'} },
  { key:'schedule:22', kind:'schedule', x:820, y:348, record:{id:22,project_id:'p1'} }
] };

test('authenticated documented row becomes contract-compatible bundle', () => {
  const result = boundary.attach({p1:project()}, rows(), 'u1');
  assert.equal(result.p1.canvasRelationshipBundle.relationships.length,1);
  assert.equal(bridge.plan(result.p1,model,contract).links.length,1);
});
test('no rows creates no relationship and does not invent proof', () => {
  const result = boundary.attach({p1:project()}, [], 'u1');
  assert.equal(Object.hasOwn(result.p1,'canvasRelationshipBundle'),false);
  assert.equal(bridge.plan(result.p1,model,contract).links.length,0);
});
test('missing authenticated identity and missing project owner fail closed', () => {
  for (const id of ['',null,undefined]) {
    assert.equal(Object.hasOwn(boundary.attach({p1:project()},rows(),id).p1,'canvasRelationshipBundle'),false);
  }
  assert.equal(Object.hasOwn(boundary.attach({p1:{id:'p1'}},rows(),'u1').p1,'canvasRelationshipBundle'),false);
});
test('cross-user and cross-project rows do not attach', () => {
  for (const patch of [{user_id:'u2'},{project_id:'p2'},{confirmed_by:'u2'}]) {
    const result=boundary.attach({p1:project()},[{...rows()[0],...patch}],'u1');
    assert.equal(Object.hasOwn(result.p1,'canvasRelationshipBundle'),false);
  }
});
test('proposals, unsupported kinds, empty statements, and missing confirmations are withheld', () => {
  for (const patch of [{state:'proposed'},{kind:'similarity'},{statement:'  '},
    {confirmed_at:null},{confirmed_at:'not-a-date'},{confirmed_at:'11'}]) {
    const result=boundary.attach({p1:project()},[{...rows()[0],...patch}],'u1');
    assert.equal(Object.hasOwn(result.p1,'canvasRelationshipBundle'),false);
  }
});
test('ambiguous, same-record and unsafe endpoint IDs are excluded', () => {
  for (const patch of [{from_action_id:44},{to_action_id:null},
    {to_event_id:11,to_action_id:null},{from_event_id:9007199254740992},
    {from_event_id:-1}]) {
    const result=boundary.attach({p1:project()},[{...rows()[0],...patch}],'u1');
    assert.equal(Object.hasOwn(result.p1,'canvasRelationshipBundle'),false);
  }
});
test('duplicate relationship identifiers attach at most once', () => {
  const r=rows(); const result=boundary.attach({p1:project()},[...r,...r],'u1');
  assert.equal(result.p1.canvasRelationshipBundle.relationships.length,1);
});
test('stale caller bundles are stripped and inputs remain unchanged', () => {
  const p={...project(),canvasRelationshipBundle:{projectId:'p1',userId:'u1',relationships:[{id:'fake'}]}};
  const source={p1:p}, original=JSON.stringify(source), input=rows(), initial=JSON.stringify(input);
  const result=boundary.attach(source,[], 'u1');
  assert.equal(Object.hasOwn(result.p1,'canvasRelationshipBundle'),false);
  assert.equal(JSON.stringify(source),original);
  assert.equal(JSON.stringify(input),initial);
});
test('does not classify source similarity as project causation', () => {
  const sourceItem={...rows()[0], kind:'similarity', source_item_id:'src-a'};
  assert.equal(Object.hasOwn(boundary.attach({p1:project()},[sourceItem],'u1').p1,'canvasRelationshipBundle'),false);
});
