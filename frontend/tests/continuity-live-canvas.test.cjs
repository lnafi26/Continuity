const test = require('node:test');
const assert = require('node:assert/strict');
const { buildCanvasModel } = require('../assets/js/continuity-live-canvas.js');
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
