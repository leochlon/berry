# Refactoring & Bug Fixes Verification Skill (RCA-gated)

Use this when:
- an AI suggests a refactor or bug fix
- a human will review/merge (or you want to *avoid wasting review time*)
- you need the model to stop “vibing” about root cause, safety, or behavior preservation

**Goal:** force a high-signal RCA-style writeup backed by evidence, then audit it with Strawberry.

---


> **Client note:** In practice, **only Codex** consistently seems willing and able to follow these skill steps end-to-end **without deviating or running away**. Some other MCP clients may skip citations/tool calls or drift into “vibes.” If that happens, paste the **Copy/paste prompt** block verbatim and require the verifier tool call before accepting the answer.
>
> **Claude tip:** In Claude, start in **`/plan` mode** and ask it to create a plan for this exact workflow skill (e.g., “rca-fix-agent”, “search-and-learn”, etc.). Then tell it to **execute that plan step-by-step**, including the Strawberry verifier call, before it gives a final answer. This makes it much more likely to stay on-plan so you don’t have to babysit drift.


## Inputs you should gather first (Evidence pack)
**This is part of the skill.** Strawberry is the verification gate — it can’t fetch logs, browse the repo, or run tests for you.

If the agent has tools (repo browsing, `git grep`, running tests, web search), it should **collect** these spans itself. If it doesn’t, it should **ask the user to paste** the missing spans before proceeding.

You will get dramatically better results if you have these spans ready up front.

Suggested spans:
- S0: reproduction command + baseline output (stack trace, failing test)
- S1: relevant code excerpt at crash site
- S2: call site / data flow into the crash site
- S3: invariants/spec (comments, docs, requirements)
- S4: experiment results (new test output, benchmark, log excerpt)
- S5: proposed patch diff (optional, but helpful)

## Output format: RCA + Fix Report
Fill the RCA template in `docs/workflows/RCA_FIX_REPORT_TEMPLATE.md`.

Rules:
- Every factual claim must be cited (e.g., `[S1]`).
- If you can’t cite it, label it as a hypothesis and propose an experiment span to confirm.

## Verification (the “merge gate”)
Strawberry should audit the critical claims:

- Tool: `audit_trace_budget`
- Settings:
  - `require_citations=true`
  - `context_mode="cited"`
  - `default_target=0.95`

What to put into `steps`:
- Root cause primary claim + sub-claims
- Fix mechanism claims (“why this should fix it”)
- Test plan + results claims

If anything is flagged:
- request missing evidence
- or downgrade the claim to a hypothesis
- do not proceed as if the claim is confirmed

---

## Worked example (max contrast): TypeError in getUserDisplayName

### ❌ Without Strawberry (the “trust me bro” refactor)
**User:** Fix this crash and refactor the module.

**Assistant (vibes):**
- “Root cause is a race condition in the cache layer.”
- “Refactored into a UserService class.”
- “Preserves behavior and improves perf by 30%.”
- “Added tests; should be stable.”

**Why this wastes time:**
- the root cause could be invented
- perf claims are often made up
- “behavior preserved” is meaningless without cited tests/spec

### ✅ With Strawberry (RCA pack + audited claims)

#### 1) Evidence pack
**S0 — crash stack trace**
```text
TypeError: cannot read property 'id' of undefined at getUserDisplayName (user.ts:41)
```

**S1 — code excerpt**
```text
export function getUserDisplayName(user) {
  return user.profile.name ?? user.id;
}
```

**S2 — calling site**
```text
const name = getUserDisplayName(session.user);
```

**S3 — session behavior**
```text
If not authenticated, session.user is undefined.
```

#### 2) Copy/paste prompt (RCA + audit)
> Fill the RCA template in `docs/workflows/RCA_FIX_REPORT_TEMPLATE.md`.  
> Every claim must cite S0–S3.  
> Then extract the Root Cause + Fix Plan into a `steps` list and run  
> `audit_trace_budget(require_citations=true, context_mode="cited", default_target=0.95)`.  
> If anything is flagged, stop and request missing evidence instead of guessing.

#### 3) Trace claims to audit (example)
```json
[
  {"idx": 0, "claim": "The crash occurs because getUserDisplayName is called with undefined.", "cites": ["S0","S2","S3"]},
  {"idx": 1, "claim": "getUserDisplayName dereferences user.profile without guarding user.", "cites": ["S1"]},
  {"idx": 2, "claim": "session.user can be undefined when not authenticated.", "cites": ["S3"]},
  {"idx": 3, "claim": "Fix: handle undefined user by returning a fallback or throwing a controlled auth error.", "cites": ["S1","S3"]}
]
```

#### 4) Verifier call (example)
```json
{
  "tool": "audit_trace_budget",
  "args": {
    "steps": [
      {"idx": 0, "claim": "The crash occurs because getUserDisplayName is called with undefined.", "cites": ["S0","S2","S3"]},
      {"idx": 1, "claim": "getUserDisplayName dereferences user.profile without guarding user.", "cites": ["S1"]},
      {"idx": 2, "claim": "session.user can be undefined when not authenticated.", "cites": ["S3"]},
      {"idx": 3, "claim": "Fix: handle undefined user by returning a fallback or throwing a controlled auth error.", "cites": ["S1","S3"]}
    ],
    "spans": [
      {"sid":"S0","text":"..."},
      {"sid":"S1","text":"..."},
      {"sid":"S2","text":"..."},
      {"sid":"S3","text":"..."}
    ],
    "require_citations": true,
    "context_mode": "cited",
    "default_target": 0.95
  }
}
```

#### 5) What “good” looks like
- The RCA stops at what the evidence supports.
- Hypotheses are explicitly labeled and paired with a confirming experiment.
- The fix is justified by cited mechanism, not vibes.
- “Behavior preserved” is only claimed if you cite tests/spec and/or show the before/after results span.

