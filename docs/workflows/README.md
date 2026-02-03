# Workflow verification playbooks (with vs without Strawberry)

These playbooks show how to use Strawberry (Berry’s hallucination detector) as a **verification step** to catch when a model “vibed” instead of using real evidence.


## Client adherence note (read this once)

These playbooks are written as **skills**: a tight sequence of “collect evidence → write with citations → run the verifier → revise”.

In practice, MCP clients vary in how strictly they execute that sequence.

- **Codex**: best adherence — it tends to follow the skill end-to-end (citations + verifier tool calls) **without deviating or running away**.
- **Claude**: start in **`/plan` mode** and ask it to create a step-by-step plan for the exact workflow skill you want (e.g., “rca-fix-agent”, “search-and-learn”, etc.). Then tell it to **execute the plan** and require the Strawberry tool call before the final answer. This makes Claude much more likely to stay on-plan so you don’t have to keep checking for drift.

**Claude `/plan` starter (copy/paste):**
```
/plan
Create a plan to execute the Strawberry-assisted workflow skill I’m using (e.g., `rca-fix-agent`, `search-and-learn`, etc.).
Your plan must include: (1) evidence collection steps and the resulting evidence pack spans (S0, S1, ...), (2) output with citations, (3) a Strawberry verifier tool call, (4) a revision step if anything is flagged.
Then execute the plan step-by-step, and do not produce a final answer until the verifier has run.

If you don’t have direct access to collect evidence (repo browsing, web search, or running experiments), your plan must explicitly stop and ask the user to paste the missing spans before you proceed.
```
- **Other clients**: may treat prompts as suggestions (skip tool calls, drop citations, or “run away” into speculative answers).

If you’re using a client that drifts, don’t fight it — **pin the “Copy/paste prompt” block** from each playbook as a system instruction, and explicitly require the tool call before a final answer.

**Two tools, five workflows:**
- `detect_hallucination` — verify a cited answer sentence-by-sentence
- `audit_trace_budget` — verify a cited reasoning trace (claims + cites)

---

## Pick your workflow

1) **Search & Learn** → `SEARCH_AND_LEARN_VERIFICATION.md`
   Q&A / repo exploration / API understanding. Uses `detect_hallucination`.

2) **Generate Boilerplate/Content** → `GENERATE_BOILERPLATE_VERIFICATION.md`
   Tests/docs/migrations/configs. Uses `audit_trace_budget` to verify *constraints and decisions*.

3) **Inline Completions** → `INLINE_COMPLETION_VERIFICATION.md`
   Spot-check high-impact tab-complete. Uses `audit_trace_budget` with a 3–6 step micro-trace.

4) **Refactoring & Bug Fixes** → `REFACTOR_AND_BUGFIX_VERIFICATION.md`
   RCA-gated changes with an audited claim trace. Uses `audit_trace_budget`.

5) **Greenfield Prototyping** → `GREENFIELD_PROTOTYPE_VERIFICATION.md`
   Move fast with **Facts vs Decisions vs Assumptions**, and verify Facts via `detect_hallucination`.

6) **RCA Fix Agent** → MCP prompt `rca_fix_agent` + `RCA_FIX_REPORT_TEMPLATE.md`
   Full debugging loop: baseline → hypotheses → verify ROOT_CAUSE → fix → test → verify claims. Uses `audit_trace_budget` with minimum claims (ROOT_CAUSE, FIX_MECHANISM, FIX_VERIFIED, NO_NEW_FAILURES).

---

## What “max contrast” means here
Each playbook includes a worked example with:
- **❌ Without Strawberry** — a plausible, confident answer that’s easy to hallucinate
- **✅ With Strawberry** — evidence pack spans + citations + a verifier call, ending in an answer you can trust

