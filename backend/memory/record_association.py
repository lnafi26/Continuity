"""B4.7a: Scoped, offline project-record-to-memory association contract.

No database, network, inference, persistence or authentication operations.
Caller must supply authenticated, authorized records.
A prepared association is never evidence that a link was saved or confirmed.
"""
import re
from collections.abc import Mapping
from uuid import UUID

_MAX_BIGINT = 9223372036854775807
_DECIMAL = re.compile(r"[1-9][0-9]{0,18}\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\Z",
    re.I,
)


def _uuid(value, label):
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        raise ValueError(f"Invalid {label} UUID.")
    return str(UUID(value))


def _record_id(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise ValueError("Invalid BIGINT record identity.")
    if int(value) > _MAX_BIGINT:
        raise ValueError("BIGINT record identity exceeds range.")
    return value


def _owned(row, user_id, project_id, label):
    if not isinstance(row, Mapping):
        raise TypeError(f"{label} record required.")

    if (
        _uuid(row.get("user_id"), "owner") != user_id
        or _uuid(row.get("project_id"), "project") != project_id
    ):
        raise PermissionError(f"{label} is outside the requested scope.")


def prepare_record_association(
    *,
    user_id,
    project_id,
    record_kind,
    record_id,
    record,
    assertion,
):
    """Validate an explicit association against supplied scoped records.

    The output is a non-durable preview, not a saved or verified link.
    No title-based matching, automatic creation, or authorization lookup.
    """
    owner = _uuid(user_id, "user")
    project = _uuid(project_id, "project")

    if record_kind not in ("event", "action"):
        raise ValueError("Unsupported project record kind.")

    selected_id = _record_id(record_id)

    _owned(record, owner, project, "Project record")
    _owned(assertion, owner, project, "Memory assertion")

    if _record_id(record.get("id")) != selected_id:
        raise PermissionError("Selected record identity mismatch.")

    assertion_id = _uuid(assertion.get("id"), "assertion")

    return {
        "schema_version": 1,
        "kind": "record_memory_association_preview",
        "persisted": False,
        "confirmed": False,
        "user_id": owner,
        "project_id": project,
        "record_kind": record_kind,
        "record_id": selected_id,
        "assertion_id": assertion_id,
    }
