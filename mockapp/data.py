"""Seed data for the mock credit-union console.

In-memory only — resets every time the app restarts. This is intentional: the
mock app's job is to exercise the automation problem (a multi-step flow with a
findable/not-findable search and a form + confirmation step), not to be real
infrastructure. Exact-match search only, per the Day 2 scope decision.
"""

from __future__ import annotations

MEMBERS: dict[str, dict[str, str]] = {
    "100002": {"name": "J. Rivera", "status": "Active"},
    "100010": {"name": "A. Chen", "status": "Active"},
}

_next_subaccount_seq = 4471


def find_member(member_id: str) -> dict[str, str] | None:
    return MEMBERS.get(member_id.strip())


def next_subaccount_number() -> str:
    """Not persisted anywhere — the confirmation screen is the capability's
    success condition; nothing downstream depends on this number being stable.
    """
    global _next_subaccount_seq
    number = f"SA-{_next_subaccount_seq}"
    _next_subaccount_seq += 1
    return number
