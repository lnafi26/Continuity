"""B4 synthetic-only adapter for fictional, database-shaped revision rows.

Does not connect to Supabase, authorize a bearer token, persist or read records.
The future authenticated reader must verify project and source ownership via
RLS-scoped queries before calling this adapter. Source links are references,
never proof of a factual claim or proof that a human approved a revision.
"""

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone

from backend.memory.revisions import project_memory_at

MAX_REVISIONS = 100
MAX_EVIDENCE = 200
MAX_LINKS = 200


def _identity(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    return value


def _rows(value, name, limit):
    if not isinstance(value, (tuple, list)) or len(value) > limit:
        raise ValueError(f"Invalid or unbounded {name} rows.")
    if any(not isinstance(row, Mapping) for row in value):
        raise TypeError(f"Invalid {name} row.")
    return value


def _owned(row, *, user_id, project_id, name):
    if row.get("user_id") != user_id or row.get("project_id") != project_id:
        raise PermissionError(f"Cross-owner or cross-project {name} rejected.")


def _instant(value, name):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid {name} timestamp.") from None
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"Timezone-aware {name} timestamp required.")
    return value.astimezone(timezone.utc)


def project_synthetic_rows(
    assertion, revisions, evidence, project_links, *,
    authenticated_user_id, project_id, as_of,
):
    """Project *already scoped* fictional rows using the B4 projector.

    Authentication, parent-project existence and source-item ownership cannot
    be established by an in-memory adapter. This function checks internal
    consistency and denies records missing an explicit authorized link.
    It must not be called with unsanitized, privileged or hosted data.
    """
    user = _identity(authenticated_user_id, "Authenticated user")
    project = _identity(project_id, "Project")
    if not isinstance(assertion, Mapping):
        raise TypeError("Assertion row required.")
    _owned(assertion, user_id=user, project_id=project, name="assertion")
    assertion_id = _identity(assertion.get("id"), "Assertion ID")
    created = _instant(assertion.get("created_at"), "assertion creation")
    _instant(as_of, "snapshot")

    revision_rows = _rows(revisions, "revision", MAX_REVISIONS)
    evidence_rows = _rows(evidence, "evidence", MAX_EVIDENCE)
    link_rows = _rows(project_links, "project link", MAX_LINKS)

    linked_sources = set()
    for row in link_rows:
        _owned(row, user_id=user, project_id=project, name="source link")
        source_id = _identity(row.get("source_item_id"), "Linked source")
        linked_sources.add(source_id)

    for row in revision_rows:
        _owned(row, user_id=user, project_id=project, name="revision")
        if row.get("assertion_id") != assertion_id:
            raise PermissionError("Revision assertion ownership mismatch.")
        recorded = _instant(row.get("recorded_at"), "revision recording")
        state = row.get("review_state")
        confirmed_by = row.get("confirmed_by")
        confirmed_at = row.get("confirmed_at")
        if state == "confirmed":
            if row.get("actor_type") != "user" or confirmed_by != user:
                raise PermissionError("Revision confirmation attribution invalid.")
            confirmed = _instant(confirmed_at, "confirmation")
            if confirmed < created or confirmed > recorded:
                raise ValueError("Confirmation time inconsistent with record.")
        elif confirmed_by is not None or confirmed_at is not None:
            raise ValueError("Unconfirmed revision cannot carry confirmation.")

    for row in evidence_rows:
        _owned(row, user_id=user, project_id=project, name="evidence")
        if row.get("assertion_id") != assertion_id:
            raise PermissionError("Evidence assertion ownership mismatch.")
        source_id = _identity(row.get("source_item_id"), "Evidence source")
        if source_id not in linked_sources:
            raise PermissionError("Evidence source not linked to this project.")

    # The existing projector independently validates predecessor chains,
    # ordering, actors, effective times, and evidence-to-revision links.
    # Defensive copies ensure caller-owned row mappings cannot be mutated.
    projection = project_memory_at(
        deepcopy(dict(assertion)),
        deepcopy([dict(row) for row in revision_rows]),
        deepcopy([dict(row) for row in evidence_rows]),
        as_of=as_of,
    )
    if (
        projection.get("kind") != "synthetic_revision_projection"
        or projection.get("persisted") is not False
    ):
        raise ValueError("Unexpected projector contract.")

    # Do not change persisted=False or claim database provenance.
    return projection
