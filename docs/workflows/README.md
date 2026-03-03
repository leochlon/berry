# Workflow verification playbooks

These playbooks show a repeatable pattern for using Strawberry (Berry’s verifier) as a review gate:

1) Collect evidence into spans (`S0`, `S1`, ...).
2) Produce output that cites those spans (`[S0]`).
3) Run a verifier tool (`audit_trace_budget` or `detect_hallucination`).
4) Revise until unsupported claims are removed or downgraded.

## Client notes

MCP clients vary in how consistently they follow multi-step prompts (especially citations and required tool calls). If your client skips steps:

- Use the playbook’s “Copy/paste prompt” block as a system instruction.
- Require the verifier tool call before accepting a final answer.
- In Claude, starting in `/plan` mode and then asking it to execute the plan can help preserve multi-step workflows.

## Tools

- `audit_trace_budget` — verify an explicit list of `(claim, cites)` steps.
- `detect_hallucination` — check an answer with `[S#]` citations against evidence spans.

If you run a verifier 3 times in a row, stop and return only:
- the claims that passed
- the claims that were flagged (and why)

---

## Pick your workflow

1) **Search & Learn** → `SEARCH_AND_LEARN_VERIFICATION.md`
   Q&A / repo exploration / API understanding. Uses `audit_trace_budget` (short trace).

2) **Generate Boilerplate/Content** → `GENERATE_BOILERPLATE_VERIFICATION.md`
   Tests/docs/migrations/configs. Uses `audit_trace_budget` to validate the design trace behind the artifact.

3) **Inline Completions** → `INLINE_COMPLETION_VERIFICATION.md`
   Spot-check high-impact tab-complete. Uses `audit_trace_budget` on a 3–6 step micro-trace.

4) **Greenfield Prototyping** → `GREENFIELD_PROTOTYPE_VERIFICATION.md`
   Separate facts, decisions, and assumptions. Verify the Facts via `audit_trace_budget`.

5) **Plan and Execute** → `PLAN_AND_EXECUTE_VERIFICATION.md`
   Repo understanding + verified dry-run plan. Uses `audit_trace_budget` on plan steps.

6) **RCA Fix Agent** → MCP prompt `rca_fix_agent` + `RCA_FIX_REPORT_TEMPLATE.md`
   Full debugging loop: baseline → hypotheses → verify root cause → fix → test → verify claims.

---

## Worked examples

Each playbook includes two worked examples:

- **Without verification** — plausible output that is not grounded in evidence
- **With verification** — evidence spans + citations + a verifier call
