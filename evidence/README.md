# Evidence index

Two real, LLM-driven discovery runs against the mock app (`gemini-3.5-flash-lite`),
kept deliberately — not cherry-picked to hide the interesting one.

## `discovery-20260914T114925-c70df4` — a real safety-relevant "stuck" outcome

The model correctly executed every step through reaching the "Review New
Sub-Account" screen, then clicked **"Confirm & Create"** — the one irreversible
action the whole system is designed to prevent an unattended agent from taking.
Its own recorded reasoning (`log.jsonl`, final step) shows it second-guessing
itself before settling on `stuck`.

Nothing in the system *stopped* this click — there was no code-level policy
enforcement wired into discovery at the time (that's Day 10's allowlist work).
This run is the concrete evidence behind that design decision: prompt-level
caution alone was not sufficient, so `config/allowlist.json` cannot remain
advisory-only. See `REPORT.md` (Safety) for the fix and its limits.

## `discovery-20260914T115514-3d104b` — the canonical successful run

After sharpening the system prompt (explicit "stop the instant the goal screen
appears; never click a finalizing/irreversible control unless the goal says
to"), the model reached the review screen and correctly called `finish`
without touching "Confirm & Create." 14 steps: 4 deterministic harness steps
(navigate + login, credentials never in the model's context or this log),
1 initial-screen observation, 9 LLM-decided actions. Every step's
`screenshots/step-NN.png` matches its own log line's step number.

This is the run the `artifacts/` capability (Day 6) is built from.
