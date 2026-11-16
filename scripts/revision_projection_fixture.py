"""Generate fictional revisions through the actual in-memory projector only.

No network, credentials, persistent storage, or real user records.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.memory.revisions import project_memory_at


def fictional_projection():
    assertion = {
        "id": "fictional-assertion",
        "user_id": "fictional-user",
        "project_id": "fictional-project",
        "created_at": "2026-10-29T09:00:00Z",
    }
    versions = [
        ("confirmed", "user", "2026-10-29T10:00:00Z", "Initial fictional decision"),
        ("proposed", "agent", "2026-10-30T10:00:00Z", "Unreviewed fictional alternative"),
        ("confirmed", "user", "2026-10-31T10:00:00Z", "Corrected fictional decision"),
        ("proposed", "agent", "2026-11-01T10:00:00Z", "New fictional proposal"),
    ]
    revisions = []
    for i, (state, actor, recorded, decision) in enumerate(versions, 1):
        revisions.append({
            "id": f"fictional-revision-{i}",
            "user_id": assertion["user_id"],
            "project_id": assertion["project_id"],
            "assertion_id": assertion["id"],
            "version_number": i,
            "review_state": state,
            "actor_type": actor,
            "recorded_at": recorded,
            "effective_at": recorded,
            "structured_value": {"decision": decision},
            "supersedes_revision_id": f"fictional-revision-{i-1}" if i > 1 else None,
        })
    evidence = [
        {
            "user_id": assertion["user_id"],
            "project_id": assertion["project_id"],
            "revision_id": "fictional-revision-1",
            "source_item_id": "fictional-source-1",
            "evidence_role": "supports",
            "created_at": "2026-10-29T11:00:00Z",
        },
        {
            "user_id": assertion["user_id"],
            "project_id": assertion["project_id"],
            "revision_id": "fictional-revision-3",
            "source_item_id": "fictional-source-2",
            "evidence_role": "contradicts",
            "created_at": "2026-10-31T11:00:00Z",
        },
    ]
    return project_memory_at(
        assertion, revisions, evidence,
        as_of="2026-11-01T12:00:00Z",
    )


if __name__ == "__main__":
    print(json.dumps(fictional_projection(), sort_keys=True))
