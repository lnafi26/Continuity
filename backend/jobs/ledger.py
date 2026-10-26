"""R0.3A: durable, owner-scoped PostgreSQL job ledger (not a worker).

A scheduled job contains identifiers, timing information, retry counts, and a
fixed diagnostic code. It never stores raw source text, exception messages,
model output, URLs, or credentials. The ledger is deliberately NOT connected
into the disabled legacy processing pipeline.

The next integration phase must fence extraction writes against the active job
lease; these functions alone do not guarantee end-to-end exactly-once work.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg

STAGE = "extract"  # R0.3A tracks only atomic extraction; other stages later.
SAFE_ERROR_CODES = frozenset({
    "inference_unavailable", "processing_failed", "storage_unavailable",
    "invalid_source", "user_edit_conflict", "lease_expired",
})


class JobLeaseLostError(RuntimeError):
    """Claim expired, replaced, or belongs to another worker (no raw payload)."""

    def __init__(self):
        super().__init__("Job lease is no longer valid; no status was changed.")


@dataclass(frozen=True)
class JobClaim:
    job_id: str
    user_id: str
    source_item_id: str
    lease_token: str
    attempt: int


def _uuid(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID.")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        raise ValueError(f"{field} must be a UUID.") from None


def _claim_ids(claim: JobClaim) -> tuple[str, str, str]:
    if not isinstance(claim, JobClaim):
        raise ValueError("An explicit JobClaim is required.")
    return (_uuid(claim.job_id, "job_id"), _uuid(claim.user_id, "user_id"),
            _uuid(claim.lease_token, "lease_token"))


def enqueue_extraction(database_url: str, *, user_id: str,
                       source_item_id: str, max_attempts: int = 3) -> str | None:
    """Create one job for an owned, unprocessed source; None if not inserted.

    A uniqueness constraint prevents duplicate schedules. Reprocessing changed
    source versions needs explicit revision semantics in a later phase.
    """
    owner = _uuid(user_id, "user_id")
    source = _uuid(source_item_id, "source_item_id")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 6:
        raise ValueError("max_attempts must be an integer from 1 through 6.")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.processing_jobs
                    (user_id, source_item_id, stage, max_attempts)
                select si.user_id, si.id, %s, %s
                from public.source_items si
                where si.id = %s and si.user_id = %s
                  and si.extracted_at is null
                on conflict (user_id, source_item_id, stage) do nothing
                returning id
                """,
                (STAGE, max_attempts, source, owner),
            )
            row = cursor.fetchone()
    return str(row[0]) if row is not None else None


def claim_next(database_url: str, *, user_id: str,
               lease_seconds: int = 180) -> JobClaim | None:
    """Recover expired claims, then exclusively lease one eligible item.

    PostgreSQL row locks and SKIP LOCKED coordinate competing workers. The
    returned random token fences later status updates. Work itself is NOT run.
    """
    owner = _uuid(user_id, "user_id")
    if type(lease_seconds) is not int or not 30 <= lease_seconds <= 900:
        raise ValueError("lease_seconds must be an integer from 30 through 900.")
    token = str(uuid4())
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            # A terminated process can't leave a job running indefinitely.
            # Exhausted leases stay failed until a separately authorized reset.
            cursor.execute(
                """
                with expired as (
                    select id from public.processing_jobs
                    where user_id = %s and stage = %s
                      and status = 'running' and lease_until <= now()
                    for update skip locked
                )
                update public.processing_jobs j
                set status = case when attempts >= max_attempts
                                  then 'failed' else 'retry_wait' end,
                    last_error_code = 'lease_expired',
                    retry_at = case when attempts >= max_attempts then null
                                    else now() + interval '30 seconds' end,
                    finished_at = case when attempts >= max_attempts
                                       then now() else null end,
                    lease_token = null, lease_until = null,
                    updated_at = now()
                from expired where j.id = expired.id
                """,
                (owner, STAGE),
            )
            cursor.execute(
                """
                with next_job as (
                    select id from public.processing_jobs
                    where user_id = %s and stage = %s
                      and status in ('queued', 'retry_wait')
                      and retry_at <= now() and attempts < max_attempts
                    order by retry_at, created_at, id
                    for update skip locked
                    limit 1
                )
                update public.processing_jobs j
                set status = 'running', attempts = attempts + 1,
                    lease_token = %s::uuid,
                    lease_until = now() + (%s * interval '1 second'),
                    last_error_code = null, updated_at = now()
                from next_job where j.id = next_job.id
                returning j.id, j.source_item_id, j.attempts
                """,
                (owner, STAGE, token, lease_seconds),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return JobClaim(str(row[0]), owner, str(row[1]), token, int(row[2]))


def mark_succeeded(database_url: str, claim: JobClaim) -> None:
    """Acknowledge a live lease; stale workers can't mark success."""
    job, owner, token = _claim_ids(claim)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.processing_jobs
                set status = 'succeeded', lease_token = null,
                    lease_until = null, retry_at = null,
                    last_error_code = null, finished_at = now(),
                    updated_at = now()
                where id = %s and user_id = %s and stage = %s
                  and status = 'running' and lease_token = %s
                  and lease_until > now()
                returning id
                """,
                (job, owner, STAGE, token),
            )
            if cursor.fetchone() is None:
                raise JobLeaseLostError()


def mark_failed(database_url: str, claim: JobClaim, *, error_code: str) -> str:
    """Store only a safe error category; schedule bounded exponential retry.

    Returns retry_wait or failed. Never pass str(exception) as error_code.
    """
    if not isinstance(error_code, str) or error_code not in SAFE_ERROR_CODES:
        raise ValueError("Use an approved diagnostic code, not exception text.")
    job, owner, token = _claim_ids(claim)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.processing_jobs
                set status = case when attempts >= max_attempts
                                  then 'failed' else 'retry_wait' end,
                    retry_at = case when attempts >= max_attempts then null
                                    else now() +
                                    (least(3600, 30 * power(2, attempts - 1))
                                      * interval '1 second') end,
                    lease_token = null, lease_until = null,
                    last_error_code = %s,
                    finished_at = case when attempts >= max_attempts
                                       then now() else null end,
                    updated_at = now()
                where id = %s and user_id = %s and stage = %s
                  and status = 'running' and lease_token = %s
                  and lease_until > now()
                returning status
                """,
                (error_code, job, owner, STAGE, token),
            )
            row = cursor.fetchone()
            if row is None:
                raise JobLeaseLostError()
    return str(row[0])


def get_status(database_url: str, *, user_id: str, job_id: str) -> dict | None:
    """Return tenant-scoped, sanitized status; no source contents or secrets."""
    owner = _uuid(user_id, "user_id")
    job = _uuid(job_id, "job_id")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, stage, status, attempts, max_attempts,
                       last_error_code, retry_at, updated_at
                from public.processing_jobs
                where id = %s and user_id = %s
                """,
                (job, owner),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "job_id": str(row[0]), "stage": row[1], "status": row[2],
        "attempts": row[3], "max_attempts": row[4],
        "error_code": row[5],
        "retry_at": row[6].isoformat() if row[6] is not None else None,
        "updated_at": row[7].isoformat() if row[7] is not None else None,
    }
