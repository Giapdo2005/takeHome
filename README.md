# Computer-Use Automation System

An LLM discovers how to complete a task by driving a real UI once; the run is
saved as a typed, versioned **capability artifact**; that artifact is then
**replayed deterministically** with no LLM in the loop. When either path gets
stuck, control is handed to a human on the *same* live session.

> Status: **Day 1 of ~11** — skeleton + dependency smoke tests. See `REPORT.md`
> for the design and the build plan.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium          # one-time browser download

cp .env.example .env                 # then add your GEMINI_API_KEY (free, no card)
```

Get a free Gemini API key at https://aistudio.google.com/apikey — no credit card,
~250 requests/day on the free tier, which is enough for this project.

## Verify the install (Day 1)

```bash
python scripts/hello_playwright.py    # opens a browser, prints an a11y snapshot, saves a screenshot
python scripts/hello_gemini.py        # one Gemini function-call -> a parsed action dict
pytest -q                             # package imports, Surface types validate
```

`hello_gemini.py` needs `GEMINI_API_KEY`; the other two do not.

## Demo path (target: end of build)

```bash
# 1. discovery — LLM drives the mock app, emits an artifact
cua discover \
  --goal "Open a new sub-account for member 100002, type Savings, initial deposit 50" \
  --target http://localhost:8080/login

# 2. replay — no LLM, returns typed outputs
cua replay \
  --artifact artifacts/open-subaccount.v1.json \
  --params '{"member_id": "100002", "account_type": "Savings", "initial_deposit": 50}'

# 3. replay an error case — a business outcome, not a crash
cua replay --artifact artifacts/open-subaccount.v1.json \
  --params '{"member_id": "999999", "account_type": "Savings", "initial_deposit": 50}'
```

## Running without live services

`cua replay` needs the mock app but **not** any LLM API. Recorded artifacts
and run logs for a full discovery + replay live in `evidence/` so the end-to-end
thread can be reviewed without running anything.

## Layout

| Path | What |
|---|---|
| `src/cua/surface/` | The `Surface` seam — the only code that touches a live UI |
| `src/cua/agent/` | The discovery loop (LLM: observe -> decide -> act) |
| `src/cua/artifact/` | The capability schema + the recorder that builds one |
| `src/cua/replay/` | Deterministic executor, locator resolution, error taxonomy |
| `src/cua/safety/` | Allowlist, risky-action classifier, redaction |
| `src/cua/escalation/` | Stuck detection, human handoff on the live session |
| `mockapp/` | The target — a deliberately legacy-flavored bank admin console |
| `config/allowlist.json` | What the agent is permitted to do |
| `evidence/` | Saved artifacts + logs from real runs (committed) |
