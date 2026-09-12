"""The `cua` command-line entrypoint.

Two subcommands, matching the two halves of the system:

    cua discover --goal "..." --target http://localhost:8080/login
    cua replay   --artifact artifacts/open-subaccount.v1.json --params '{"member_id": "100002"}'

Both are stubbed today (Day 1). `discover` is wired on Day 4-5, `replay` on Day 7.
"""

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False, help="Computer-use automation: discover -> artifact -> replay.")


@app.command()
def discover(
    goal: str = typer.Option(..., "--goal", help="Natural-language task for the target app."),
    target: str = typer.Option(..., "--target", help="Entry URL / app to start from."),
    max_steps: int = typer.Option(30, help="Stop after this many agent steps."),
) -> None:
    """Run the LLM-driven observe -> decide -> act loop until the goal is met."""
    typer.echo(f"[discover] goal={goal!r} target={target!r} max_steps={max_steps}")
    typer.echo("Not implemented yet — wired on Day 4-5.")
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
