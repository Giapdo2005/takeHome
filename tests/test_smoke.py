"""Day 1: the package imports and the Surface types behave. No browser, no API."""

from __future__ import annotations

from cua.surface import Action, ActionKind, ElementQuery, Observation


def test_action_roundtrips_through_json():
    a = Action(
        kind=ActionKind.TYPE,
        target=ElementQuery(role="textbox", name="Member ID"),
        value="100002",
        intent="enter the member id",
    )
    restored = Action.model_validate_json(a.model_dump_json())
    assert restored == a
    assert restored.kind is ActionKind.TYPE


def test_bad_action_kind_is_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Action(kind="frobnicate")  # not a valid ActionKind


def test_observation_allows_empty_screenshot():
    obs = Observation(url="http://localhost:8080/", a11y_tree='button "Search"')
    assert obs.screenshot == b""
    assert obs.captured_at is not None
