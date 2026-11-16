-- PROJECT CONTINUITY / B4 / DEFERRED DESIGN REVIEW ONLY
-- DO NOT APPLY. NOT AN APPROVED MIGRATION.
-- Keep this file OUTSIDE supabase/migrations.
-- A reviewed, generated migration is required before any local or hosted execution.
-- No backend write endpoint or human-confirmation authorization is implemented.

BEGIN;

-- Every composite FK below includes owner and project where applicable.
-- Pre-deployment review: inspect preexisting ownership/duplicate records.
CREATE UNIQUE INDEX IF NOT EXISTS memory_source_items_owner_id_reference
  ON public.source_items (user_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS memory_project_source_links_scope_reference
  ON public.project_source_links (user_id, project_id, source_item_id);
-- public.projects (user_id, id) is already indexed by the relationship migration.

CREATE TABLE public.project_memory_assertions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  project_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT memory_assertions_parent_project_fk
    FOREIGN KEY (user_id, project_id)
    REFERENCES public.projects (user_id, id) ON DELETE CASCADE,
  CONSTRAINT memory_assertions_owner_project_id_unique
    UNIQUE (user_id, project_id, id)
);

CREATE TABLE public.project_memory_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  project_id uuid NOT NULL,
  assertion_id uuid NOT NULL,
  version_number integer NOT NULL CHECK (version_number > 0),
  supersedes_revision_id uuid,
  review_state text NOT NULL CHECK (
    review_state IN ('proposed', 'confirmed', 'disputed', 'rejected')
  ),
  actor_type text NOT NULL CHECK (
    actor_type IN ('user', 'agent', 'system')
  ),
  -- A confirmation is only recorded by an authenticated human-confirmation flow.
  -- This CHECK is necessary but NOT sufficient to verify a human actor.
  confirmed_by uuid,
  confirmed_at timestamptz,
  structured_value jsonb NOT NULL CHECK (
    jsonb_typeof(structured_value) = 'object'
  ),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  effective_at timestamptz NOT NULL,
  CONSTRAINT memory_revision_confirmation_shape CHECK (
    (review_state = 'confirmed'
      AND actor_type = 'user'
      AND confirmed_by IS NOT NULL
      AND confirmed_by = user_id
      AND confirmed_at IS NOT NULL)
    OR
    (review_state <> 'confirmed'
      AND confirmed_by IS NULL
      AND confirmed_at IS NULL)
  ),
  CONSTRAINT memory_revision_predecessor_shape CHECK (
    (version_number = 1 AND supersedes_revision_id IS NULL)
    OR (version_number > 1 AND supersedes_revision_id IS NOT NULL)
  ),
  CONSTRAINT memory_revision_not_self_reference CHECK (
    id IS DISTINCT FROM supersedes_revision_id
  ),
  CONSTRAINT memory_revision_assertion_fk
    FOREIGN KEY (user_id, project_id, assertion_id)
    REFERENCES public.project_memory_assertions (user_id, project_id, id)
    ON DELETE CASCADE,
  CONSTRAINT memory_revision_version_unique
    UNIQUE (user_id, project_id, assertion_id, version_number),
  CONSTRAINT memory_revision_scoped_id_unique
    UNIQUE (user_id, project_id, assertion_id, id),
  CONSTRAINT memory_revision_single_successor_unique
    UNIQUE (user_id, project_id, assertion_id, supersedes_revision_id),
  CONSTRAINT memory_revision_predecessor_fk
    FOREIGN KEY (user_id, project_id, assertion_id, supersedes_revision_id)
    REFERENCES public.project_memory_revisions
      (user_id, project_id, assertion_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE public.project_memory_revision_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  project_id uuid NOT NULL,
  assertion_id uuid NOT NULL,
  revision_id uuid NOT NULL,
  source_item_id uuid NOT NULL,
  evidence_role text NOT NULL CHECK (
    evidence_role IN ('supports', 'contradicts', 'context')
  ),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT memory_evidence_revision_fk
    FOREIGN KEY (user_id, project_id, assertion_id, revision_id)
    REFERENCES public.project_memory_revisions
      (user_id, project_id, assertion_id, id)
    ON DELETE CASCADE,
  CONSTRAINT memory_evidence_source_owner_fk
    FOREIGN KEY (user_id, source_item_id)
    REFERENCES public.source_items (user_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT memory_evidence_source_project_link_fk
    FOREIGN KEY (user_id, project_id, source_item_id)
    REFERENCES public.project_source_links
      (user_id, project_id, source_item_id)
    ON DELETE RESTRICT,
  CONSTRAINT memory_evidence_role_unique
    UNIQUE (
      user_id, project_id, assertion_id, revision_id,
      source_item_id, evidence_role
    )
);

CREATE INDEX memory_assertions_project_idx
  ON public.project_memory_assertions (user_id, project_id, created_at DESC);
CREATE INDEX memory_revisions_assertion_idx
  ON public.project_memory_revisions
  (user_id, project_id, assertion_id, version_number);
CREATE INDEX memory_evidence_revision_idx
  ON public.project_memory_revision_evidence
  (user_id, project_id, assertion_id, revision_id);

ALTER TABLE public.project_memory_assertions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_memory_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_memory_revision_evidence ENABLE ROW LEVEL SECURITY;

-- Explicitly remove default Data API privileges; RLS alone is insufficient.
REVOKE ALL ON TABLE public.project_memory_assertions
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.project_memory_revisions
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.project_memory_revision_evidence
  FROM PUBLIC, anon, authenticated;

-- The future reader may select owner-scoped records. There is deliberately
-- NO INSERT/UPDATE/DELETE grant or policy for user-facing roles.
GRANT SELECT ON TABLE public.project_memory_assertions TO authenticated;
GRANT SELECT ON TABLE public.project_memory_revisions TO authenticated;
GRANT SELECT ON TABLE public.project_memory_revision_evidence TO authenticated;

CREATE POLICY memory_assertions_read_owned
  ON public.project_memory_assertions FOR SELECT TO authenticated
  USING (
    (SELECT auth.uid()) = user_id
    AND EXISTS (
      SELECT 1 FROM public.projects AS p
      WHERE p.id = project_memory_assertions.project_id
        AND p.user_id = project_memory_assertions.user_id
    )
  );

CREATE POLICY memory_revisions_read_owned
  ON public.project_memory_revisions FOR SELECT TO authenticated
  USING (
    (SELECT auth.uid()) = user_id
    AND EXISTS (
      SELECT 1 FROM public.projects AS p
      WHERE p.id = project_memory_revisions.project_id
        AND p.user_id = project_memory_revisions.user_id
    )
  );

CREATE POLICY memory_evidence_read_owned
  ON public.project_memory_revision_evidence FOR SELECT TO authenticated
  USING (
    (SELECT auth.uid()) = user_id
    AND EXISTS (
      SELECT 1 FROM public.projects AS p
      WHERE p.id = project_memory_revision_evidence.project_id
        AND p.user_id = project_memory_revision_evidence.user_id
    )
  );

COMMIT;
