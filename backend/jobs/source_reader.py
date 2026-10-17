"""R0.4: Read a source belonging to a currently leased extraction job.

This module does not start workers, invoke inference, or write data.
"""

from __future__ import annotations

import psycopg

from backend.jobs.ledger import (
    JobClaim, JobLeaseLostError, STAGE, _claim_ids, _uuid,
)


def fetch_claimed_source(
    database_url: str,
    claim: JobClaim,
) -> dict:
    """Retrieve one authorized source and its selected project."""
    job_id, user_id, token = _claim_ids(claim)
    source_id = _uuid(claim.source_item_id, "source_item_id")

    if type(claim.attempt) is not int or claim.attempt < 1:
        raise JobLeaseLostError()

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id, p.color,
                    si.source_type, si.title, si.sender,
                    si.participants, si.occurred_at,
                    si.extracted_text
                FROM public.processing_jobs j
                JOIN public.source_items si
                  ON si.id = j.source_item_id
                 AND si.user_id = j.user_id
                JOIN public.project_source_links l
                  ON l.source_item_id = si.id
                 AND l.user_id = j.user_id
                JOIN public.projects p
                  ON p.id = l.project_id
                 AND p.user_id = j.user_id
                WHERE j.id = %s
                  AND j.user_id = %s
                  AND j.source_item_id = %s
                  AND j.stage = %s
                  AND j.status = 'running'
                  AND j.lease_token = %s
                  AND j.attempts = %s
                  AND j.lease_until > clock_timestamp()
                  AND si.extracted_at IS NULL
                ORDER BY l.confidence DESC NULLS LAST,
                         l.id, p.id
                LIMIT 1
                """,
                (
                    job_id, user_id, source_id,
                    STAGE, token, claim.attempt,
                ),
            )
            row = cursor.fetchone()

    if row is None:
        raise JobLeaseLostError()

    return {
        "project_id": str(row[0]),
        "color": row[1] or "#4263eb",
        "item": {
            "source_type": row[2],
            "title": row[3],
            "sender": row[4],
            "participants": row[5] or [],
            "occurred_at": row[6],
            "extracted_text": row[7],
        },
    }
