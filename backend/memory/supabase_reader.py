"""Authenticated, RLS-scoped, read-only Supabase memory retrieval.

Not exposed as a Flask route. No automatic inference or writes.
"""
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

import requests

from backend.auth.supabase_auth import verify_access_token
from backend.memory.context import build_project_context


class MemoryReadUnavailable(RuntimeError):
    """Sanitized error; never contains response bodies or tokens."""


LIMIT = 20

SELECT = {
    "projects": (
        "id,user_id,name,summary,origin"
    ),
    "project_events": (
        "id,user_id,project_id,event_type,title,"
        "event_date,source_item_id,user_edited"
    ),
    "project_actions": (
        "id,user_id,project_id,title,status,"
        "completed,due_date"
    ),
    "project_source_links": (
        "user_id,project_id,source_item_id,"
        "review_status"
    ),
}


def _base_url(value):
    if not isinstance(value, str):
        raise ValueError("Invalid Supabase URL.")

    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.hostname.endswith(".supabase.co")
            and parsed.netloc == parsed.hostname
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False

    if not valid:
        raise ValueError("Invalid Supabase URL.")

    return "https://" + parsed.hostname


def _uuid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid project identity.") from None


def _get_rows(base, key, authorization, table, params):
    if table not in SELECT:
        raise ValueError("Unsupported table.")

    query = dict(params)
    query["select"] = SELECT[table]

    try:
        response = requests.get(
            f"{base}/rest/v1/{table}",
            headers={
                "apikey": key,
                "Authorization": authorization,
                "Accept": "application/json",
                "Cache-Control": "no-store",
            },
            params=query,
            timeout=8,
            allow_redirects=False,
        )

        if response.status_code != 200:
            raise MemoryReadUnavailable(
                "Project records unavailable."
            )

        rows = response.json()
    except requests.RequestException:
        raise MemoryReadUnavailable(
            "Project records unavailable."
        ) from None
    except ValueError:
        raise MemoryReadUnavailable(
            "Invalid project record response."
        ) from None

    if not isinstance(rows, list):
        raise MemoryReadUnavailable(
            "Invalid project record response."
        )

    if len(rows) > LIMIT or any(
        not isinstance(row, dict) for row in rows
    ):
        raise MemoryReadUnavailable(
            "Unexpected project record response."
        )

    return rows


def fetch_project_context(
    authorization_header,
    *,
    supabase_url,
    publishable_key,
    project_id,
):
    """Read a bounded context under a verified user's RLS identity.

    All retrievals use the user's bearer token, never service_role.
    The resulting snapshot is ephemeral and potentially incomplete.
    """
    base = _base_url(supabase_url)
    pid = _uuid(project_id)

    if (
        not isinstance(publishable_key, str)
        or not publishable_key.startswith("sb_publishable_")
    ):
        raise ValueError("Publishable key required.")

    user_id = verify_access_token(
        authorization_header,
        supabase_url=base,
        publishable_key=publishable_key,
    )
    user_id = str(UUID(user_id))

    scope = {
        "user_id": f"eq.{user_id}",
        "project_id": f"eq.{pid}",
        "limit": str(LIMIT),
    }

    projects = _get_rows(
        base, publishable_key, authorization_header,
        "projects",
        {
            "id": f"eq.{pid}",
            "user_id": f"eq.{user_id}",
            "limit": "1",
        },
    )

    if not projects:
        raise LookupError("Project not found or inaccessible.")

    if len(projects) != 1:
        raise MemoryReadUnavailable(
            "Unexpected project response."
        )

    project = projects[0]
    if (
        str(project.get("id")) != pid
        or str(project.get("user_id")) != user_id
    ):
        raise PermissionError("Project ownership mismatch.")

    events = _get_rows(
        base, publishable_key, authorization_header,
        "project_events",
        {
            **scope,
            "order": "event_date.desc",
        },
    )

    actions = _get_rows(
        base, publishable_key, authorization_header,
        "project_actions",
        {
            **scope,
            "completed": "eq.false",
            "status": "neq.completed",
            "order": "created_at.desc",
        },
    )

    links = _get_rows(
        base, publishable_key, authorization_header,
        "project_source_links",
        {
            **scope,
            "order": "created_at.desc",
        },
    )

    result = build_project_context(
        project, events, actions, links,
        as_of=datetime.now(timezone.utc),
    )

    # The builder's counts reflect fetched rows, not total
    # database records. Never claim complete project history.
    result["retrieval"] = {
        "authenticated": True,
        "rls_scoped": True,
        "limit_per_collection": LIMIT,
        "completeness": "bounded_partial",
        "source": "supabase_data_api",
    }

    result["warnings"].append(
        "Counts reflect bounded retrieved rows, not full totals."
    )

    return result
