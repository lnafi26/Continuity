const test = require('node:test');
const assert = require('node:assert/strict');
const composer = require('../assets/js/continuity-relationship-composer.js');
const canvas = require('../assets/js/continuity-live-canvas.js');
const observatory = require('../assets/js/continuity-live-observatory.js');
const uid = '11111111-1111-4111-8111-111111111111';
const pid = '33333333-3333-4333-8333-333333333333';
const project = () => ({id:pid,user_id:uid,name:'Live project',events:[{id:11,title:'Accepted decision',dateMs:Date.UTC(2026,10,1),type:'Decision'}],actions:[{id:22,title:'Schedule test',dueDate:'2026-11-05'}]});
const records = () => composer.visibleRecords(project(),canvas,observatory);
const selection = () => ({fromKey:'history:11',toKey:'schedule:22',kind:'dependency',statement:'The decision must precede the planned work.',confirmed:true});
function fakeClient({userId=uid,row={},error=null,throwAuth=false,throwWrite=false}={}) {
  let reads=0,writes=[];
  return {
    auth:{ async getUser() { reads++; if(throwAuth) throw Error('offline'); return {data:{user:{id:userId}},error:null}; } },
    from(table) {
      assert.equal(table,'project_record_relationships');
      return { insert(payload){ writes.push(payload); if(throwWrite) throw Error('offline'); return {select(fields){assert.match(fields,/confirmed_by/); return {async single(){return {data:error?null:{id:'44444444-4444-4444-8444-444444444444', user_id:uid,project_id:pid,kind:'dependency',state:'documented',confirmed_by:uid,confirmed_at:'2026-11-01T12:00:00Z', ...row},error};}};}};}};
    },
    writes, get reads(){return reads;}
  };
}

