# Search & Learn Verification Skill

Use this when you're asking questions, exploring unfamiliar codebases, or trying to understand an API.

**Goal:** catch answers that *sound right* but aren't supported by evidence (repo excerpts, web excerpts, experiments).

---


> **Client note:** In practice, **only Codex** consistently seems willing and able to follow these skill steps end-to-end **without deviating or running away**. Some other MCP clients may skip citations/tool calls or drift into “vibes.” If that happens, paste the **Copy/paste prompt** block verbatim and require the verifier tool call before accepting the answer.
>
> **Claude tip:** In Claude, start in **`/plan` mode** and ask it to create a plan for this exact workflow skill (e.g., “rca-fix-agent”, “search-and-learn”, etc.). Then tell it to **execute that plan step-by-step**, including the Strawberry verifier call, before it gives a final answer. This makes it much more likely to stay on-plan so you don’t have to babysit drift.


## Problem / question
- What are we trying to learn?
- What decision will this answer influence?

## Evidence pack
**This is part of the skill.** Strawberry does *verification*, not retrieval — so evidence must be collected by the agent (repo browsing, web search, experiments) or pasted by the user.

If you don’t yet have spans, **stop here** and either:
- collect the minimal snippets you need (code/doc/log output), or
- ask the user to paste them.

> List the spans you used (`S0`, `S1`, ...) and what they represent.

Example span types:
- S0: README excerpt describing the API contract
- S1: Code excerpt showing the implementation
- S2: Web excerpt from **official docs** (if used)
- S3: Experiment output (test run / curl / repro)

## Answer (cited)
- Every **factual** sentence must end with citations like `[S0]` or `[S1][S2]`.
- If you cannot cite it, label it **Unknown** or **Assumption** (do not present as fact).

## Verification
Run the verifier:

- Tool: `audit_trace_budget` (with a short trace of key claims)
- Recommended settings:
  - `require_citations=true`
  - `context_mode="cited"` (strict: only cited spans count)

If anything is flagged:
- rewrite the answer to remove or downgrade unsupported claims
- list what additional evidence would resolve each gap
- If the verifier is run 3 times in a row, **STOP** and return only the claims that passed plus the claims that flagged and why they flagged.

---

## Worked example (max contrast): “Does auth validate JWT aud+iss?”

### ❌ Without Strawberry (vibes)
**User:** Does this repo’s auth validate JWT `aud` and `iss`? Where is it configured?

**Assistant (sounds confident, but vibing):**
- “Yes — the middleware validates issuer and audience via `jsonwebtoken.verify()` using `JWT_ISSUER` and `JWT_AUDIENCE` env vars.”
- “It’s configured in `config/auth.ts` and loaded from `.env`.”
- “To disable audience validation, set `audience: undefined`.”

**What’s wrong (typical failure modes):**
- file paths and env vars may not exist
- “disable audience validation” advice may be incorrect for the library in use
- it’s unverifiable unless you manually hunt through the repo

### ✅ With Strawberry (evidence-first + `audit_trace_budget`)

#### 1) Evidence pack (spans you collect or paste)
**S0 — middleware code**
```text
// src/auth/middleware.ts
export function auth(req, res, next) {
  const token = getBearer(req);
  const { payload } = jwtVerify(token, getKey(), {
    issuer: process.env.JWT_ISSUER,
  });
  req.user = payload.sub;
  next();
}
```

**S1 — configuration docs**
```text
# README.md
JWT_ISSUER is required. No other JWT settings are currently supported.
```

**S2 — env example**
```text
# .env.example
JWT_ISSUER=
```

#### 2) Copy/paste prompt you give the model
> Answer using **only** evidence in S0–S2.  
> Every factual sentence must end with citations like `[S0]`.  
> If something is unknown, say “unknown from evidence.”  
> Then run `audit_trace_budget(steps=..., require_citations=true, context_mode="cited")` and revise if flagged.  
> If the verifier is run 3 times in a row, stop and return only the claims that passed plus the claims that flagged and why they flagged.

#### 3) Cited answer (draft)
Auth validates **issuer** via the `issuer:` option passed into `jwtVerify(...)`. [S0]  
The issuer value comes from `process.env.JWT_ISSUER`. [S0]  
I do **not** see any audience (`aud`) validation in the provided middleware; no `audience:` option is present. [S0]  
The README explicitly says `JWT_ISSUER` is required and that no other JWT settings are supported. [S1]  
`.env.example` only includes `JWT_ISSUER`. [S2]

#### 4) Verifier call (example)
```json
{
  "tool": "audit_trace_budget",
  "args": {
    "steps": [
      {"idx": 0, "claim": "Auth validates issuer via the issuer option in jwtVerify.", "cites": ["S0"]},
      {"idx": 1, "claim": "The issuer value comes from process.env.JWT_ISSUER.", "cites": ["S0"]},
      {"idx": 2, "claim": "Audience validation is not evidenced in the provided middleware.", "cites": ["S0"]},
      {"idx": 3, "claim": "README states JWT_ISSUER is required and no other JWT settings are supported.", "cites": ["S1"]}
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

#### 5) Final answer (what “good” looks like)
Issuer is validated and configured via `JWT_ISSUER`. [S0][S1][S2]  
Audience (`aud`) validation is **not evidenced** in S0–S2. [S0]  
If audience validation exists elsewhere, it is not shown here; provide the relevant span(s) to verify it. [S0]

---

## Gaps / next evidence to collect
- File(s) to inspect:
- Command(s) to run:
- URL(s) to fetch:
