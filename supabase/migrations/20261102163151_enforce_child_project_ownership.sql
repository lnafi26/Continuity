-- Protect child records from referencing projects owned by other users.
-- Add restrictive policies without weakening existing user_id policies.
-- This migration does not change grants or bypass RLS.

-- Refuse activation if existing records violate parent ownership.
-- Any such records need a separate, reviewed reconciliation.
DO $ownership_preflight$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.project_events AS e
    JOIN public.projects AS p ON p.id = e.project_id
    WHERE e.user_id IS DISTINCT FROM p.user_id
  ) OR EXISTS (
    SELECT 1
    FROM public.project_actions AS a
    JOIN public.projects AS p ON p.id = a.project_id
    WHERE a.user_id IS DISTINCT FROM p.user_id
  ) THEN
    RAISE EXCEPTION
      'Existing child records violate project ownership; reconcile before applying';
  END IF;
END;
$ownership_preflight$;

CREATE POLICY project_events_parent_owner_guard
ON public.project_events
AS RESTRICTIVE
FOR ALL
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.projects AS p
    WHERE p.id = project_events.project_id
      AND p.user_id = (SELECT auth.uid())
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.projects AS p
    WHERE p.id = project_events.project_id
      AND p.user_id = (SELECT auth.uid())
  )
);

CREATE POLICY project_actions_parent_owner_guard
ON public.project_actions
AS RESTRICTIVE
FOR ALL
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.projects AS p
    WHERE p.id = project_actions.project_id
      AND p.user_id = (SELECT auth.uid())
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.projects AS p
    WHERE p.id = project_actions.project_id
      AND p.user_id = (SELECT auth.uid())
  )
);
