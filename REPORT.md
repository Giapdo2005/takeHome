# Design Write-up

> Filled in as the build progresses. Headings are fixed (they match the brief).
> Bullets are notes-to-self / decisions already made, to be turned into prose.

## 1. Architecture

- Pipeline: `discover` (LLM in the loop) -> `Capability` artifact -> `replay` (no LLM).
  Discovery is expensive and run once per capability; replay is cheap and run many times.
- **The Surface seam** (`surface/base.py`): `observe()` / `act()` is the only interface
  to a live UI. The loop, recorder, and replay engine are surface-agnostic. Adding a
  legacy-web or desktop surface = a new class, no changes above the seam.
- Perception: accessibility tree (text) is the primary signal; screenshot is secondary
  + evidence. Rationale: stable semantic handles > pixel coordinates for both LLM
  targeting and deterministic re-resolution on replay.
- Single process, CLI-driven (`cua discover`, `cua replay`). Storage is JSON files on
  disk (`artifacts/`, `evidence/`, `runs/`). No DB, no queue — justified by scope.
- Language: Python + Pydantic (schema validation + JSON Schema export for the agent
  contract). LLM: Gemini (free tier — provider choice is explicitly ours; the loop is
  isolated to `agent/loop.py` + `agent/prompt.py` and swappable). Manual function-call
  loop (not the SDK's automatic function calling) so every action is interceptable for
  guardrails / recording / escalation.

## 2. Artifact schema

- _TODO (Day 6). Focal point._ Key intended decisions:
  - `Locator` is a *ranked bundle* of strategies (role+name, label, text, attribute,
    css path, ordinal), each with a confidence and a reviewer-facing note — not one selector.
  - `Checkpoint` is one type reused for success condition, per-step verification, and
    error detection.
  - `value` is a reference (`{param}` / `{secret}` / `{literal}`), never an inline secret.
  - `target.app_id` identifies the vendor product, not the tenant — the hook for reuse.
  - Versioned; re-discovery bumps the version.

## 3. Determinism & error handling

- _TODO (Day 7-8)._ Intended: locator resolution tries strategies best-first, requires
  exactly one match, treats zero/ambiguous as a stop. Error taxonomy:
  **business outcome** (declared, returned as a normal result) vs
  **recoverable** (known interstitial / transient — bounded retry) vs
  **hard failure** (stop, structured `{step, expected, observed, evidence}`).

## 4. Heterogeneity & multi-tenant

- _TODO (Day 11)._ Surface abstraction extends to legacy/desktop by new `Surface` impls;
  artifact describes intent, not mechanism. Multi-tenant: base artifact keyed by
  `app_id` + per-tenant override layer; drift detected via checkpoint failure rates.

## 5. Escalation & handoff

- _TODO (Day 9)._ Stuck = explicit `stuck` tool call / no state change over K steps /
  guardrail blocked a required action / replay hard-failure in attended mode.
  Handoff: pause the loop, keep the *same* headed browser alive, flip a control token,
  expose it via a minimal operator page, resume on signal, diff + record what the human did.

## 6. Safety

- Allowlist (`config/allowlist.json`): permitted URL prefixes + action types, enforced
  before every `act()` on both paths. Risky controls = specific irreversible verbs
  matched on control text; global list stays precise, app-specific danger words go in
  the per-artifact `risky_controls`. Policy: block | confirm | flag.
- Redaction: artifacts store param *name + type*, never values; secrets via `{secret}`
  refs resolved at run time; logs redact declared-sensitive values.
- _TODO (Day 10): limits of the model._

## 7. Cuts

- _TODO._ Planned cuts: multi-tenant/desktop are design-only; operator UI is a minimal
  mock; no assisted-LLM replay fallback; no capability-catalog API; mock-app auth is fake.
