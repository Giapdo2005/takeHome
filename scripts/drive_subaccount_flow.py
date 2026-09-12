"""Day 3 acceptance test — drive the full sub-account flow with a HARDCODED
action list (no LLM) against BrowserSurface. Proves the Surface abstraction and
the ElementQuery -> Playwright locator mapping both work against the real mock
app, including its table-based, no-test-id markup.

`build_actions` / `run` are imported by tests/test_browser_surface.py so the
action list is defined exactly once. Run this file directly to watch it happen
in a visible browser:

    python scripts/drive_subaccount_flow.py                # http://localhost:8080
    python scripts/drive_subaccount_flow.py http://host:port
    CUA_HEADLESS=1 python scripts/drive_subaccount_flow.py  # no visible window
"""

from __future__ import annotations

import os
import sys

from cua.surface import Action, ActionKind, ElementQuery, Surface
from cua.surface.browser import BrowserSurface

MEMBER_ID = "100002"


def build_actions(base_url: str) -> list[Action]:
    return [
        Action(kind=ActionKind.NAVIGATE, value=f"{base_url}/login", intent="open the console"),
        Action(
            kind=ActionKind.TYPE,
            target=ElementQuery(role="textbox", name="Username"),
            value="operator",
            intent="enter username",
        ),
        Action(
            kind=ActionKind.TYPE,
            target=ElementQuery(role="textbox", name="Password"),
            value="pw",
            intent="enter password",
        ),
        Action(
            kind=ActionKind.CLICK,
            target=ElementQuery(role="button", name="Sign In"),
            intent="log in",
        ),
        Action(
            kind=ActionKind.CLICK,
            target=ElementQuery(role="link", name="Member Search"),
            intent="go to member search",
        ),
        Action(
            kind=ActionKind.TYPE,
            target=ElementQuery(role="textbox", name="Member ID"),
            value=MEMBER_ID,
            intent="enter member id",
        ),
        Action(
            kind=ActionKind.CLICK,
            target=ElementQuery(role="button", name="Search"),
            intent="run search",
        ),
        Action(
            kind=ActionKind.CLICK,
            target=ElementQuery(role="link", name="View"),
            intent="open member detail",
        ),
        Action(
            kind=ActionKind.CLICK,
            target=ElementQuery(role="link", name="Add Sub-Account"),
            intent="start new sub-account",
        ),
        Action(
            kind=ActionKind.SELECT,
            target=ElementQuery(role="combobox", name="Account Type"),
            value="Savings",
            intent="choose account type",
        ),
        Action(
            kind=ActionKind.TYPE,
            target=ElementQuery(role="textbox", name="Initial Deposit"),
            value="50",
            intent="enter initial deposit",
        ),
        Action(
            kind=ActionKind.CLICK,
            target=ElementQuery(role="button", name="Review"),
            intent="review the new sub-account",
        ),
    ]


def run(surface: Surface, base_url: str):
    """Execute the hardcoded flow against `surface`. Returns the final
    Observation. Raises AssertionError the moment any step fails, or if the
    final screen isn't the review page.
    """
    for i, action in enumerate(build_actions(base_url)):
        outcome = surface.act(action)
        status = "ok" if outcome.ok else f"ERROR: {outcome.error}"
        print(f"[{i:2d}] {action.kind.value:8s} {action.intent:30s} -> {status}")
        assert outcome.ok, f"step {i} ({action.intent}) failed: {outcome.error}"

    # One READ, to exercise the last ActionKind and preview how a Day-6
    # OutputSpec will pull a value off a final screen. Deliberately uses the
    # css fallback strategy (no stable role+name exists for a bare table
    # cell) -- a live example of why css is the LAST-resort locator kind.
    read_outcome = surface.act(
        Action(
            kind=ActionKind.READ,
            target=ElementQuery(css="tr:has-text('Sub-Account') td:nth-child(2)"),
            intent="read the generated sub-account number",
        )
    )
    print(f"[read] sub-account number -> {read_outcome.read_value!r}")
    assert read_outcome.ok, f"read failed: {read_outcome.error}"

    final = surface.observe()
    assert "Review New Sub-Account" in final.a11y_tree, "did not land on the review screen"
    return final


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MOCKAPP_URL", "http://localhost:8080")
    headless = os.environ.get("CUA_HEADLESS", "0") == "1"

    surface = BrowserSurface(headless=headless)
    surface.start()
    try:
        final = run(surface, base_url)
        print("\n--- final screen a11y ---")
        print(final.a11y_tree)
        print("\nOK — BrowserSurface drove the full flow with no LLM.")
    finally:
        surface.stop()


if __name__ == "__main__":
    main()
