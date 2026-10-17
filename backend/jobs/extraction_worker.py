"""R0.4: Manually invoked offline extraction.

No scheduler, background worker, or external inference.
Writes are restricted to the disposable local Docker test DB.
"""

from __future__ import annotations

from psycopg.conninfo import conninfo_to_dict

from backend.extract.extract_repo import write_extraction_with_claim_atomic
from backend.intelligence import ModelRouter
from backend.jobs.ledger import JobClaim
from backend.jobs.source_reader import fetch_claimed_source


def prepare_claimed_extraction(
    database_url: str,
    claim: JobClaim,
) -> dict:
    """Prepare candidates without writing extraction results."""
    source = fetch_claimed_source(database_url, claim)

    result = ModelRouter().run(
        "event_extraction",
        {"item": source["item"]},
    )

    if result.provider != "offline":
        raise RuntimeError("Offline-only extraction required.")

    return {
        "project_id": source["project_id"],
        "color": source["color"],
        "events": result.data["events"],
        "actions": result.data["actions"],
    }


def process_one_claim_local(
    database_url: str,
    claim: JobClaim,
) -> bool:
    """Process one claimed job in disposable Docker only.

    The fenced writer rechecks the lease before committing.
    """
    settings = conninfo_to_dict(database_url)

    if (
        settings.get("host") != "127.0.0.1"
        or str(settings.get("port")) != "55432"
        or settings.get("dbname") != "continuity_test"
        or settings.get("user") != "continuity_test"
        or settings.get("hostaddr")
        or settings.get("service")
    ):
        raise ValueError(
            "R0.4 writes require the local Docker test database."
        )

    prepared = prepare_claimed_extraction(database_url, claim)

    return write_extraction_with_claim_atomic(
        database_url,
        claim,
        prepared["project_id"],
        events=prepared["events"],
        actions=prepared["actions"],
        color=prepared["color"],
    )
