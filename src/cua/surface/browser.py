"""BrowserSurface — the Playwright-backed implementation of Surface.

This is the ONLY file in the project that imports Playwright. Everything above
the Surface seam (the future agent loop, recorder, replay engine) talks only to
observe()/act() and has no idea this file exists. See surface/base.py for why
that boundary matters.

Built: Day 3, driven end to end by a HARDCODED action list
(scripts/drive_subaccount_flow.py) — no LLM involved yet.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page, sync_playwright

from cua.surface.base import Action, ActionKind, ActionOutcome, ElementQuery, Observation, Surface


class BrowserSurface(Surface):
    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._page: Page | None = None

    # --- lifecycle -----------------------------------------------------
    # Deliberately explicit start()/stop() rather than a context manager:
    # the escalation design (Day 9) needs this browser to stay alive and
    # paused across a human handoff, not torn down between calls.

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._page = self._browser.new_page()

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    @property
    def current_url(self) -> str:
        return self._require_page().url

    # --- perception ------------------------------------------------------

    def observe(self) -> Observation:
        page = self._require_page()
        try:
            a11y = page.locator("body").aria_snapshot()
        except Exception as exc:  # page mid-navigation, no body yet, etc.
            a11y = f"<failed to capture accessibility tree: {exc}>"
        try:
            screenshot = page.screenshot()
        except Exception:
            screenshot = b""
        return Observation(url=page.url, title=page.title(), a11y_tree=a11y, screenshot=screenshot)

    # --- action ------------------------------------------------------------

    def act(self, action: Action) -> ActionOutcome:
        page = self._require_page()
        try:
            if action.kind is ActionKind.NAVIGATE:
                page.goto(action.value, wait_until="load")
                return ActionOutcome(ok=True, url_after=page.url)

            if action.kind is ActionKind.WAIT:
                if action.target is not None:
                    self._resolve(action.target).wait_for(state="visible")
                else:
                    page.wait_for_load_state("load")
                return ActionOutcome(ok=True, url_after=page.url)

            # CLICK / TYPE / SELECT / READ all act on a resolved target.
            locator = self._resolve(action.target)

            if action.kind is ActionKind.CLICK:
                locator.click()
            elif action.kind is ActionKind.TYPE:
                locator.fill(action.value or "")
            elif action.kind is ActionKind.SELECT:
                locator.select_option(action.value)
            elif action.kind is ActionKind.READ:
                value = locator.inner_text()
                return ActionOutcome(ok=True, url_after=page.url, read_value=value)
            else:
                return ActionOutcome(ok=False, url_after=page.url, error=f"unhandled action kind: {action.kind}")

            return ActionOutcome(ok=True, url_after=page.url)

        except Exception as exc:
            # Playwright's TimeoutError, a strict-mode violation (ambiguous
            # match), a disappeared element, etc. Never raise past this point —
            # the caller (agent loop / replay engine) decides what a failed
            # action means; this class only reports what happened.
            return ActionOutcome(ok=False, url_after=page.url, error=str(exc))

    # --- helpers ----------------------------------------------------------

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserSurface.start() must be called before use")
        return self._page

    def _resolve(self, query: ElementQuery | None) -> Locator:
        """Turn ONE ElementQuery into ONE Playwright locator, best-signal first.

        This is single-strategy resolution — given a hint, produce a locator.
        Trying several candidate ElementQueries in priority order and falling
        back when one doesn't resolve is the artifact's multi-strategy
        `Locator` bundle's job (replay/locators.py, Day 7), not this method's.

        Playwright's locators are "strict" by default: if a query matches more
        than one element, the action raises rather than guessing — we don't
        need to write ambiguity detection ourselves.
        """
        page = self._require_page()
        if query is None:
            raise ValueError("this action requires a target ElementQuery")

        # exact=True on both: our locators are meant to be precise semantic
        # handles, not fuzzy text search. Without it, Playwright's default
        # substring match can silently resolve to the wrong element whenever
        # one accessible name is a substring of another (e.g. "Member Search"
        # vs. "Go to Member Search") -- discovered by the Day 3 integration
        # test failing exactly this way.
        if query.role and query.name:
            locator = page.get_by_role(query.role, name=query.name, exact=True)
        elif query.role:
            locator = page.get_by_role(query.role)
        elif query.text:
            locator = page.get_by_text(query.text, exact=True)
        elif query.css:
            locator = page.locator(query.css)
        else:
            raise ValueError(f"ElementQuery has no usable field to resolve: {query.describe()}")

        if query.nth is not None:
            locator = locator.nth(query.nth)
        return locator
