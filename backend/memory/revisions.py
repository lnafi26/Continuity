"""B4 synthetic-only, in-memory assertion revision projection.

No database, network, filesystem, or agent/inference operations.
Caller owns authentication, record authorization, and source ownership checks.
"""
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone

_STATES = frozenset({
    "proposed", "confirmed", "disputed", "rejected"
})
_ACTORS = frozenset({"user", "agent", "system"})
_ROLES = frozenset({"supports", "contradicts", "context"})


def _instant(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            raise ValueError(
                "Invalid timezone-aware timestamp."
            ) from None

    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "Timezone-aware timestamp required."
        )

    return value.astimezone(timezone.utc)


def _rows(value, label):
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            f"{label} must be a list or tuple."
        )

    if any(not isinstance(row, Mapping) for row in value):
        raise TypeError(
            f"{label} contains an invalid record."
        )

    return value


def _identity(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{label} identity required."
        )
    return value


def _scope(row, user_id, project_id, label):
    if (
        row.get("user_id") != user_id
        or row.get("project_id") != project_id
    ):
        raise PermissionError(
            f"Cross-user or cross-project {label} rejected."
        )


def project_memory_at(assertion, revisions, evidence, *, as_of):
    """Reconstruct only knowledge recorded by as_of.

    A new proposal or dispute cannot silently replace
    user-confirmed state.

    'Superseded' is a derived relationship, not an
    in-place status update.
    """
    if not isinstance(assertion, Mapping):
        raise TypeError("Assertion must be a record.")

    assertion_id = _identity(
        assertion.get("id"), "Assertion"
    )
    user_id = _identity(
        assertion.get("user_id"), "Owner"
    )
    project_id = _identity(
        assertion.get("project_id"), "Project"
    )

    cutoff = _instant(as_of)

    assertion_created = _instant(
        assertion.get("created_at")
    )
    if assertion_created > cutoff:
        raise ValueError(
            "Snapshot predates assertion creation."
        )

    normalized = []
    known_ids = set()
    previous_id = None
    previous_recorded = None

    for expected_version, row in enumerate(
        _rows(revisions, "Revisions"), start=1
    ):
        _scope(row, user_id, project_id, "revision")

        if row.get("assertion_id") != assertion_id:
            raise PermissionError(
                "Revision belongs to another assertion."
            )

        rid = _identity(
            row.get("id"), "Revision"
        )
        version = row.get("version_number")

        if (
            rid in known_ids
            or type(version) is not int
            or version != expected_version
        ):
            raise ValueError(
                "Revision IDs and versions must be "
                "unique and sequential."
            )

        if row.get("supersedes_revision_id") != previous_id:
            raise ValueError(
                "Revision must reference its predecessor."
            )

        state = row.get("review_state")
        actor = row.get("actor_type")

        if state not in _STATES or actor not in _ACTORS:
            raise ValueError(
                "Unsupported review state or actor."
            )

        if state == "confirmed" and actor != "user":
            raise PermissionError(
                "Only a human user may confirm memory."
            )

        structured_value = row.get("structured_value")

        if not isinstance(structured_value, Mapping):
            raise TypeError(
                "Structured revision value must be a mapping."
            )

        recorded = _instant(
            row.get("recorded_at")
        )
        effective = _instant(
            row.get("effective_at")
        )

        if recorded < assertion_created:
            raise ValueError(
                "Revision predates assertion creation."
            )

        if (
            previous_recorded is not None
            and recorded < previous_recorded
        ):
            raise ValueError(
                "Revision record times must be ordered."
            )

        normalized.append({
            "id": rid,
            "version_number": version,
            "review_state": state,
            "actor_type": actor,
            "structured_value": deepcopy(
                dict(structured_value)
            ),
            "recorded_at": recorded,
            "effective_at": effective,
            "supersedes_revision_id": previous_id,
        })

        known_ids.add(rid)
        previous_id = rid
        previous_recorded = recorded

    visible = [
        row for row in normalized
        if row["recorded_at"] <= cutoff
    ]

    confirmed = [
        row for row in visible
        if row["review_state"] == "confirmed"
        and row["effective_at"] <= cutoff
    ]

    current = confirmed[-1] if confirmed else None
    current_version = (
        current["version_number"] if current else 0
    )

    visible_ids = {
        row["id"] for row in visible
    }

    visible_evidence = []
    revision_by_id = {
        row["id"]: row for row in normalized
    }

    for row in _rows(evidence, "Evidence"):
        _scope(row, user_id, project_id, "evidence")

        if row.get("revision_id") not in known_ids:
            raise ValueError(
                "Evidence references unknown revision."
            )

        if row.get("evidence_role") not in _ROLES:
            raise ValueError(
                "Unsupported evidence role."
            )

        source_id = _identity(
            row.get("source_item_id"), "Source"
        )

        when = _instant(row.get("created_at"))

        if when < revision_by_id[
            row["revision_id"]
        ]["recorded_at"]:
            raise ValueError(
                "Evidence link predates its revision."
            )

        if (
            when <= cutoff
            and row["revision_id"] in visible_ids
        ):
            visible_evidence.append({
                "revision_id": row["revision_id"],
                "source_item_id": source_id,
                "role": row["evidence_role"],
                "evidence_verification": "not_verified",
                "linked_at": when.isoformat(),
            })

    current_id = current["id"] if current else None

    def format_revision(row):
        if row is None:
            return None

        if row["review_state"] != "confirmed":
            derived_state = row["review_state"]
        elif row["effective_at"] > cutoff:
            derived_state = "not_yet_effective"
        elif row["id"] == current_id:
            derived_state = "current"
        else:
            derived_state = "superseded"

        return {
            "derived_state": derived_state,
            **{
                key: deepcopy(value)
                for key, value in row.items()
                if key not in (
                    "recorded_at", "effective_at"
                )
            },
            "recorded_at": row[
                "recorded_at"
            ].isoformat(),
            "effective_at": row[
                "effective_at"
            ].isoformat(),
        }

    return {
        "schema_version": 1,
        "kind": "synthetic_revision_projection",
        "persisted": False,
        "assertion_id": assertion_id,
        "user_id": user_id,
        "project_id": project_id,
        "as_of": cutoff.isoformat(),
        "current_confirmed": format_revision(current),
        "visible_revisions": [
            format_revision(row) for row in visible
        ],
        "open_review_revision_ids": [
            row["id"] for row in visible
            if row["version_number"] > current_version
            and row["review_state"] in (
                "proposed", "disputed"
            )
        ],
        "evidence": visible_evidence,
        "has_contradictory_evidence": any(
            row["role"] == "contradicts"
            for row in visible_evidence
        ),
        "has_current_contradictory_evidence": any(
            row["role"] == "contradicts"
            and row["revision_id"] == current_id
            for row in visible_evidence
        ),
        "warnings": [
            "Evidence links do not verify factual claims.",
            "Caller must authenticate records and verify "
            "referenced source ownership.",
            "No durable revision storage exists "
            "in this prototype.",
        ],
    }
