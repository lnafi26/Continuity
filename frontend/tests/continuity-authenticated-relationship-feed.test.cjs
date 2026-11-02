const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const feed = require('../assets/js/continuity-authenticated-relationship-feed.js');
const boundary = require('../assets/js/continuity-relationship-data-boundary.js');
const visuals = require('../assets/js/continuity-record-relationship-visuals.js');
const contract = require('../assets/js/continuity-record-relationships.js');
const canvas = require('../assets/js/continuity-live-canvas.js');
const observatory = require('../assets/js/continuity-live-observatory.js');
const user = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const pid = '33333333-3333-4333-8333-333333333333';
const project = () => ({
  id: pid, user_id: user, name: 'A real project',
  events: [{ id:11, title:'Approved decision', type:'Decision', dateMs:Date.UTC(2026,10,1) }],
  actions: [{ id:22, title:'Perform work', dueDate:'2026-11-05' }]
});
const relation = () => ({
  id:'44444444-4444-4444-8444-444444444444',
  user_id:user, project_id:pid, kind:'dependency', state:'documented',
  statement:'This decision must precede the scheduled work.',
  from_event_id:11, from_action_id:null, to_event_id:null, to_action_id:22,
  confirmed_by:user, confirmed_at:'2026-11-01T12:00:00Z'
});
function client(result, capture=[]) {
  return { from(table) {
    capture.push(['from', table]);
    return { select(fields) {
      capture.push(['select', fields]);
      return { async eq(key, value) {
        capture.push(['eq',key,value]);
        return result;
      } };
    } };
  } };
}

const view = projectMap => {
  const record = projectMap[pid];
  return visuals.plan(record, canvas.buildCanvasModel(record, observatory.normalizedRecords), contract);
};

test('auth-scoped select can draw one stored, explicitly confirmed relation', async () => {
  const calls=[];
  const original={ [pid]:project() };
  const result=await feed.load(client({data:[relation()],error:null},calls),original,user,boundary);
  assert.deepEqual(calls.map(c=>c[0]),['from','select','eq']);
  assert.equal(calls[0][1],'project_record_relationships');
  assert.deepEqual(calls[2],['eq','user_id',user]);
  assert.match(calls[1][1],/confirmed_by/);
  assert.equal(view(result).links.length,1);
  assert.equal(view(result).links[0].proofMode,'user-confirmed');
  assert.equal(Object.hasOwn(original[pid],'canvasRelationshipBundle'),false);
});

test('missing hosted table fails closed while keeping real project records', async () => {
  for (const code of ['PGRST205','42P01']) {
    const result=await feed.load(client({data:null,error:{code}}),{[pid]:project()},user,boundary);
    assert.equal(result[pid].events.length,1);
    assert.equal(result[pid].actions.length,1);
    assert.equal(view(result).links.length,0);
  }
});

test('network failures and malformed responses cannot reuse stale bundles', async () => {
  const seeded={...project(),canvasRelationshipBundle:{ relationships:[relation()] }};
  for (const db of [
    {from(){ throw Error('offline'); }},
    client({data:null,error:null}),
    client({data:{id:'nonsense'},error:null})
  ]) {
    const oldWarn=console.warn; console.warn=()=>{};
    try {
      const result=await feed.load(db,{[pid]:seeded},user,boundary);
      assert.equal(view(result).links.length,0);
      assert.equal(Object.hasOwn(result[pid],'canvasRelationshipBundle'),false);
    } finally { console.warn=oldWarn; }
  }
  assert.ok(seeded.canvasRelationshipBundle);
});

test('anonymous and missing boundary do not fetch or preserve connections', async () => {
  const original={ [pid]:{...project(),canvasRelationshipBundle:{relationships:[relation()]}} };
  const db={from(){throw Error('query must not execute');}};
  for (const [identity, validator] of [[null,boundary], ['',boundary], [user,null]]) {
    const result=await feed.load(db,original,identity,validator);
    assert.equal(Object.hasOwn(result[pid],'canvasRelationshipBundle'),false);
  }
  assert.ok(original[pid].canvasRelationshipBundle);
});

test('cross-user, cross-project, and unconfirmed rows never draw', async () => {
  for (const patch of [
    {user_id:other}, {confirmed_by:other},
    {project_id:'55555555-5555-4555-8555-555555555555'},
    {confirmed_at:null}, {state:'proposed'}, {from_event_id:99}
  ]) {
    const result=await feed.load(client({data:[{...relation(),...patch}],error:null}),
      {[pid]:project()},user,boundary);
    assert.equal(view(result).links.length,0);
  }
});

test('account switch cannot attach previous-user relationship to new map', async () => {
  const next={ [pid]: {...project(), user_id:other} };
  const result=await feed.load(client({data:[relation()],error:null}),next,other,boundary);
  assert.equal(view(result).links.length,0);
});

test('page loads required boundary and feed ahead of authentication', () => {
  const index=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
  const boundaryPos=index.indexOf('src="assets/js/continuity-relationship-data-boundary.js');
  const feedPos=index.indexOf('src="assets/js/continuity-authenticated-relationship-feed.js');
  const authPos=index.indexOf('src="assets/js/auth.js');
  assert.ok(boundaryPos>0 && feedPos>boundaryPos && authPos>feedPos);
  const auth=fs.readFileSync(path.join(__dirname,'../assets/js/auth.js'),'utf8');
  assert.match(auth, /user_id: p\.user_id === user\.id \? p\.user_id : null/);
  assert.match(auth, /relationshipFeed\.load\(db, projectsById, user\.id,/);
  assert.match(auth, /if \(!sessionIsCurrent\(user\.id, generation\)\) return;\s*\/\/ Build the timeline items/);
  assert.match(auth, /setTimelineData\?\.\(\{ feed, all, projects: projectsWithRelationships \}\)/);
});
