/* Offline structural guards for deferred SQL. NOT database execution tests. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const sql = fs.readFileSync(path.join(__dirname,
  '../../backend/database/deferred/project_record_relationships.draft.sql'), 'utf8');
const active = sql.split('\n').filter(line => !line.trim().startsWith('--')).join('\n');

test('draft cannot be mistaken for an applied Supabase migration', () => {
  assert.match(sql, /DRAFT ONLY; NOT A SUPABASE MIGRATION/);
  assert.match(sql, /isolated\/staging validation/);
});
test('uses a dedicated project-record relationship table, not semantic source links', () => {
  assert.match(active, /CREATE TABLE public\.project_record_relationships/);
  assert.doesNotMatch(active, /CREATE TABLE public\.item_relationships/);
});
test('four explicit relationship kinds and only documented state', () => {
  for (const kind of ['dependency', 'handoff', 'divergence', 'convergence'])
    assert.ok(active.includes(`'${kind}'`));
  assert.match(active, /CHECK \(state = 'documented'\)/);
});
test('exactly one typed endpoint on each side and self-links denied', () => {
  assert.match(active, /num_nonnulls\(from_event_id, from_action_id\) = 1/);
  assert.match(active, /num_nonnulls\(to_event_id, to_action_id\) = 1/);
  assert.match(active, /record_relationship_no_self CHECK/);
});
test('server verifies both project and owner for both endpoints', () => {
  assert.match(active, /FOREIGN KEY \(user_id, project_id\)\s+REFERENCES public\.projects \(user_id, id\)/);
  for (const table of ['project_events', 'project_actions']) {
    const re = new RegExp('FOREIGN KEY \\(user_id, project_id, (?:from|to)_(?:event|action)_id\\)\\s+REFERENCES public\\.' + table + ' \\(user_id, project_id, id\\)', 'g');
    assert.equal([...active.matchAll(re)].length, 2, table);
  }
});
test('all required composite reference keys have unique indexes', () => {
  for (const key of ['projects (user_id, id)',
    'project_events (user_id, project_id, id)',
    'project_actions (user_id, project_id, id)']) assert.ok(active.includes(key));
});
test('duplicate typed endpoint edges are prohibited, even with NULL columns', () => {
  assert.match(active, /CREATE UNIQUE INDEX project_record_relationships_endpoint_uq/);
  assert.match(active, /NULLS NOT DISTINCT/);
});
test('server-owned confirmation cannot be supplied through granted INSERT columns', () => {
  assert.match(active, /confirmed_by uuid NOT NULL DEFAULT auth\.uid\(\)/);
  assert.match(active, /confirmed_at timestamptz NOT NULL DEFAULT now\(\)/);
  const insert = active.match(/GRANT INSERT\s*\(([\s\S]*?)\) ON TABLE public\.project_record_relationships TO authenticated;/);
  assert.ok(insert);
  for (const forbidden of ['confirmed_by', 'confirmed_at', 'user_id', 'state', 'id', 'created_at'])
    assert.ok(!insert[1].split(',').map(x=>x.trim()).includes(forbidden), forbidden);
});
test('RLS enabled and explicitly authorized SELECT/INSERT/DELETE only', () => {
  assert.match(active, /ENABLE ROW LEVEL SECURITY/);
  assert.match(active, /REVOKE ALL ON TABLE public\.project_record_relationships FROM PUBLIC, anon, authenticated/);
  assert.match(active, /GRANT SELECT, DELETE ON TABLE public\.project_record_relationships TO authenticated/);
  for (const op of ['SELECT', 'INSERT', 'DELETE'])
    assert.match(active, new RegExp('FOR ' + op + ' TO authenticated'));
  assert.doesNotMatch(active, /FOR UPDATE TO authenticated|GRANT UPDATE/);
  assert.doesNotMatch(active, /TO anon;/);
});
test('ownership checks cover reading, inserting and deleting', () => {
  assert.equal((active.match(/\(SELECT auth\.uid\(\)\) = user_id/g) || []).length, 3);
  assert.match(active, /AND confirmed_by = \(SELECT auth\.uid\(\)\)/);
});
