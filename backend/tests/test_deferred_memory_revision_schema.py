"""Static safety tests for deferred B4 SQL; never connect to a database."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / 'backend/database/deferred/project_memory_revisions.review.sql'
DESIGN = ROOT / 'backend/database/deferred/project_memory_revisions.design.md'
MIGRATIONS = ROOT / 'supabase/migrations'
GATE = ROOT / 'scripts/check_supabase_integration_gate.py'

TABLES = (
    'project_memory_assertions',
    'project_memory_revisions',
    'project_memory_revision_evidence',
)


def normalize(sql):
    return re.sub(r'\s+', ' ', sql.lower())


class DeferredMemoryRevisionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = DRAFT.read_text()
        cls.sql = normalize(cls.raw)
        cls.design = DESIGN.read_text()

    def test_is_deferred_and_not_an_approved_migration(self):
        self.assertTrue(DRAFT.is_file())
        self.assertTrue(DESIGN.is_file())
        self.assertNotIn(DRAFT.name, {p.name for p in MIGRATIONS.glob('*.sql')})
        self.assertIn('DO NOT APPLY', self.raw)
        self.assertIn('DESIGN REVIEW ONLY', self.design)
        self.assertIn('Only after', self.design)

    def test_exact_candidate_tables(self):
        found = re.findall(r'create table public\.(\w+)', self.sql)
        self.assertEqual(tuple(found), TABLES)
        self.assertEqual(self.sql.count('enable row level security'), 3)

    def test_project_assertion_owner_composite_key(self):
        self.assertIn('foreign key (user_id, project_id) references public.projects (user_id, id)', self.sql)
        self.assertIn('unique (user_id, project_id, id)', self.sql)

    def test_revision_references_scoped_assertion_and_predecessor(self):
        self.assertIn('foreign key (user_id, project_id, assertion_id) references public.project_memory_assertions (user_id, project_id, id)', self.sql)
        self.assertIn('foreign key (user_id, project_id, assertion_id, supersedes_revision_id) references public.project_memory_revisions (user_id, project_id, assertion_id, id)', self.sql)
        self.assertIn('unique (user_id, project_id, assertion_id, version_number)', self.sql)
        self.assertIn('unique (user_id, project_id, assertion_id, supersedes_revision_id)', self.sql)
        self.assertIn('version_number = 1 and supersedes_revision_id is null', self.sql)

    def test_confirmation_is_restricted_in_shape_not_assumed_authenticated(self):
        self.assertIn("review_state in ('proposed', 'confirmed', 'disputed', 'rejected')", self.sql)
        self.assertIn("actor_type in ('user', 'agent', 'system')", self.sql)
        self.assertIn("review_state = 'confirmed' and actor_type = 'user' and confirmed_by is not null and confirmed_by = user_id", self.sql)
        self.assertIn('row shape CHECK alone cannot prove', self.design)
        self.assertIn("jsonb_typeof(structured_value) = 'object'", self.sql)

    def test_evidence_scope_is_project_and_source_owned(self):
        self.assertIn('foreign key (user_id, project_id, assertion_id, revision_id) references public.project_memory_revisions (user_id, project_id, assertion_id, id)', self.sql)
        self.assertIn('foreign key (user_id, source_item_id) references public.source_items (user_id, id)', self.sql)
        self.assertIn('foreign key (user_id, project_id, source_item_id) references public.project_source_links (user_id, project_id, source_item_id)', self.sql)
        self.assertIn("evidence_role in ('supports', 'contradicts', 'context')", self.sql)

    def test_no_direct_user_mutation_grants_or_policies(self):
        for table in TABLES:
            self.assertIn(f'revoke all on table public.{table} from public, anon, authenticated', self.sql)
            self.assertIn(f'grant select on table public.{table} to authenticated', self.sql)
        self.assertEqual(self.sql.count('for select to authenticated'), 3)
        for phrase in ('grant insert', 'grant update', 'grant delete', 'for insert', 'for update', 'for delete', 'security definer', 'auth.role('):
            self.assertNotIn(phrase, self.sql)

    def test_rls_owner_and_parent_ownership(self):
        self.assertEqual(self.sql.count('(select auth.uid()) = user_id'), 3)
        for table in TABLES:
            self.assertIn(
                f'p.id = {table}.project_id and p.user_id = {table}.user_id',
                self.sql,
            )
        self.assertIn('Data API', self.design)

    def test_existing_source_contracts_are_present(self):
        initial = (MIGRATIONS / '20261016000000_initial_schema.sql').read_text().lower()
        relationship = (MIGRATIONS / '20261101233115_project_record_relationships.sql').read_text().lower()
        for table in ('projects', 'source_items', 'project_source_links'):
            self.assertRegex(initial, rf'create table public\.{table}\b')
        self.assertIn('on public.projects (user_id, id)', normalize(relationship))
        self.assertIn('source_item_id', initial)

    def test_gate_remains_separate_and_unexpanded(self):
        gate = GATE.read_text()
        self.assertIn('20261016000000_initial_schema.sql', gate)
        self.assertIn('20261030212002_continuity_b1_privilege_hardening.sql', gate)
        for table in TABLES:
            self.assertNotIn(table, gate)
        self.assertEqual(len(tuple(MIGRATIONS.glob('*.sql'))), 4)


if __name__ == '__main__':
    unittest.main()
