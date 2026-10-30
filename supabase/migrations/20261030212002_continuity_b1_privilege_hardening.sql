-- Project Continuity — B1 security hardening.
-- Previously applied manually to the linked database.
-- Intended for fresh database environments.
-- Reconcile remote migration history before deployment.

BEGIN;

-- Client roles must not bypass row ownership via TRUNCATE.
-- REFERENCES and TRIGGER are unnecessary for app clients.
REVOKE TRUNCATE, TRIGGER, REFERENCES ON TABLE
    public.profiles,
    public.projects,
    public.source_connections,
    public.source_items,
    public.project_source_links,
    public.project_events,
    public.project_actions,
    public.user_corrections,
    public.item_relationships
FROM anon, authenticated;

-- Trigger and event-trigger functions must not be client RPCs.
-- Preserve SECURITY DEFINER for their internal database operation.
REVOKE EXECUTE ON FUNCTION public.handle_new_user()
FROM PUBLIC, anon, authenticated;

-- Optional function: absent from the initial schema.
DO $b1_optional_rls$
BEGIN
    IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated';
    END IF;
END;
$b1_optional_rls$;

COMMIT;
