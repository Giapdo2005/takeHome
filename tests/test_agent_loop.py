"""Day 4-5 unit tests: the pure logic in the agent loop that needs no live API
and no browser -- tool-call -> Action mapping, and observation formatting.

A full live discover() run is the evidence saved under evidence/, not a
repeatable test: too slow, too costly, and non-deterministic (a real LLM call)
to run on every `pytest`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cua.agent.loop import _tool_call_to_action
from cua.agent.prompt import format_observation
from cua.surface.base import ActionKind, Observation


def _fake_call(call_name: str, **args):
    return SimpleNamespace(name=call_name, args=args)


def test_click_call_maps_to_click_action():
    action = _tool_call_to_action(_fake_call("click", role="button", name="Search", reasoning="run the search"))
    assert action.kind is ActionKind.CLICK
    assert action.target.role == "button"
    assert action.target.name == "Search"
    assert action.intent == "run the search"


def test_type_call_carries_value():
    action = _tool_call_to_action(
        _fake_call("type", role="textbox", name="Member ID", value="100002", reasoning="enter id")
    )
    assert action.kind is ActionKind.TYPE
    assert action.value == "100002"


def test_select_call_carries_value():
    action = _tool_call_to_action(
        _fake_call("select", role="combobox", name="Account Type", value="Savings", reasoning="choose type")
    )
    assert action.kind is ActionKind.SELECT
    assert action.value == "Savings"


def test_read_call_has_no_value():
    action = _tool_call_to_action(_fake_call("read", role="cell", name="Sub-Account", reasoning="read it"))
    assert action.kind is ActionKind.READ


def test_unknown_call_name_rejected():
    with pytest.raises(ValueError):
        _tool_call_to_action(_fake_call("navigate", value="http://example.com", reasoning="go"))


def test_format_observation_includes_goal_only_on_first_call():
    obs = Observation(url="http://localhost:8080/dashboard", a11y_tree='link "Member Search"')

    with_goal = format_observation("look up member 100002", obs)
    assert with_goal.startswith("GOAL: look up member 100002")
    assert "CURRENT SCREEN" in with_goal

    without_goal = format_observation(None, obs)
    assert "GOAL:" not in without_goal
    assert without_goal.startswith("CURRENT SCREEN")
