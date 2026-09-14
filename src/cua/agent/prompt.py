"""
The discovery loop's prompt: system instruction + tool surface.

Deliberately NOT exposed as tools: `navigate` (the harness performs the one
navigation, plus login, as a deterministic setup step -- see agent/loop.py --
the model only ever clicks links within the already-open app) and `wait`
(Playwright auto-waits; there's no injected slowness until Day 8).

This file plus loop.py are the only two files in the project that know a
specific LLM provider exists. Swapping providers means editing these two files;
nothing else in the system changes.
"""

from __future__ import annotations

from google.genai import types

from cua.surface.base import Observation

SYSTEM_INSTRUCTION = """\
You operate a real web application one action at a time, on behalf of an \
automation system. You will be told a GOAL and, after every action, the \
CURRENT SCREEN as a list of elements (their accessibility role and name -- \
the same thing a screen reader would see). You cannot see pixels or layout, \
only this list.

Rules:
- Call exactly one tool per turn. Never call more than one, never call none.
- Only act on elements that literally appear in the CURRENT SCREEN listing. \
Never guess at an element's name. If you can't find something you expect, \
look again at what IS listed rather than inventing a name.
- Use the exact `role` and `name` as they appear in the listing.
- Call `finish` the INSTANT the CURRENT SCREEN matches what the goal \
describes. If the goal says to "reach" a screen, that screen being displayed \
IS the finish condition -- do not take any further action on it, even if a \
button on it looks like a natural next step.
- Never click a control that finalizes, confirms, submits, deletes, closes, \
transfers, or otherwise commits an irreversible change UNLESS the goal \
explicitly and literally asks you to complete that exact action. When in \
doubt, treat the screen you are on as the destination and call `finish`.
- Call `stuck` if the goal seems unreachable, if no visible element lets you \
proceed, or if an action has already failed once and you have no other idea. \
Do not repeat a failing action.
"""

CLICK = types.FunctionDeclaration(
    name="click",
    description="Click a button or link on the current screen.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "role": {"type": "string", "description": "Accessibility role, e.g. 'button' or 'link'."},
            "name": {"type": "string", "description": "The exact accessible name of the element."},
            "reasoning": {"type": "string", "description": "One sentence: why this makes progress."},
        },
        "required": ["role", "name", "reasoning"],
    },
)

TYPE = types.FunctionDeclaration(
    name="type",
    description="Type text into a textbox on the current screen.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "name": {"type": "string"},
            "value": {"type": "string", "description": "The text to type."},
            "reasoning": {"type": "string"},
        },
        "required": ["role", "name", "value", "reasoning"],
    },
)

SELECT = types.FunctionDeclaration(
    name="select",
    description="Choose an option in a dropdown/combobox on the current screen.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "name": {"type": "string"},
            "value": {"type": "string", "description": "The option's value/label to select."},
            "reasoning": {"type": "string"},
        },
        "required": ["role", "name", "value", "reasoning"],
    },
)

READ = types.FunctionDeclaration(
    name="read",
    description="Read the text of an element on the current screen. No side effect.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "name": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": ["role", "name", "reasoning"],
    },
)

FINISH = types.FunctionDeclaration(
    name="finish",
    description="Call when the CURRENT SCREEN shows the goal has been reached. Stops the run.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "reasoning": {"type": "string", "description": "What on the screen shows the goal is met."},
        },
        "required": ["reasoning"],
    },
)

STUCK = types.FunctionDeclaration(
    name="stuck",
    description="Call when you cannot safely proceed and a human should take over. Stops the run.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "reasoning": {"type": "string", "description": "What you tried and why you're stuck."},
        },
        "required": ["reasoning"],
    },
)

TOOL = types.Tool(function_declarations=[CLICK, TYPE, SELECT, READ, FINISH, STUCK])

UI_ACTION_NAMES = {"click", "type", "select", "read"}
CONTROL_NAMES = {"finish", "stuck"}


def format_observation(goal: str | None, observation: Observation) -> str:
    """The text block sent each turn.

    `goal` is only passed on turn 1. The model retains it on every later turn
    purely because `contents` keeps growing and gets resent in full each call
    (see loop.py) -- we never need to repeat the goal ourselves.
    """
    header = f"GOAL: {goal}\n\n" if goal else ""
    return f"{header}CURRENT SCREEN (url: {observation.url}):\n{observation.a11y_tree}"
