const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizedRecords, validDate } = require('../assets/js/continuity-live-observatory.js');

test('builds chronological recorded history independently from task deadlines', () => {
  const result = normalizedRecords({
    events: [
      { id: 2, title: 'Later decision', dateMs: Date.UTC(2026,10,4), type:'Decision', body: 'Decision detail' },
      { id: 1, title: 'Earlier decision', dateMs: Date.UTC(2026,9,28), type:'Decision' }
    ],
    actions: [{ id: 3, title:'Follow up', dueDate:'2026-11-03', done:false }]
  });
  assert.deepEqual(result.history.map(x=>x.title), ['Earlier decision','Later decision']);
  assert.deepEqual(result.scheduled.map(x=>x.title), ['Follow up']);
  assert.equal(result.history.some(x=>x.kind==='task'),false);
  assert.equal(result.scheduled[0].state,'Open');
});

test('never invents a date for undated tasks or events', () => {
  const result=normalizedRecords({events:[{id:4,title:'Unsure'}],actions:[{id:5,title:'Maybe',dueDate:''}]});
  assert.equal(result.history.length,0);
  assert.equal(result.scheduled.length,0);
  assert.equal(result.unscheduled.length,2);
  assert.ok(result.unscheduled.every(x=>x.date===''));
});

test('invalid calendar dates are not treated as schedules',()=>{
  assert.equal(validDate('2026-02-30'),false);
  assert.equal(validDate('2026-11-03'),true);
  assert.equal(validDate('next Friday'),false);
  const result=normalizedRecords({actions:[{id:9,title:'Bad date',dueDate:'2026-02-30'}]});
  assert.equal(result.scheduled.length,0);
});

test('does not mutate source events or tasks',()=>{
  const p={events:[{id:1,title:'Original',dateMs:Date.UTC(2026,9,31)}],actions:[{id:2,title:'Task',dueDate:'2026-11-03'}]};
  const copy=JSON.parse(JSON.stringify(p));
  normalizedRecords(p);
  assert.deepEqual(p,copy);
});

test('empty and missing user-owned data generate no synthetic events',()=>{
  assert.deepEqual(normalizedRecords({events:[],actions:[]}), {history:[],scheduled:[],unscheduled:[]});
  assert.deepEqual(normalizedRecords(null), {history:[],scheduled:[],unscheduled:[]});
});
