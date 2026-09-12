"""Day 1 smoke test #2 — prove the Gemini API works and returns a structured action.

This is the shape of ONE turn of the discovery loop:
  - we describe the current screen as text (here: hardcoded),
  - we offer the model a set of tools / function declarations (here: just `choose_action`),
  - we force it to call one (function_calling_config mode ANY),
  - the model replies with a function_call naming the action + args,
  - we read function_call.args into a plain dict.

Day 4 replaces the hardcoded screen with a real Observation and actually performs
the action. Nothing else about this changes. The provider lives only here and in
agent/loop.py + agent/prompt.py — swapping it does not touch the rest of the system.

Run:  python scripts/hello_gemini.py
Pass: prints a parsed action dict like {'kind': 'type', 'target_name': 'Member ID', 'value': '100002'}
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.environ.get("CUA_MODEL", "gemini-3.6-flash")

FAKE_SCREEN = """\
url: http://localhost:8080/search
- textbox "Member ID"
- button "Search"
- link "Logout"
"""

GOAL = "Look up member 100002."

SYSTEM = (
    "You operate a web UI one action at a time. You are given the goal and a text "
    "rendering of the current screen. Call choose_action with the single next step."
)

# One function. The real loop will have click / type / navigate / read / finish / stuck.
CHOOSE_ACTION = types.FunctionDeclaration(
    name="choose_action",
    description="Pick the single next UI action that makes progress toward the goal.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["navigate", "click", "type", "select", "read", "finish"],
            },
            "target_name": {
                "type": "string",
                "description": "Accessible name of the element to act on (omit for navigate/finish).",
            },
            "value": {
                "type": "string",
                "description": "Text to type, option to select, or URL to navigate to.",
            },
            "reasoning": {"type": "string", "description": "One sentence: why this action."},
        },
        "required": ["kind", "reasoning"],
    },
)


def main() -> None:
    client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY from env / .env

    tool = types.Tool(function_declarations=[CHOOSE_ACTION])

    resp = client.models.generate_content(
        model=MODEL,
        contents=f"GOAL: {GOAL}\n\nCURRENT SCREEN:\n{FAKE_SCREEN}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=[tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",  # force a function call
                    allowed_function_names=["choose_action"],
                )
            ),
        ),
    )

    usage = resp.usage_metadata
    print(f"model:  {MODEL}")
    print(f"usage:  in={usage.prompt_token_count} out={usage.candidates_token_count}")

    calls = resp.function_calls or []
    if not calls:
        raise SystemExit(f"FAIL — no function call returned. Raw text: {resp.text!r}")

    action = dict(calls[0].args)
    print("\nparsed action:")
    for k, v in action.items():
        print(f"  {k}: {v!r}")
    print("\nOK — Gemini API + function calling works.")


if __name__ == "__main__":
    main()
