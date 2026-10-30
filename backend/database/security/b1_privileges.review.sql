-- Project Continuity — B1 security hardening.
-- Applied manually to Continuity Supabase on 2026-10-30.
-- Retained as an audited SQL record, NOT an automatic migration.
-- Do not replay without checking current database privileges.
-- Existing migration history remains unreconciled.
--
-- Preserve existing authenticated CRUD access and RLS policies.
-- Do not modify the production release configuration.
-- Do not activate the deferred processing_jobs migration.

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

REVOKE EXECUTE ON FUNCTION public.rls_auto_enable()
FROM PUBLIC, anon, authenticated;

COMMIT;
