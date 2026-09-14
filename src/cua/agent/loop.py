"""
The discovery loop: observe -> decide (Gemini) -> act, until finish/stuck/max_steps.

This file plus prompt.py are the only two files that know a specific LLM
provider exists. Everything below Surface has no idea this file is calling an
API at all.

Login is a deterministic harness step (see _perform_login), not an LLM
decision -- credentials never enter the model's context or the evidence log.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from cua.agent.prompt import TOOL, SYSTEM_INSTRUCTION, format_observation
from cua.surface.base import Action, ActionKind, ElementQuery, Observation, Surface

RecordFn = Callable[[dict], None]


def _retry_delay_seconds(exc: Exception, default: float = 20.0) -> float:
    """Gemini's free-tier 429 response carries a structured RetryInfo with the
    server's own suggested wait -- prefer that over a guess. `exc.details` is
    already a parsed dict (see google.genai.errors.APIError.__init__), not a
    string we'd need to regex.
    """
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        for item in details.get("error", {}).get("details", []):
            if str(item.get("@type", "")).endswith("RetryInfo"):
                raw = str(item.get("retryDelay", ""))
                if raw.endswith("s"):
                    try:
                        return float(raw[:-1])
                    except ValueError:
                        pass
    return default


def _generate_with_backoff(client: genai.Client, model: str, contents, config, max_retries: int = 3):
    """Discovered empirically: the free tier for gemini-3.6-flash allows only
    5 requests/minute, which a 9+ turn discovery run exceeds without this.
    Only 429s are retried -- everything else propagates immediately to the
    caller's broad except, which turns it into a clean `error` DiscoveryResult.
    """
    for attempt in range(max_retries + 1):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) != 429 or attempt == max_retries:
                raise
            time.sleep(_retry_delay_seconds(exc) + 2.0)  # small safety buffer
    raise RuntimeError("unreachable")  # pragma: no cover


@dataclass
class DiscoveryResult:
    status: str  # "finished" | "stuck" | "max_steps" | "error"
    reasoning: str
    steps: list[dict] = field(default_factory=list)
    final_observation: Observation | None = None
    run_dir: Path | None = None


def _perform_login(surface: Surface, record: RecordFn) -> None:
    """Deterministic setup, never an LLM decision. `record` gets the real
    username (not a secret) but always "<redacted>" for the password -- the
    plaintext password is used only in-memory to drive the browser and never
    written to the log.
    """
    username = os.environ.get("MOCKAPP_USERNAME", "operator")
    password = os.environ.get("MOCKAPP_PASSWORD", "changeme")

    plan = [
        (ActionKind.TYPE, ElementQuery(role="textbox", name="Username"), username, username),
        (ActionKind.TYPE, ElementQuery(role="textbox", name="Password"), password, "<redacted>"),
        (ActionKind.CLICK, ElementQuery(role="button", name="Sign In"), None, None),
    ]
    for kind, target, real_value, logged_value in plan:
        outcome = surface.act(Action(kind=kind, target=target, value=real_value, intent="log in (harness)"))
        record(
            {
                "source": "harness",
                "kind": kind.value,
                "target": target.describe(),
                "value": logged_value,
                "ok": outcome.ok,
                "error": outcome.error,
            }
        )
        if not outcome.ok:
            raise RuntimeError(f"harness login failed at {kind.value} {target.describe()}: {outcome.error}")


def _tool_call_to_action(call) -> Action:
    args = dict(call.args)
    reasoning = args.get("reasoning", "")
    target = ElementQuery(role=args.get("role"), name=args.get("name"))

    if call.name == "click":
        return Action(kind=ActionKind.CLICK, target=target, intent=reasoning)
    if call.name == "type":
        return Action(kind=ActionKind.TYPE, target=target, value=args.get("value", ""), intent=reasoning)
    if call.name == "select":
        return Action(kind=ActionKind.SELECT, target=target, value=args.get("value", ""), intent=reasoning)
    if call.name == "read":
        return Action(kind=ActionKind.READ, target=target, intent=reasoning)
    raise ValueError(f"not a UI action: {call.name}")


def discover(
    goal: str,
    target_url: str,
    surface: Surface,
    client: genai.Client,
    model: str,
    max_steps: int = 20,
    evidence_root: Path = Path("evidence"),
) -> DiscoveryResult:
    """
    Run the LLM-driven loop against `surface` (already start()-ed by the
    caller -- this function does not own the Surface's lifetime; see Day 9).
    """
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_dir = evidence_root / f"discovery-{run_id}"
    (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)

    log: list[dict] = []
    step_counter = 0

    def _next_step() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter

    def _log(step: int, entry: dict) -> None:
        full = {"step": step, **entry}
        log.append(full)
        with (run_dir / "log.jsonl").open("a") as f:
            f.write(json.dumps(full) + "\n")

    def _record(entry: dict) -> None:
        """For steps with no screenshot of their own (navigate, login)."""
        _log(_next_step(), entry)

    def _save_screenshot(step: int, obs: Observation) -> str | None:
        if not obs.screenshot:
            return None
        path = run_dir / "screenshots" / f"step-{step:02d}.png"
        path.write_bytes(obs.screenshot)
        return str(path)

    # 1. Deterministic setup -- harness, not LLM.
    nav_outcome = surface.act(
        Action(kind=ActionKind.NAVIGATE, value=target_url, intent="open the target application")
    )
    _record(
        {"source": "harness", "kind": "navigate", "value": target_url, "ok": nav_outcome.ok, "error": nav_outcome.error}
    )
    if not nav_outcome.ok:
        return DiscoveryResult(
            status="error", reasoning=f"could not open target: {nav_outcome.error}", steps=log, run_dir=run_dir
        )

    try:
        _perform_login(surface, _record)
    except RuntimeError as exc:
        return DiscoveryResult(status="error", reasoning=str(exc), steps=log, run_dir=run_dir)

    # 2. The LLM loop. The screen the model sees on turn 1 gets its own
    # numbered log entry + screenshot too, rather than being a special case --
    # every screen the model (or a reviewer) ever sees is a numbered step.
    obs = surface.observe()
    initial_step = _next_step()
    _log(
        initial_step,
        {"source": "harness", "kind": "observe", "screenshot": _save_screenshot(initial_step, obs)},
    )
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=format_observation(goal, obs))])]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[TOOL],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY")),
    )

    for _ in range(max_steps):
        try:
            response = _generate_with_backoff(client, model, contents, config)
        except Exception as exc:  # non-429 API error, network, refusal, etc.
            _record({"source": "llm", "error": f"API error: {exc}"})
            return DiscoveryResult(
                status="error", reasoning=f"Gemini API error: {exc}", steps=log, final_observation=obs, run_dir=run_dir
            )

        calls = response.function_calls or []
        if not calls:
            _record({"source": "llm", "error": "no function call returned"})
            return DiscoveryResult(
                status="error", reasoning="model returned no tool call", steps=log, final_observation=obs, run_dir=run_dir
            )

        call = calls[0]  # forced to exactly one action per turn by the system prompt
        contents.append(response.candidates[0].content)
        args = dict(call.args)
        reasoning = args.get("reasoning", "")

        if call.name == "finish":
            _record({"source": "llm", "kind": "finish", "reasoning": reasoning})
            return DiscoveryResult(status="finished", reasoning=reasoning, steps=log, final_observation=obs, run_dir=run_dir)

        if call.name == "stuck":
            _record({"source": "llm", "kind": "stuck", "reasoning": reasoning})
            return DiscoveryResult(status="stuck", reasoning=reasoning, steps=log, final_observation=obs, run_dir=run_dir)

        action = _tool_call_to_action(call)
        outcome = surface.act(action)
        obs = surface.observe()
        step = _next_step()
        screenshot_path = _save_screenshot(step, obs)

        _log(
            step,
            {
                "source": "llm",
                "kind": action.kind.value,
                "target": action.target.describe() if action.target else None,
                "value": action.value,
                "reasoning": reasoning,
                "ok": outcome.ok,
                "error": outcome.error,
                "read_value": outcome.read_value,
                "url_after": outcome.url_after,
                "screenshot": screenshot_path,
            },
        )

        fr_part = types.Part.from_function_response(
            name=call.name,
            response={
                "ok": outcome.ok,
                "error": outcome.error,
                "read_value": outcome.read_value,
                "current_screen": format_observation(None, obs),
            },
        )
        contents.append(types.Content(role="user", parts=[fr_part]))

    return DiscoveryResult(
        status="max_steps",
        reasoning=f"stopped after {max_steps} steps without finish/stuck",
        steps=log,
        final_observation=obs,
        run_dir=run_dir,
    )
