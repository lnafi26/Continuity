-- Project Continuity: project-record relationship schema; deployment pending.
-- Intended for isolated/staging validation after security review.
-- Do not paste into the live SQL editor, run db push, or apply to production.
-- PostgreSQL 17 target; first release allows explicit user confirmation ONLY.
-- Source-document similarity is never proof of project causation.

-- Foreign keys must bind BOTH owner and project, not just globally unique IDs.
-- These unique indexes do not change existing records or client privileges.
CREATE UNIQUE INDEX IF NOT EXISTS projects_owner_id_uq_for_relationships
  ON public.projects (user_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS project_events_owner_project_id_uq_for_relationships
  ON public.project_events (user_id, project_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS project_actions_owner_project_id_uq_for_relationships
  ON public.project_actions (user_id, project_id, id);

CREATE TABLE public.project_record_relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid(),
  project_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN (
    'dependency', 'handoff', 'divergence', 'convergence'
  )),
  state text NOT NULL DEFAULT 'documented' CHECK (state = 'documented'),
  statement text NOT NULL CHECK (char_length(btrim(statement)) BETWEEN 1 AND 2000),
  from_event_id bigint,
  from_action_id bigint,
  to_event_id bigint,
  to_action_id bigint,
  -- Proof metadata is SERVER DEFAULTED. Clients cannot insert these columns.
  confirmed_by uuid NOT NULL DEFAULT auth.uid(),
  confirmed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT record_relationship_confirmation_owner CHECK (confirmed_by = user_id),
  CONSTRAINT record_relationship_from_exactly_one CHECK (
    num_nonnulls(from_event_id, from_action_id) = 1
  ),
  CONSTRAINT record_relationship_to_exactly_one CHECK (
    num_nonnulls(to_event_id, to_action_id) = 1
  ),
  CONSTRAINT record_relationship_no_self CHECK (
    NOT (from_event_id IS NOT NULL AND to_event_id IS NOT NULL
      AND from_event_id = to_event_id)
    AND NOT (from_action_id IS NOT NULL AND to_action_id IS NOT NULL
      AND from_action_id = to_action_id)
  ),
  CONSTRAINT record_relationship_project_owner_fk
    FOREIGN KEY (user_id, project_id)
    REFERENCES public.projects (user_id, id) ON DELETE CASCADE,
  CONSTRAINT record_relationship_from_event_owner_fk
    FOREIGN KEY (user_id, project_id, from_event_id)
    REFERENCES public.project_events (user_id, project_id, id) ON DELETE CASCADE,
  CONSTRAINT record_relationship_from_action_owner_fk
    FOREIGN KEY (user_id, project_id, from_action_id)
    REFERENCES public.project_actions (user_id, project_id, id) ON DELETE CASCADE,
  CONSTRAINT record_relationship_to_event_owner_fk
    FOREIGN KEY (user_id, project_id, to_event_id)
    REFERENCES public.project_events (user_id, project_id, id) ON DELETE CASCADE,
  CONSTRAINT record_relationship_to_action_owner_fk
    FOREIGN KEY (user_id, project_id, to_action_id)
    REFERENCES public.project_actions (user_id, project_id, id) ON DELETE CASCADE
);

-- PostgreSQL 17: NULLS NOT DISTINCT prevents duplicate typed endpoints.
CREATE UNIQUE INDEX project_record_relationships_endpoint_uq
  ON public.project_record_relationships (
    user_id, project_id, kind,
    from_event_id, from_action_id, to_event_id, to_action_id
  ) NULLS NOT DISTINCT;
CREATE INDEX project_record_relationships_project_idx
  ON public.project_record_relationships (user_id, project_id);

ALTER TABLE public.project_record_relationships ENABLE ROW LEVEL SECURITY;

-- Grants are distinct from RLS. Revoke all defaults before granting minimum.
REVOKE ALL ON TABLE public.project_record_relationships FROM PUBLIC, anon, authenticated;
GRANT SELECT, DELETE ON TABLE public.project_record_relationships TO authenticated;
-- No INSERT for ID, user_id, state, confirmed_by or confirmed_at.
-- The database generates the proof identity and timestamp; UPDATE is never granted.
GRANT INSERT (
  project_id, kind, statement,
  from_event_id, from_action_id, to_event_id, to_action_id
) ON TABLE public.project_record_relationships TO authenticated;

CREATE POLICY project_record_relationships_read_owned
  ON public.project_record_relationships
  FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) = user_id);
CREATE POLICY project_record_relationships_insert_confirmed
  ON public.project_record_relationships
  FOR INSERT TO authenticated
  WITH CHECK (
    (SELECT auth.uid()) = user_id
    AND confirmed_by = (SELECT auth.uid())
    AND state = 'documented'
  );
CREATE POLICY project_record_relationships_delete_owned
  ON public.project_record_relationships
  FOR DELETE TO authenticated
  USING ((SELECT auth.uid()) = user_id);

-- No UPDATE policy, grant, or write APIs in this draft.
-- A documented relation is inserted only after an explicit user gesture.
-- Delete/recreate is required to change endpoints or confirmation content.
-- Do not claim that this draft has passed PostgreSQL execution or RLS tests.
