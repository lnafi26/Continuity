"""B4 transaction orchestration for user-originated revision intents.

NOT connected to a route or database adapter.

The caller must verify the bearer token and explicit user action.
The future transaction adapter must lock the assertion row before
reading its latest revision, verify database ownership, and roll back
on any exception.

Do not activate before migration and API security review.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

_ACTIONS = {
    "propose": "proposed",
    "confirm": "confirmed",
    "dispute": "disputed",
    "reject": "rejected",
}

_EVIDENCE_ROLES = {"supports", "contradicts", "context"}

MAX_EVIDENCE = 20
MAX_VALUE_BYTES = 16384


class RevisionConflict(RuntimeError):
    """Expected revision is no longer the assertion head."""


@dataclass(frozen=True)
class UserRevisionIntent:
    project_id: str
    assertion_id: str
    expected_head_id: str | None
    action: str
    structured_value: dict
    effective_at: datetime
    evidence: tuple[tuple[str, str], ...] = ()


def _uuid(value, name):
    if not isinstance(value, str):
        raise ValueError(f"Invalid {name}.")
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError(f"Invalid {name}.") from None


def _instant(value, name):
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"Timezone-aware {name} required.")
    return value.astimezone(timezone.utc)


def _prepare(intent):
    if not isinstance(intent, UserRevisionIntent):
        raise TypeError("A typed revision intent is required.")

    project = _uuid(intent.project_id, "project ID")
    assertion = _uuid(intent.assertion_id, "assertion ID")
    head = (
        _uuid(intent.expected_head_id, "head ID")
        if intent.expected_head_id is not None
        else None
    )

    if intent.action not in _ACTIONS:
        raise ValueError("Unsupported user revision action.")

    if type(intent.structured_value) is not dict:
        raise ValueError("Revision must contain a JSON object.")

    try:
        encoded = json.dumps(
            intent.structured_value,
            allow_nan=False,
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Revision must be valid JSON.") from None

    if len(encoded) > MAX_VALUE_BYTES:
        raise ValueError("Revision content exceeds limit.")

    effective = _instant(intent.effective_at, "effective time")

    if (
        not isinstance(intent.evidence, tuple)
        or len(intent.evidence) > MAX_EVIDENCE
    ):
        raise ValueError("Invalid evidence collection.")

    checked = []
    seen = set()

    for item in intent.evidence:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("Invalid evidence reference.")

        source, role = item
        source = _uuid(source, "evidence source")

        if role not in _EVIDENCE_ROLES or (source, role) in seen:
            raise ValueError("Invalid or duplicate evidence role.")

        checked.append((source, role))
        seen.add((source, role))

    return (
        project,
        assertion,
        head,
        effective,
        checked,
        json.loads(encoded),
    )


def append_user_revision(
    *,
    verified_user_id,
    intent,
    transaction_factory,
    clock=None,
):
    """Append a user action using an atomic transaction.

    This function does not authenticate a network identity or prove
    a human clicked Confirm. The future authenticated API must do so.

    Never accept verified_user_id, actor_type, confirmed_by,
    version_number, or recorded_at directly from client payloads.

    Transaction interface:
      lock_assertion
      latest_revision
      lock_source_link
      insert_revision
      insert_evidence

    lock_assertion must SELECT FOR UPDATE before latest_revision.
    The adapter must commit on success and roll back on failure.
    """

    user = _uuid(verified_user_id, "authenticated user")

    (
        project,
        assertion_id,
        expected,
        effective,
        sources,
        value,
    ) = _prepare(intent)

    now = _instant(
        clock() if clock is not None else datetime.now(timezone.utc),
        "recorded time",
    )

    with transaction_factory() as tx:
        assertion = tx.lock_assertion(
            user_id=user,
            project_id=project,
            assertion_id=assertion_id,
        )

        if not isinstance(assertion, dict) or any(
            assertion.get(k) != v
            for k, v in (
                ("id", assertion_id),
                ("user_id", user),
                ("project_id", project),
            )
        ):
            raise PermissionError(
                "Assertion not found or inaccessible."
            )

        created = _instant(
            assertion.get("created_at"),
            "assertion creation",
        )

        if now < created or effective < created:
            raise ValueError("Revision predates its assertion.")

        head = tx.latest_revision(
            user_id=user,
            project_id=project,
            assertion_id=assertion_id,
        )

        if head is not None:
            if not isinstance(head, dict) or any(
                head.get(k) != v
                for k, v in (
                    ("user_id", user),
                    ("project_id", project),
                    ("assertion_id", assertion_id),
                )
            ):
                raise PermissionError(
                    "Revision head scope invalid."
                )

            head_id = _uuid(head.get("id"), "stored head")
            number = head.get("version_number")

            if type(number) is not int or number < 1:
                raise ValueError(
                    "Invalid stored revision sequence."
                )

            if now < _instant(
                head.get("recorded_at"),
                "previous recording",
            ):
                raise ValueError(
                    "Recording timestamp would regress."
                )

            next_number = number + 1
        else:
            head_id = None
            next_number = 1

        if expected != head_id:
            raise RevisionConflict(
                "Revision changed; refresh before applying action."
            )

        for source, _ in sources:
            link = tx.lock_source_link(
                user_id=user,
                project_id=project,
                source_item_id=source,
            )

            if not isinstance(link, dict) or any(
                link.get(k) != v
                for k, v in (
                    ("user_id", user),
                    ("project_id", project),
                    ("source_item_id", source),
                )
            ):
                raise PermissionError(
                    "Evidence source is not linked to this project."
                )

        new_id = str(uuid4())
        confirmed = intent.action == "confirm"

        row = dict(
            id=new_id,
            user_id=user,
            project_id=project,
            assertion_id=assertion_id,
            version_number=next_number,
            supersedes_revision_id=head_id,
            review_state=_ACTIONS[intent.action],
            actor_type="user",
            confirmed_by=user if confirmed else None,
            confirmed_at=now if confirmed else None,
            recorded_at=now,
            effective_at=effective,
            structured_value=deepcopy(value),
        )

        tx.insert_revision(deepcopy(row))

        for source, role in sources:
            tx.insert_evidence(dict(
                id=str(uuid4()),
                user_id=user,
                project_id=project,
                assertion_id=assertion_id,
                revision_id=new_id,
                source_item_id=source,
                evidence_role=role,
                created_at=now,
            ))

    return deepcopy(row)
