# Inline Completion Verification Skill

Use this when you accepted a tab-complete suggestion that changes real behavior.

**Goal:** catch micro-hallucinations hidden inside fast completions (retries, timeouts, auth checks, parsing, “helpful” refactors).

Inline completions are too frequent to verify constantly — so use this as a **spot-check gate** when a completion:
- touches correctness/security/money
- changes external requests or persistence
- adds retries, caching, concurrency, or error handling
- “explains” behavior in a comment/docstring

---


> **Client note:** MCP clients vary in how reliably they follow multi-step prompts (especially citations and required tool calls). If your client skips steps, treat the **Copy/paste prompt** block as a system instruction and require the verifier tool call before accepting the answer.
>
> **Claude tip:** Starting in `/plan` mode and asking Claude to execute the plan can help preserve multi-step workflows.


## What changed
- Summarize the completion’s effect (no speculation).

## Evidence pack
**This is part of the skill.** You’re not “verifying the completion”; you’re verifying the *reason you should trust it*.

Collect the smallest evidence pack that constrains correctness (surrounding code, contracts/comments, failing tests/logs). Strawberry can only judge what you show it.

If you don’t have those spans, stop and either collect them (repo browsing / tools) or ask the user to paste them.

> List the spans you used (`S0`, `S1`, ...) and what they represent.

Suggested spans:
- S0: surrounding code (function + nearby helpers)
- S1: the completion itself (exact text inserted)
- S2: contract docs / invariants / comments
- S3: failing test or stack trace (if this was a fix)
- S4: API semantics (idempotency rules, rate limits, etc.)

## Micro-trace (required)
Write **3–6 steps** describing why the completion is safe/correct.
Each step must cite evidence spans.

Example:
```json
{"idx": 0, "claim": "This change retries the call to /charge three times.", "cites": ["S1"]}
```

## Verification
Run the verifier:

- Tool: `audit_trace_budget` (on the trace text)
- Recommended settings:
  - `require_citations=true`
  - `context_mode="cited"`
  - `default_target=0.95` (strict: treat as review gate)

If anything is flagged:
- do not rationalize flagged steps
- propose a safer edit, or request the missing evidence span (contract/test/log)
- If the verifier is run 3 times in a row, **STOP** and return only the claims that passed plus the claims that flagged and why they flagged.

---

## Worked example (without vs with verification): "helpful retry" that can double-charge

### Without verification (silent regression)
**User:** Is this completion okay?

**Assistant (speculative):**
> “Yep — retries are standard and improve reliability.”

Result: risk of duplicate charges.

### With verification (micro-trace + `audit_trace_budget`)

#### 1) Evidence pack
**S0 — contract comment**
```text
// IMPORTANT: do not retry POST /charge (non-idempotent)
```

**S1 — accepted completion**
```text
async function charge(card, amount) {
  return retry(async () => http.post("/charge", { card, amount }), { retries: 3 });
}
```

**S2 — retry helper behavior**
```text
retry(fn, {retries}) retries on ANY thrown error.
```

#### 2) Copy/paste prompt
> Produce a 3–6 step trace explaining why this completion is safe/correct.  
> Cite S0–S2.  
> Run `audit_trace_budget(steps=..., require_citations=true, context_mode="cited", default_target=0.95)` on the trace text.  
> If unsafe or unsupported, propose a safer alternative.
> If the verifier is run 3 times in a row, stop and return only the claims that passed plus the claims that flagged and why they flagged.

#### 3) Micro-trace (grounded)
```json
[
  {"idx": 0, "claim": "The completion retries POST /charge up to 3 times.", "cites": ["S1"]},
  {"idx": 1, "claim": "POST /charge is explicitly marked non-idempotent and must not be retried.", "cites": ["S0"]},
  {"idx": 2, "claim": "The retry helper retries on any error, so it could retry on timeouts/5xx/other failures.", "cites": ["S2"]},
  {"idx": 3, "claim": "Therefore this completion violates the contract and risks duplicate charges.", "cites": ["S0","S1","S2"]}
]
```

#### 4) Verifier call (example)
```json
{
  "tool": "audit_trace_budget",
  "args": {
    "steps": [
      {"idx": 0, "claim": "The completion retries POST /charge up to 3 times.", "cites": ["S1"]},
      {"idx": 1, "claim": "POST /charge is explicitly marked non-idempotent and must not be retried.", "cites": ["S0"]},
      {"idx": 2, "claim": "The retry helper retries on any error...", "cites": ["S2"]},
      {"idx": 3, "claim": "Therefore this completion violates the contract...", "cites": ["S0","S1","S2"]}
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

#### 5) Safer alternative (what good looks like)
- Remove retry logic from `/charge`. [S0]  
- If you need reliability, introduce idempotency keys + server-side dedupe **only if** supported by specs (otherwise label as Assumption and request requirements). [S0]

**Why this helps:** it turns a fast completion into a reviewable change by requiring a cited micro-trace and a verifier run.
