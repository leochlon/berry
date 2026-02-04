# Greenfield Prototyping Verification Skill

Use this in "vibe code" prototyping where requirements are incomplete.

**Goal:** move fast without pretending assumptions are facts.

The pattern:
1) Extract **Facts** from evidence spans (requirements, constraints, repo context, experiments).
2) Put everything else into **Decisions** or **Assumptions**.
3) Verify the Facts section with `audit_trace_budget` (trace of Facts).

---


> **Client note:** In practice, **only Codex** consistently seems willing and able to follow these skill steps end-to-end **without deviating or running away**. Some other MCP clients may skip citations/tool calls or drift into “vibes.” If that happens, paste the **Copy/paste prompt** block verbatim and require the verifier tool call before accepting the answer.
>
> **Claude tip:** In Claude, start in **`/plan` mode** and ask it to create a plan for this exact workflow skill (e.g., “rca-fix-agent”, “search-and-learn”, etc.). Then tell it to **execute that plan step-by-step**, including the Strawberry verifier call, before it gives a final answer. This makes it much more likely to stay on-plan so you don’t have to babysit drift.


## Goal
- What are we building and why?
- What is “good enough” for this prototype?

## Evidence pack
**This is part of the skill.** Prototypes fail when assumptions get smuggled in as “facts.”

So first, collect a tiny evidence pack (requirements, constraints, repo context, web refs, experiments). If you can’t collect it automatically, ask the user to paste it.

> List spans `S0`, `S1`, ... (requirements, repo context, web refs, experiments).

Suggested spans:
- S0: product requirement paragraph / ticket
- S1: explicit constraints (no broker, single service, etc.)
- S2: privacy/compliance requirements
- S3: repo conventions (framework, DB choice, deployment model)
- S4: experiment results (throughput, latency, benchmarks)

## Facts (must be cited)
- Only include requirements/constraints you can point to.
- Every sentence must end in citations `[S#]`.

## Decisions (design choices)
- You can choose these, but label them clearly as **Decisions**.
- Cite evidence if it motivates the decision.

## Assumptions (explicitly declared)
- Throughput/latency goals, “exactly-once”, tech choices not in evidence, etc.
- These are allowed — just don’t smuggle them in as Facts.

## Verification
Run:

- Tool: `audit_trace_budget` (trace of Facts)
- Recommended settings:
  - `require_citations=true`
  - `context_mode="cited"`
  - `default_target=0.9` (prototype-friendly strictness)

If any Fact is flagged:
- move it to Assumptions **or**
- request additional evidence spans
- If the verifier is run 3 times in a row, **STOP** and return only the claims that passed plus the claims that flagged and why they flagged.

---

## Worked example (max contrast): prototype an events ingestion API

### ❌ Without Strawberry (prototype becomes a fake spec)
**User:** Prototype an events ingestion API.

**Assistant (vibes):**
- “Exactly-once delivery”
- “Kafka pipeline”
- “99p < 50ms”
- “GDPR compliant by default”
- “RBAC and audit logs”

It reads great — and it’s mostly invented unless explicitly required.

### ✅ With Strawberry (Facts vs Decisions vs Assumptions + `audit_trace_budget`)

#### 1) Evidence pack
**S0 — requirements**
```text
We need POST /events. Return 202 quickly. Store events in Postgres.
```

**S1 — constraint**
```text
No message broker in v1. Deploy as a single service.
```

**S2 — privacy**
```text
Events may contain PII. Must support deletion by user_id.
```

#### 2) Copy/paste prompt
> Produce three sections: **Facts**, **Decisions**, **Assumptions**.  
> Every Fact must be cited `[S#]`.  
> Run `audit_trace_budget(steps=..., require_citations=true, context_mode="cited")` on the Facts section only.  
> If any Fact is flagged, move it to Assumptions.
> If the verifier is run 3 times in a row, stop and return only the claims that passed plus the claims that flagged and why they flagged.

#### 3) Output (example)
**Facts**
- The API must expose `POST /events` and return `202` quickly. [S0]  
- Events are stored in Postgres. [S0]  
- v1 must not use a message broker and is deployed as a single service. [S1]  
- Events may contain PII and deletion by `user_id` must be supported. [S2]

**Decisions**
- Use an `events_raw` table and a background worker to process events asynchronously. [S0][S1]  
- Use request validation and schema versioning on the event payload. (Decision; motivated by “store events” but not explicitly required.) [S0]

**Assumptions**
- Throughput target: 1k req/s. (Assumption)  
- Exactly-once semantics. (Assumption)  
- Latency SLO. (Assumption)  

#### 4) Verifier call (example)
```json
{
  "tool": "audit_trace_budget",
  "args": {
    "steps": [
      {"idx": 0, "claim": "The API must expose POST /events and return 202 quickly.", "cites": ["S0"]},
      {"idx": 1, "claim": "Events are stored in Postgres.", "cites": ["S0"]},
      {"idx": 2, "claim": "v1 must not use a message broker and is deployed as a single service.", "cites": ["S1"]},
      {"idx": 3, "claim": "Events may contain PII and deletion by user_id must be supported.", "cites": ["S2"]}
    ],
    "spans": [
      {"sid":"S0","text":"..."},
      {"sid":"S1","text":"..."},
      {"sid":"S2","text":"..."}
    ],
    "require_citations": true,
    "context_mode": "cited",
    "default_target": 0.9
  }
}
```

**Why this is a “wow” difference:** Strawberry forces the prototype to be *honest*. You can still move fast — but now you can tell what’s real vs what’s invented.
