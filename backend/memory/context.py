"""Read-only, source-aware project context assembly.

No database connection, remote inference, ingestion, or writes.
Authorization must occur at the database/repository boundary.
"""
from collections.abc import Mapping
from datetime import datetime, timezone


def _timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Timestamp must include a timezone.")
    return value.astimezone(timezone.utc).isoformat()


def _scoped(rows, user_id, project_id, label):
    if not isinstance(rows, (list, tuple)):
        raise TypeError(f"{label} must be a collection.")

    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError(f"Invalid {label} row.")
        if (
            str(row.get("user_id")) != user_id
            or str(row.get("project_id")) != project_id
        ):
            raise PermissionError(
                f"Cross-project or cross-user {label} rejected."
            )
        result.append(row)
    return result


def build_project_context(
    project, events, actions, source_links, *, as_of
):
    """Assemble an ephemeral, non-authoritative context snapshot."""
    if not isinstance(project, Mapping):
        raise TypeError("Project must be a record.")

    user_id = str(project.get("user_id") or "")
    project_id = str(project.get("id") or "")

    if not user_id or not project_id:
        raise ValueError("Project identity and owner required.")

    timestamp = _timestamp(as_of)
    events = _scoped(events, user_id, project_id, "events")
    actions = _scoped(actions, user_id, project_id, "actions")
    links = _scoped(
        source_links, user_id, project_id, "source links"
    )

    link_status = {
        str(row["source_item_id"]): row.get(
            "review_status", "pending"
        )
        for row in links
        if row.get("source_item_id") is not None
    }

    historical = []
    for event in events:
        source_id = event.get("source_item_id")
        historical.append({
            "id": str(event.get("id", "")),
            "type": event.get("event_type"),
            "title": event.get("title", ""),
            "occurred_at": _timestamp(event["event_date"]),
            "source_item_id": (
                str(source_id) if source_id is not None else None
            ),
            "source_link_status": (
                link_status.get(str(source_id), "link_not_in_snapshot")
                if source_id is not None else "no_source"
            ),
            "evidence_verification": "not_verified",
            "user_edited": event.get("user_edited") is True,
        })

    historical.sort(
        key=lambda row: row["occurred_at"], reverse=True
    )

    open_actions = [
        {
            "id": str(row.get("id", "")),
            "title": row.get("title", ""),
            "status": row.get("status", "not_started"),
            "due_date": (
                str(row["due_date"])
                if row.get("due_date") is not None else None
            ),
        }
        for row in actions
        if row.get("completed") is not True
        and row.get("status") != "completed"
    ]

    return {
        "schema_version": 1,
        "kind": "derived_read_only",
        "persisted": False,
        "as_of": timestamp,
        "project": {
            "id": project_id,
            "user_id": user_id,
            "name": project.get("name", ""),
            "summary": project.get("summary", ""),
            "origin": project.get("origin", "unknown"),
        },
        "counts": {
            "events": len(historical),
            "open_actions": len(open_actions),
            "source_links": len(links),
        },
        "recent_events": historical[:20],
        "open_actions": open_actions[:20],
        "warnings": [
            "Source links do not verify extracted claims.",
            "A missing link in a bounded snapshot does not prove that no association exists.",
            "Context must be retrieved under authenticated RLS.",
            "This snapshot is not durable project memory.",
        ],
    }
