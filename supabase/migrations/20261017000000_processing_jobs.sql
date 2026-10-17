-- R0.3A: persistent job lease/retry ledger. DO NOT apply to live Supabase yet.
-- Backend-only access. No current stage reads/writes this table.
-- Later migrations must add source-revision semantics before automatic reuse.
BEGIN;

-- Ensure the source row and job record share the same owner at the FK level.
CREATE UNIQUE INDEX source_items_id_user_id_job_ownership_idx
    ON public.source_items (id, user_id);

CREATE TABLE public.processing_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    source_item_id uuid NOT NULL,
    stage text NOT NULL DEFAULT 'extract' CHECK (stage IN ('extract')),
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','retry_wait','succeeded','failed')),
    attempts smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 6),
    max_attempts smallint NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 6),
    retry_at timestamptz DEFAULT now(),
    lease_token uuid,
    lease_until timestamptz,
    last_error_code text CHECK (last_error_code IN (
        'inference_unavailable','processing_failed','storage_unavailable',
        'invalid_source','user_edit_conflict','lease_expired'
    )),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CONSTRAINT processing_jobs_source_owner_fk
        FOREIGN KEY (source_item_id, user_id)
        REFERENCES public.source_items (id, user_id) ON DELETE CASCADE,
    CONSTRAINT processing_jobs_unique_stage_source
        UNIQUE (user_id, source_item_id, stage),
    CONSTRAINT processing_jobs_lease_state_check CHECK (
        (status = 'running' AND lease_token IS NOT NULL AND lease_until IS NOT NULL)
        OR (status <> 'running' AND lease_token IS NULL AND lease_until IS NULL)
    ),
    CONSTRAINT processing_jobs_attempts_within_max_check CHECK (attempts <= max_attempts)
);

CREATE INDEX processing_jobs_claim_idx
    ON public.processing_jobs (user_id, stage, retry_at, created_at)
    WHERE status IN ('queued','retry_wait');
CREATE INDEX processing_jobs_stale_idx
    ON public.processing_jobs (user_id, stage, lease_until)
    WHERE status = 'running';

ALTER TABLE public.processing_jobs ENABLE ROW LEVEL SECURITY;
-- No browser/authenticated RLS policies or grants. Privileged service only.
REVOKE ALL PRIVILEGES ON public.processing_jobs FROM PUBLIC, anon, authenticated;
COMMIT;
