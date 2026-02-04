# Plan and Execute Verification Skill

Use this when you need a verified, dry-run plan before making any edits or running commands.

**Goal:** first understand the repo with evidence, then propose a plan (including unit + integration tests) that is verified step-by-step.

---


> **Client note:** In practice, **only Codex** consistently seems willing and able to follow these skill steps end-to-end **without deviating or running away**. Some other MCP clients may skip citations/tool calls or drift into “vibes.” If that happens, paste the **Copy/paste prompt** block verbatim and require the verifier tool call before accepting the answer.
>
> **Claude tip:** In Claude, start in **`/plan` mode** and ask it to create a plan for this exact workflow skill (e.g., “rca-fix-agent”, “search-and-learn”, etc.). Then tell it to **execute that plan step-by-step**, including the Strawberry verifier call, before it gives a final answer. This makes it much more likely to stay on-plan so you don’t have to babysit drift.


## Phase 1 — Search & Learn (repo understanding)
- Use the Search & Learn verification pattern to explore and understand the repo.
- Build an Evidence pack of spans `S0`, `S1`, ... (repo excerpts, docs, configs).
- Every factual sentence must end with citations like `[S0]`.
- If you cannot cite, label it **Unknown** or **Assumption**.

## Phase 2 — Plan (Greenfield-style, but for changes)
- Produce **Facts (cited)**, **Decisions**, **Assumptions** based on the evidence.
- Then propose a plan with **explicit steps** that includes:
  - unit tests to add/update
  - integration tests to add/update
  - exact files to change (paths and what will change)

## Phase 3 — Dry-run plan only
- Do NOT run commands or edit files.
- Output only a dry-run plan that outlines the exact file changes.

## Phase 4 — Approval gate
- Ask the user to approve the plan before any execution.
- If not approved, return to Phase 2 and revise the plan.

## Phase 5 — Execute (only after approval)
- Implement the planned edits as real patches.
- Run the planned unit and integration tests.
- If tests fail or evidence contradicts the plan, return to Phase 2 and revise.
- Repeat until tests pass or the user stops the loop.

## Verification (plan steps)
Run the verifier on the plan steps:

- Tool: `audit_trace_budget`
- Recommended settings:
  - `require_citations=true`
  - `context_mode="cited"`
  - `default_target=0.95`

If any step is flagged:
- revise the plan to remove or downgrade unsupported steps
- request the missing evidence instead of guessing
- If the verifier is run 3 times in a row, **STOP** and return only the steps that passed plus the steps that flagged and why they flagged.

---

## Copy/paste prompt
> First do Search & Learn verification to understand the repo. Build an evidence pack and cite every factual sentence. Then propose a plan using a Greenfield-style Facts/Decisions/Assumptions structure, and include both unit tests and integration tests. Output a dry-run plan only (no commands, no edits), but list the exact files to change and what will change.
> Then create a plan-step trace and run `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode="cited", default_target=0.95)` on the plan steps. If any step is flagged, revise the plan or request missing evidence.
> Ask for approval before executing. If approved, implement the patches and run the planned unit + integration tests. If tests fail, return to the draft plan stage and iterate.
> If the verifier is run 3 times in a row, stop and return only the steps that passed plus the steps that flagged and why they flagged.

---

## Worked example (max contrast): add feature flag to a service

### ❌ Without Strawberry (plan drifts into guesses)
**User:** Plan a feature flag rollout for endpoint `/v2/search`.

**Assistant (vibes):**
- “Add `FEATURE_SEARCH_V2` flag to config.”
- “Update middleware to check flag.”
- “Add unit tests for config.”
- “Add integration tests for both flag states.”

**Typical hidden problems:**
- config system may not exist
- endpoints may live in a different module
- test framework may not support the described integration tests

### ✅ With Strawberry (dry-run plan + audit_trace_budget)

#### 1) Evidence pack
**S0 — config module**
```text
# src/config/flags.py
FLAGS = {"search_v2": False}
```

**S1 — router**
```text
# src/routes/search.py
@router.get("/v2/search")
async def search_v2(...):
  ...
```

**S2 — test harness**
```text
# tests/conftest.py
@pytest.fixture
async def api_client(...):
  ...
```

#### 2) Dry-run plan (exact file changes)
1) Update `src/config/flags.py` to add a `search_v2` flag default and document it. [S0]
2) Update `src/routes/search.py` to gate `/v2/search` behind the flag. [S1]
3) Add unit tests in `tests/unit/test_flags.py` for the default flag value. [S0]
4) Add integration tests in `tests/integration/test_search_v2_flag.py` covering both flag states. [S1][S2]

#### 3) Plan-step trace (audited)
```json
[
  {"idx": 0, "claim": "Flags are defined in src/config/flags.py, so that file should be updated to include search_v2.", "cites": ["S0"]},
  {"idx": 1, "claim": "The /v2/search route is implemented in src/routes/search.py and can be gated there.", "cites": ["S1"]},
  {"idx": 2, "claim": "Unit tests can be added under tests/unit for flag defaults.", "cites": ["S0"]},
  {"idx": 3, "claim": "Integration tests can use the api_client fixture to exercise /v2/search under both flag states.", "cites": ["S2","S1"]}
]
```

#### 4) Verifier call (example)
```json
{
  "tool": "audit_trace_budget",
  "args": {
    "steps": [
      {"idx": 0, "claim": "Flags are defined in src/config/flags.py, so that file should be updated to include search_v2.", "cites": ["S0"]},
      {"idx": 1, "claim": "The /v2/search route is implemented in src/routes/search.py and can be gated there.", "cites": ["S1"]},
      {"idx": 2, "claim": "Unit tests can be added under tests/unit for flag defaults.", "cites": ["S0"]},
      {"idx": 3, "claim": "Integration tests can use the api_client fixture to exercise /v2/search under both flag states.", "cites": ["S2","S1"]}
    ],
    "spans": [
      {"sid":"S0","text":"..."},
      {"sid":"S1","text":"..."},
      {"sid":"S2","text":"..."}
    ],
    "require_citations": true,
    "context_mode": "cited",
    "default_target": 0.95
  }
}
```

**Why this is a “wow” difference:** you get a plan you can trust, without running any commands or editing files, and every step is grounded in evidence.
