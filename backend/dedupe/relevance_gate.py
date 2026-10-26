"""LLM work-gate for Stage 3 (the 'judge work vs. not-work' layer).

Runs a cheap model (Haiku 4.5) to decide whether an item is WORK the recipient
should track -- projects, tasks, assignments, team/manager meetings,
conferences, work training, project discussions/decisions, and interviews the
recipient attends or conducts (recruiter interviews, interview panels) -- versus
anything else: personal errands, entertainment/social plans, job alerts and
job-board digests, applications the recipient submitted, marketing, and personal
finance/shopping.

Unlike a spam filter this is a topic filter: personal mail from a real person
(a friend asking a favour, a doctor's appointment reminder) is not "noise" but
is still NOT work, so only an LLM can separate it reliably. It fails OPEN
(returns True) so a transient API error keeps a possibly-work item rather than
silently discarding real project data.
"""

from __future__ import annotations

DEFAULT_GATE_MODEL = "claude-haiku-4-5"

_SYSTEM = (
    "You classify a working professional's inbox into WORK vs NOT-WORK. "
    "Answer with only 'work' or 'not_work', nothing else."
)


def _prompt(sender: str | None, title: str | None, text: str | None) -> str:
    return (
        "Classify the following email or calendar item as 'work' or 'not_work' "
        "for a working professional.\n\n"
        "WORK includes: their projects, tasks and assignments; team meetings, "
        "manager 1:1s, and planning sessions; work conferences and internal "
        "summits; training or learning for their job; discussions, decisions, "
        "and differing opinions about a project; and interviews they attend or "
        "conduct as part of their job (recruiter interviews, interview panels, "
        "candidate reviews).\n\n"
        "NOT_WORK includes: personal errands and appointments (doctor, dentist, "
        "picking up a pet or child, groceries); entertainment and social plans "
        "(concerts, dinners, sports, parties); job alerts and job-board digests; "
        "confirmations of job applications they submitted; marketing, "
        "promotions, and newsletters; and personal finance or shopping.\n\n"
        f"From: {sender or '(unknown)'}\n"
        f"Subject: {title or '(no subject)'}\n"
        f"Body: {(text or '')[:600]}\n\n"
        "Answer with only 'work' or 'not_work'."
    )


def is_work_related(
    sender: str | None,
    title: str | None,
    text: str | None,
    *,
    api_key: str,
    model: str = DEFAULT_GATE_MODEL,
) -> bool:
    """Return True if the item is WORK and should be KEPT for grouping.

    Fails OPEN: on any API/parse error returns True so genuine work items are
    never dropped because of a transient failure. Only a confident 'not_work'
    answer excludes an item.
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=5,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _prompt(sender, title, text)}],
        )
        answer = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        ).strip().lower()
        # Only an explicit not-work verdict excludes; anything else keeps.
        return not answer.startswith("not")
    except Exception:  # noqa: BLE001 - fail open; keep possibly-work items
        return True
