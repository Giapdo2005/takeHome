"""Day 4 Step 0 — verify the exact multi-turn function-calling shape with the
installed google-genai SDK before wiring the real loop. Two turns: the model
calls a tool, we send a function_response back, the model calls a tool again —
proving it "remembers" turn 1 purely because we resent the growing `contents`
list, not because the model has any memory of its own.

Throwaway verification script, not part of the shipped system. Run:
    python scripts/verify_multiturn_gemini.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
MODEL = os.environ.get("CUA_MODEL", "gemini-3.6-flash")

CLICK = types.FunctionDeclaration(
    name="click",
    description="Click a button or link on the current screen.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Accessible name of the element."},
            "reasoning": {"type": "string"},
        },
        "required": ["name", "reasoning"],
    },
)
FINISH = types.FunctionDeclaration(
    name="finish",
    description="Call when the goal has been reached.",
    parameters_json_schema={
        "type": "object",
        "properties": {"reasoning": {"type": "string"}},
        "required": ["reasoning"],
    },
)

tool = types.Tool(function_declarations=[CLICK, FINISH])
config = types.GenerateContentConfig(
    system_instruction="You operate a UI one action at a time by calling exactly one tool per turn.",
    tools=[tool],
    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY")),
)

client = genai.Client()

contents = [
    types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    "GOAL: open the search results.\n\n"
                    "CURRENT SCREEN:\n- link \"Search\"\n- link \"Reports\""
                )
            )
        ],
    )
]

print("--- turn 1 ---")
resp1 = client.models.generate_content(model=MODEL, contents=contents, config=config)
call1 = resp1.function_calls[0]
print("model called:", call1.name, dict(call1.args))
print("resp1.candidates[0].content.role:", resp1.candidates[0].content.role)

# The model's own turn must be appended verbatim, or it will have no memory of
# having called anything.
contents.append(resp1.candidates[0].content)

fr_part = types.Part.from_function_response(
    name=call1.name,
    response={"ok": True, "new_screen": '- heading "Search Results"\n- text "3 results found"'},
)
function_response_content = types.Content(role="user", parts=[fr_part])
contents.append(function_response_content)

print("\n--- turn 2 ---")
resp2 = client.models.generate_content(model=MODEL, contents=contents, config=config)
call2 = resp2.function_calls[0]
print("model called:", call2.name, dict(call2.args))

print(f"\nlen(contents) after 2 turns: {len(contents)}")
print("OK — multi-turn function calling verified with role='user' for function_response.")
