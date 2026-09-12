"""The Surface seam.

A `Surface` is the ONLY thing in the system that touches a live UI. Everything
above it — the agent loop, the recorder, the replay engine — is surface-agnostic
and talks only through these types.

Why this matters (REPORT sections 1 and 4): to add a legacy web app or a desktop
app later, you write a new class that implements `Surface` (reading the OS/browser
accessibility tree, driving the mouse, etc.). None of the loop / artifact / replay
code changes, because it only knows `observe()` and `act()`.

Built: Day 1 (types). BrowserSurface implementation: Day 3.
"""

from __future__ import annotations

import datetime as _dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ActionKind(str, Enum):
    """The verbs a Surface can perform. Deliberately small.

    Kept in sync with `schema.ActionKind` — the artifact records the same verbs
    the loop issues, so a step maps 1:1 onto an `Action` at replay time.
    """

    NAVIGATE = "navigate"  # go to a URL
    CLICK = "click"
    TYPE = "type"  # type text into a field
    SELECT = "select"  # choose an option in a <select> / combobox
    READ = "read"  # extract a value from an element (no side effect)
    WAIT = "wait"  # wait for a condition (load, element, timeout)


class ElementQuery(BaseModel):
    """A single, simple way to point at one element at the Surface boundary.

    This is NOT the artifact's rich multi-strategy `Locator` (see schema.py).
    The replay engine's job is to reduce a `Locator` to a sequence of these and
    try them in priority order; the discovery loop produces one directly from
    what the LLM said ("the button named 'Search'").
    """

    role: str | None = None  # ARIA role: "button", "textbox", "link", "row", ...
    name: str | None = None  # accessible name / visible label
    text: str | None = None  # visible text substring
    css: str | None = None  # last-resort raw selector
    nth: int | None = None  # disambiguate when several match (0-indexed)

    def describe(self) -> str:
        parts = [f"{k}={v!r}" for k, v in self.model_dump(exclude_none=True).items()]
        return "ElementQuery(" + ", ".join(parts) + ")"


class Action(BaseModel):
    """One thing to do on the surface."""

    kind: ActionKind
    target: ElementQuery | None = None  # None only for NAVIGATE
    value: str | None = None  # text to type / option to select / url to navigate
    # Free-text rationale from whoever produced this action (the LLM during
    # discovery). Recorded as the step's `intent`. Never contains secrets.
    intent: str | None = None


class Observation(BaseModel):
    """A snapshot of the current surface state. Fed to the LLM during discovery
    and checked against checkpoints during replay.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: str
    title: str = ""
    # A compact TEXT rendering of the accessibility tree — the PRIMARY signal.
    # The Surface owns the formatting so the rest of the system never sees raw
    # Playwright/OS objects. For BrowserSurface this is Playwright's aria_snapshot
    # (YAML-ish), e.g.:  - textbox "Member ID"
    #                    - button "Search"
    a11y_tree: str = ""
    # PNG bytes. SECONDARY signal + evidence. May be b"" if capture failed.
    screenshot: bytes = b""
    captured_at: _dt.datetime = Field(default_factory=lambda: _dt.datetime.now(_dt.UTC))


class ActionOutcome(BaseModel):
    """The result of `Surface.act()`. Never raises for expected conditions —
    the caller decides what a failure means (business outcome vs hard failure).
    """

    ok: bool
    url_after: str
    error: str | None = None  # populated when ok is False
    read_value: str | None = None  # populated for successful READ actions


class Surface:
    """Interface every concrete surface implements. Plain class (not typing.Protocol)
    so implementations can inherit shared helpers later if useful.

    Lifetime note (REPORT section 5): a Surface must be able to outlive a single
    discover/replay call so a human can take over the *same* live session during
    an escalation. Don't tear it down inside the loop; own it at the CLI level.
    """

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def observe(self) -> Observation:
        raise NotImplementedError

    def act(self, action: Action) -> ActionOutcome:
        raise NotImplementedError

    @property
    def current_url(self) -> str:
        raise NotImplementedError