test('lists only actual dated records displayed by the Canvas',()=>{
  assert.deepEqual(records().map(r=>r.key), ['history:11','schedule:22']);
  const p=project();p.actions.push({id:23,title:'No date',dueDate:null});
  assert.equal(composer.visibleRecords(p,canvas,observatory).length,2);
  assert.deepEqual(composer.visibleRecords({},null,observatory),[]);
});
test('explicit confirmation and explanation are mandatory',()=>{
  for(const choice of [{...selection(),confirmed:false},{...selection(),statement:' '},{...selection(),statement:'x'.repeat(2001)}]) {
    assert.ok(composer.prepare(project(),records(),choice).error);
  }
});
test('prevents invalid, duplicate, unsupported and hidden endpoints',()=>{
  for(const choice of [
    {...selection(),fromKey:'schedule:22',toKey:'schedule:22'},
    {...selection(),fromKey:'history:999'},
    {...selection(),kind:'suggestion'}
  ]) assert.ok(composer.prepare(project(),records(),choice).error);
  const p=project();p.canvasRelationshipBundle={relationships:[{kind:'dependency',from:{type:'event',id:11},to:{type:'action',id:22}}]};
  assert.match(composer.prepare(p,records(),selection()).error,/already exists/);
});
test('payload has only permitted INSERT columns and mapped typed endpoints',()=>{
  const r=composer.prepare(project(),records(),selection());
  assert.equal(r.error,undefined);
  assert.deepEqual(r.payload, {project_id:pid,kind:'dependency',statement:selection().statement,from_event_id:11,from_action_id:null,to_event_id:null,to_action_id:22});
  for(const key of ['confirmed_by','confirmed_at','user_id','state','id']) assert.ok(!Object.hasOwn(r.payload,key));
});
test('reverse direction uses typed columns correctly and all four kinds work',()=>{
  for(const kind of ['dependency','handoff','divergence','convergence']) {
    const r=composer.prepare(project(),records(),{...selection(),fromKey:'schedule:22',toKey:'history:11',kind});
    assert.equal(r.error,undefined);
    assert.equal(r.payload.from_action_id,22);assert.equal(r.payload.to_event_id,11);
  }
});
test('no database call is made without explicit confirmation',async()=>{
  const db=fakeClient();
  const r=await composer.save(db,project(),records(),{...selection(),confirmed:false});
  assert.equal(r.ok,false);assert.equal(db.writes.length,0);assert.equal(db.reads,0);
});
test('authenticated user mismatch never inserts',async()=>{
  const db=fakeClient({userId:'22222222-2222-4222-8222-222222222222'});
  const r=await composer.save(db,project(),records(),selection());
  assert.equal(r.ok,false);assert.equal(db.writes.length,0);
});
test('stale selection and account revocation cannot insert',async()=>{
  const db=fakeClient();const r=await composer.save(db,project(),records(),selection(),()=>false);
  assert.equal(r.ok,false);assert.equal(db.writes.length,0);
});
test('successful local API insert verifies server confirmation',async()=>{
  const db=fakeClient();const r=await composer.save(db,project(),records(),selection());
  assert.equal(r.ok,true);assert.equal(r.current,true);assert.equal(db.writes.length,1);
});
test('unverified server metadata is never reported as saved',async()=>{
  for(const row of [{confirmed_by:'other'},{state:'proposed'},{project_id:'wrong'},{confirmed_at:'bogus'}]) {
    const r=await composer.save(fakeClient({row}),project(),records(),selection());
    assert.equal(r.ok,false);
  }
});
test('missing hosted migration, duplicate and offline requests fail gracefully',async()=>{
  for(const error of [{code:'PGRST205'},{code:'23505'}, {code:'42501'}]) {
    const r=await composer.save(fakeClient({error}),project(),records(),selection());assert.equal(r.ok,false);assert.ok(r.message);
  }
  assert.equal((await composer.save(fakeClient({throwAuth:true}),project(),records(),selection())).ok,false);
  assert.equal((await composer.save(fakeClient({throwWrite:true}),project(),records(),selection())).ok,false);
});
test('module mount never inserts on render or dialog open; requires checked submit',async()=>{
  class El {
    constructor(){this.listeners={};this.value='';this.open=false;this.disabled=false;this.checked=false;this.children=[];this.textContent='';}
    addEventListener(type,cb){(this.listeners[type]??=[]).push(cb);}
    async emit(type,evt={}){for(const fn of this.listeners[type]||[]) await fn({preventDefault(){},...evt});}
    replaceChildren(){this.children=[];this.value='';}
    append(child){this.children.push(child);}
    reset(){}
    focus(){}
    showModal(){this.open=true;}
    close(){this.open=false;}
  }
  const ids=['loCreateRelationship','observatoryProjectSelect','loRelationshipDialog','loRelationshipForm','loRelationshipFrom','loRelationshipTo','loRelationshipKind','loRelationshipStatement','loRelationshipConfirmed','loRelationshipSubmit','loRelationshipCancel','loRelationshipStatus'];
  const els=Object.fromEntries(ids.map(id=>[id,new El()]));
  const doc={getElementById:id=>els[id],createElement:()=>new El()};
  const db=fakeClient();let refreshed=0;
  const live={render(p){els.observatoryProjectSelect.value=Object.keys(p)[0]||'';},normalizedRecords:observatory.normalizedRecords};
  const host={ContinuityLiveObservatory:live,ContinuityLiveCanvas:canvas,supabaseDb:db,async refreshProjectData(){refreshed++;}};
  composer.mount(doc,host);
  live.render({[pid]:project()});
  assert.equal(db.writes.length,0);assert.equal(els.loCreateRelationship.disabled,false);
  await els.loCreateRelationship.emit('click');
  assert.equal(db.writes.length,0);assert.equal(els.loRelationshipDialog.open,true);
  els.loRelationshipFrom.value='history:11';els.loRelationshipTo.value='schedule:22';
  els.loRelationshipKind.value='dependency';els.loRelationshipStatement.value=selection().statement;
  await els.loRelationshipForm.emit('submit');
  assert.equal(db.writes.length,0);
  els.loRelationshipConfirmed.checked=true;
  await els.loRelationshipForm.emit('submit');
  assert.equal(db.writes.length,1);assert.equal(refreshed,1);
  live.render({});assert.equal(els.loCreateRelationship.disabled,true);
});
