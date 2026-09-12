"""Day 3 integration test — the one piece of browser-touching code worth a real
regression test, since the agent loop, recorder, and replay engine (Days 4-7)
all depend on BrowserSurface behaving correctly against the real mock app.

Starts the mock app in a background thread (a real Flask server, not mocked)
and drives it with the same hardcoded action list scripts/drive_subaccount_flow.py
uses, headless.
"""

from __future__ import annotations

import threading

import pytest
from werkzeug.serving import make_server

from cua.surface.browser import BrowserSurface
from mockapp.app import app as flask_app
from scripts.drive_subaccount_flow import run

TEST_PORT = 8099


class _ServerThread(threading.Thread):
    def __init__(self, app, port: int) -> None:
        super().__init__(daemon=True)
        self._server = make_server("127.0.0.1", port, app)

    def run(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()


@pytest.fixture(scope="session")
def mockapp_url():
    thread = _ServerThread(flask_app, TEST_PORT)
    thread.start()
    yield f"http://127.0.0.1:{TEST_PORT}"
    thread.shutdown()


@pytest.fixture
def surface():
    s = BrowserSurface(headless=True)
    s.start()
    yield s
    s.stop()


def test_subaccount_flow_reaches_review_screen(mockapp_url, surface):
    final = run(surface, mockapp_url)
    assert "SA-" in final.a11y_tree
