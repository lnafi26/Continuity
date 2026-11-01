const test = require('node:test');
const assert = require('node:assert/strict');
const { buildCanvasModel, navigatorMarkers, adjacentNode } = require('../assets/js/continuity-live-canvas.js');
const { normalizedRecords } = require('../assets/js/continuity-live-observatory.js');

const model = project => buildCanvasModel(project, normalizedRecords);

test('real history and planned deadlines have separate Canvas strands', () => {
  const data = model({
    events: [{ id: 1, title: 'Decide', type: 'Decision', dateMs: Date.UTC(2026,9,31) }],
    actions: [{ id: 2, title: 'Ship', dueDate: '2026-11-03' }]
  });
  assert.equal(data.nodes.length, 2);
  assert.deepEqual(data.nodes.map(n => n.kind), ['history','schedule']);
  assert.equal(data.nodes[0].record.type, 'Decision');
  assert.equal(data.nodes[1].record.type, 'Task deadline');
  assert.notEqual(data.nodes[0].y, data.nodes[1].y);
  assert.deepEqual(data.links, []);
});

test('never invents causal relationships or fabricated branches', () => {
  const data = model({ events: [
    { id: 5, dateMs: Date.UTC(2026,9,28), title: 'First' },
    { id: 6, dateMs: Date.UTC(2026,10,2), title: 'Second' }
  ] });
  assert.deepEqual(data.links, []);
  assert.ok(data.nodes[1].x > data.nodes[0].x);
});

test('undated tasks are counted without receiving positions', () => {
  const data = model({ actions: [{id:3,title:'No due date',dueDate:''}] });
  assert.equal(data.nodes.length, 0);
  assert.equal(data.undatedCount, 1);
  assert.equal(data.earliest, null);
});

test('empty and missing projects show no synthetic history', () => {
  assert.deepEqual(model(null).nodes, []);
  assert.deepEqual(model({events:[], actions:[]}).nodes, []);
});

test('user records are not modified by Canvas layout', () => {
  const source = {events:[{id:7,title:'Unchanged',dateMs:Date.UTC(2026,10,1)}],actions:[{id:9,title:'Task',dueDate:'2026-11-02'}]};
  const before = JSON.parse(JSON.stringify(source));
  model(source);
  assert.deepEqual(source, before);
});

test('large event lists disclose truncation, with bounded Canvas rendering', () => {
  const events = Array.from({length:90}, (_,i) => ({id:i,title:'E'+i,dateMs:Date.UTC(2026,9,1+i)}));
  const data = model({events});
  assert.equal(data.nodes.length, 80);
  assert.equal(data.truncated.history,10);
  assert.equal(data.truncated.schedule,0);
});


test('navigator positions use real dated records only', () => {
  const data = model({events:[{id:1,title:'A',dateMs:Date.UTC(2026,9,31)}],actions:[{id:2,title:'B',dueDate:'2026-11-03'},{id:3,title:'No deadline'}]});
  const marks = navigatorMarkers(data);
  assert.equal(marks.length,2);
  assert.deepEqual(marks.map(m=>m.key),['history:1','schedule:2']);
  assert.ok(marks.every(m => m.position >=0 && m.position<=100));
  assert.equal(marks.some(m=>m.title==='No deadline'),false);
});

test('navigator traverses real events in deterministic spatial order', () => {
  const data = model({events:[{id:1,title:'Early',dateMs:Date.UTC(2026,9,30)},{id:2,title:'Late',dateMs:Date.UTC(2026,10,5)}],actions:[{id:3,title:'Intermediate deadline',dueDate:'2026-11-02'}]});
  assert.equal(adjacentNode(data,null,1).key,'history:1');
  assert.equal(adjacentNode(data,null,-1).key,'history:2');
  assert.equal(adjacentNode(data,'history:1',1).key,'schedule:3');
  assert.equal(adjacentNode(data,'schedule:3',1).key,'history:2');
  assert.equal(adjacentNode(data,'history:2',1).key,'history:1');
  assert.equal(adjacentNode(data,'history:1',-1).key,'history:2');
});

test('navigator is inert for empty or invalid models', () => {
  assert.deepEqual(navigatorMarkers(null),[]);
  assert.equal(adjacentNode(null,null,1),null);
  assert.equal(adjacentNode(model(null),null,1),null);
});

test('navigator does not create relationships or mutate records', () => {
  const source = {events:[{id:1,title:'Event',dateMs:Date.UTC(2026,9,31)}],actions:[]};
  const before = JSON.parse(JSON.stringify(source));
  const data=model(source);
  navigatorMarkers(data);
  adjacentNode(data,null,1);
  assert.deepEqual(data.links,[]);
  assert.deepEqual(source,before);
});
