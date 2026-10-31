const test = require('node:test');
const assert = require('node:assert/strict');
const feature = require('../assets/js/manual-projects.js');

function client() {
  const inserts = [];
  const db = {
    from(table) {
      if (table === 'projects') {
        return {
          insert(value) {
            inserts.push({ table, value });
            return { select() { return { async single() { return { data: { id: 'project-1' }, error: null }; } }; } };
          },
          select() {
            return { eq() { return this; }, async maybeSingle() { return { data: { id: 'project-1' }, error: null }; } };
          }
        };
      }
      return { async insert(value) { inserts.push({ table, value }); return { error: null }; } };
    }
  };
  return { db, inserts };
}

test('create project writes a user-owned record', async () => {
  const { db, inserts } = client();
  const id = await feature.createProject(db, 'user-1', { name: '  Lunar Observatory ', summary: ' A demo ' });
  assert.equal(id, 'project-1');
  assert.deepEqual(inserts[0], { table: 'projects', value: {
    user_id: 'user-1', name: 'Lunar Observatory', summary: 'A demo', symbol: 'L', origin: 'user', category: 'project'
  } });
});

test('decision is associated with an owned project', async () => {
  const { db, inserts } = client();
  await feature.addDecision(db, 'user-1', 'project-1', { title: ' Approve timeline ', body: ' manual ' });
  assert.equal(inserts[0].table, 'project_events');
  assert.equal(inserts[0].value.event_type, 'decision');
  assert.equal(inserts[0].value.project_id, 'project-1');
  assert.equal(inserts[0].value.title, 'Approve timeline');
});

test('task uses allowed status and due date', async () => {
  const { db, inserts } = client();
  await feature.addTask(db, 'user-1', 'project-1', { title: ' Wire dashboard ', due_date: '2026-11-03' });
  assert.equal(inserts[0].table, 'project_actions');
  assert.equal(inserts[0].value.status, 'not_started');
  assert.equal(inserts[0].value.due_date, '2026-11-03');
});

test('invalid dates are refused', () => {
  assert.throws(() => feature.dateOnly('2026-02-30'), /Invalid calendar date/);
  assert.throws(() => feature.dateOnly('Nov 3 2026'), /YYYY-MM-DD/);
  assert.equal(feature.dateOnly(''), null);
});

test('invalid project name prevents any mutation', async () => {
  const { db, inserts } = client();
  await assert.rejects(feature.createProject(db, 'user-1', { name: ' ', summary: '' }), /Project name/);
  assert.equal(inserts.length, 0);
});

test('missing project ownership refuses event write', async () => {
  const { db, inserts } = client();
  db.from = () => ({ select() { return { eq() { return this; }, async maybeSingle() { return {data:null,error:null}; } }; } });
  await assert.rejects(feature.addDecision(db, 'user-1', 'project-9', { title:'New', body:'' }), /not owned/);
  assert.equal(inserts.length, 0);
});
