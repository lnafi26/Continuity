"""R0.5: Explicitly invoked, single-job local worker.

No background loop, scheduler, CLI entrypoint, or hosted inference.
Restricted to the disposable Docker PostgreSQL database.
"""

from __future__ import annotations

from backend.extract.extract_repo import ExtractionWriteConflict
from backend.intelligence.router import InferenceUnavailableError
from backend.jobs.extraction_worker import (
    process_one_claim_local,
    require_local_test_database,
)
from backend.jobs.ledger import (
    JobLeaseLostError,
    claim_next,
    mark_failed,
)


def run_one_local(database_url: str, *, user_id: str) -> dict:
    """Claim and process at most one eligible synthetic extraction job.

    Returns sanitized job status without exposing source contents,
    inference output, credentials, or raw exception messages.
    """
    # Validate destination BEFORE claiming or modifying any jobs.
    require_local_test_database(database_url)

    claim = claim_next(
        database_url,
        user_id=user_id,
        lease_seconds=180,
    )

    if claim is None:
        return {"status": "no_eligible_job", "job_id": None}

    try:
        committed = process_one_claim_local(database_url, claim)

        if committed is not True:
            raise RuntimeError("Extraction did not commit.")

    except JobLeaseLostError:
        # An expired or replaced worker cannot report success/failure.
        return {
            "status": "lease_lost",
            "job_id": claim.job_id,
        }

    except Exception as exc:
        # Fixed categories only. Never persist str(exc).
        if isinstance(exc, InferenceUnavailableError):
            code = "inference_unavailable"
        elif isinstance(exc, ExtractionWriteConflict):
            code = "user_edit_conflict"
        else:
            code = "processing_failed"

        try:
            status = mark_failed(
                database_url,
                claim,
                error_code=code,
            )
        except JobLeaseLostError:
            return {
                "status": "lease_lost",
                "job_id": claim.job_id,
            }

        return {
            "status": status,
            "job_id": claim.job_id,
            "error_code": code,
        }

    return {
        "status": "succeeded",
        "job_id": claim.job_id,
    }
