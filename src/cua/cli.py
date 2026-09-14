"""The `cua` command-line entrypoint.

Two subcommands, matching the two halves of the system:

    cua discover --goal "..." --target http://localhost:8080/login
    cua replay   --artifact artifacts/open-subaccount.v1.json --params '{"member_id": "100002"}'

`discover` is wired as of Day 4-5. `replay` is stubbed, wired on Day 7.
"""

from __future__ import annotations

import os

import typer
from dotenv import load_dotenv
from google import genai

from cua.agent.loop import discover as run_discover
from cua.surface.browser import BrowserSurface

load_dotenv()

app = typer.Typer(add_completion=False, help="Computer-use automation: discover -> artifact -> replay.")


@app.command()
def discover(
    goal: str = typer.Option(..., "--goal", help="Natural-language task for the target app."),
    target: str = typer.Option(..., "--target", help="Entry URL / app to start from."),
    max_steps: int = typer.Option(20, help="Stop after this many agent steps."),
    headless: bool = typer.Option(False, help="Run without a visible browser window."),
) -> None:
    """Run the LLM-driven observe -> decide -> act loop until the goal is met."""
    model = os.environ.get("CUA_MODEL", "gemini-3.6-flash")
    client = genai.Client()

    surface = BrowserSurface(headless=headless)
    surface.start()
    try:
        result = run_discover(goal=goal, target_url=target, surface=surface, client=client, model=model, max_steps=max_steps)
    finally:
        # Day 9 will keep this alive across a "stuck" escalation instead of
        # closing it; for now, close it in every case.
        surface.stop()

    typer.echo(f"status: {result.status}")
    typer.echo(f"reasoning: {result.reasoning}")
    typer.echo(f"steps: {len(result.steps)}")
    typer.echo(f"evidence: {result.run_dir}")

    if result.status != "finished":
        raise typer.Exit(code=1)


@app.command()
def replay(
    artifact: str = typer.Option(..., "--artifact", help="Path to a saved capability artifact."),
    params: str = typer.Option("{}", "--params", help="JSON object of input parameters."),
) -> None:
    """Execute a saved artifact deterministically, with no LLM in the loop."""
    typer.echo(f"[replay] artifact={artifact!r} params={params!r}")
    typer.echo("Not implemented yet — wired on Day 7.")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
