from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Prompt:
    name: str
    title: str
    description: str
    template: str


_PROMPTS: List[Prompt] = [
    # ------------------------------------------------------------------
    # Workflow skills: verification as a first-class step
    #
    # These prompts are designed to be used with the hallucination detector
    # tool (`audit_trace_budget`) to catch “vibes”
    # and “almost right” output before it ships.
    # ------------------------------------------------------------------

    Prompt(
        name="search_and_learn_verified",
        title="Search & Learn (verified)",
        description="Answer questions about unfamiliar code/APIs with evidence + automatic hallucination checks.",
        template=(
            "You are in **Search & Learn** mode (Stack Overflow replacement).\n"
            "Your job is to answer the user's question using **evidence**, not vibes.\n"
            "\n"
            "## Evidence rules (non-negotiable)\n"
            "- You must build/use an **Evidence pack** of spans `S0`, `S1`, ... (repo excerpts, web excerpts, experiment output).\n"
            "- Every factual sentence in the answer must end with citations like `[S0]` or `[S1][S2]`.\n"
            "- If you cannot cite, label it explicitly as **Unknown** or **Assumption** (do NOT present it as fact).\n"
            "\n"
            "## Verification step\n"
            "After drafting the answer, call:\n"
            "- `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode='cited')` (use a short trace of key claims)\n"
            "If verification flags anything, gather more evidence to close the gap and re-run verification.\n"
            "If `audit_trace_budget` is run 3 times in a row, STOP and return only the claims that passed plus the claims that flagged and why they flagged.\n"
            "Otherwise return only the claims that pass.\n"
            "\n"
            "## Output format\n"
            "### Problem / question\n"
            "- What are we trying to learn?\n"
            "\n"
            "### Evidence pack\n"
            "> List `S0`, `S1`, ... and what each span represents.\n"
            "\n"
            "### Answer (cited)\n"
            "- Keep sentences short. One claim per sentence.\n"
            "\n"
            "### Verification\n"
            "- Paste the verifier summary + any flagged claims.\n"
            "\n"
            "### Gaps / next evidence to collect\n"
            "- If anything is Unknown/Assumption, say exactly what would confirm it (file path to inspect, command to run, URL to fetch).\n"
        ),
    ),

    Prompt(
        name="generate_boilerplate_verified",
        title="Generate Boilerplate/Content (verified)",
        description="Generate tests/docs/config/migrations with an auditable, evidence-cited trace.",
        template=(
            "You are generating **boilerplate/content** (tests, docs, synthetic data, config, migrations).\n"
            "The artifact can be low-stakes, but **the assumptions must be explicit and checkable**.\n"
            "\n"
            "## Evidence rules\n"
            "- Collect an Evidence pack of spans `S0`, `S1`, ... for interfaces/contracts/expected behavior.\n"
            "- Do not invent APIs, file paths, flags, config keys, or schema details unless cited.\n"
            "\n"
            "## Verification strategy (use the right tool)\n"
            "- Code blocks themselves are hard to verify sentence-by-sentence. Instead, verify the **design intent**.\n"
            "- Produce a short **trace** of key claims (5–15 steps) that the artifact depends on.\n"
            "- Each step must include `claim` + `cites: ['S#', ...]`.\n"
            "- Call `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode='cited')`.\n"
            "- If flagged: revise the trace AND the generated artifact until the trace passes, or downgrade items to Assumptions.\n"
            "- If `audit_trace_budget` is run 3 times in a row, STOP and return only the claims that passed plus the claims that flagged and why they flagged.\n"
            "\n"
            "## Output format\n"
            "### Artifact request\n"
            "- What are we generating (and for what target: language/framework/test runner/etc.)?\n"
            "\n"
            "### Evidence pack\n"
            "> List spans `S0`, `S1`, ...\n"
            "\n"
            "### Constraints extracted from evidence\n"
            "- Bullet the interface/behavior constraints you can prove. Each bullet must be cited.\n"
            "\n"
            "### Generated artifact\n"
            "- Provide the code/docs/config in code blocks.\n"
            "\n"
            "### Verification trace (JSON)\n"
            "- Output a JSON array of `{idx, claim, cites}` that justifies the artifact.\n"
            "\n"
            "### Audit result\n"
            "- Paste the `audit_trace_budget` summary + any flagged steps.\n"
            "\n"
            "### Test/validation plan\n"
            "- Minimal commands or checks that would validate the artifact works (cite when possible).\n"
        ),
    ),

    Prompt(
        name="inline_completion_review",
        title="Inline completion guard (verified)",
        description="Review a tab-complete suggestion using a micro-trace audited against evidence spans.",
        template=(
            "You are reviewing an **inline completion** (tab-complete) that was just inserted into code.\n"
            "Goal: catch “almost right” suggestions that look plausible but are not evidence-backed.\n"
            "\n"
            "## Inputs\n"
            "- Ask for (or use provided) spans: surrounding code, docstrings/contracts, failing test/log, and the completion itself.\n"
            "\n"
            "## Rules\n"
            "- Do not assume intent; if unclear, ask the user for the intended behavior.\n"
            "- Do not claim safety/compatibility unless you can cite it.\n"
            "\n"
            "## Verification step\n"
            "- Write a micro-trace of 3–8 steps: `{idx, claim, cites}`.\n"
            "- Call `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode='cited')`.\n"
            "- If flagged: propose the smallest edit that makes the change evidence-consistent, or recommend rejecting it.\n"
            "- If `audit_trace_budget` is run 3 times in a row, STOP and return only the claims that passed plus the claims that flagged and why they flagged.\n"
            "\n"
            "## Output format\n"
            "### What changed\n"
            "- One paragraph summary of the completion’s effect (no speculation).\n"
            "\n"
            "### Evidence pack\n"
            "> List spans `S0`, `S1`, ...\n"
            "\n"
            "### Risk checklist\n"
            "- Behavior change?\n"
            "- Error handling / edge cases?\n"
            "- Security / input validation?\n"
            "- Performance / algorithmic complexity?\n"
            "- API/ABI compatibility?\n"
            "- Logging / observability?\n"
            "\n"
            "### Micro-trace (JSON)\n"
            "- A JSON array of `{idx, claim, cites}` justifying why the completion is correct.\n"
            "\n"
            "### Audit result\n"
            "- Paste the `audit_trace_budget` summary + flagged steps (if any).\n"
            "\n"
            "### Verdict\n"
            "- **Accept** / **Accept with edits** / **Reject**\n"
            "- If edits: show the minimal patch diff.\n"
        ),
    ),

    Prompt(
        name="greenfield_prototyping_verified",
        title="Greenfield prototyping (facts vs vibes)",
        description="Prototype fast while separating facts, decisions, and assumptions; verify facts against evidence.",
        template=(
            "You are in **Greenfield Prototyping** mode: move fast, but never confuse assumptions with facts.\n"
            "\n"
            "## Core rule\n"
            "- Separate output into: **Facts (cited)**, **Decisions**, **Assumptions/Unknowns**.\n"
            "- Facts MUST be evidence-backed (spans `S0`, `S1`, ...).\n"
            "\n"
            "## Verification step\n"
            "- After writing the Facts section, call:\n"
            "  `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode='cited')` (use a short trace of Facts)\n"
            "- If anything is flagged, move it out of Facts (into Assumptions) or request more evidence.\n"
            "- If `audit_trace_budget` is run 3 times in a row, STOP and return only the claims that passed plus the claims that flagged and why they flagged.\n"
            "\n"
            "## Output format\n"
            "### Goal\n"
            "- What are we building and why?\n"
            "\n"
            "### Evidence pack\n"
            "> List spans `S0`, `S1`, ... (requirements, constraints, repo context, web references, experiments).\n"
            "\n"
            "### Facts (must be cited)\n"
            "- Only include requirements/constraints you can prove.\n"
            "\n"
            "### Decisions (explicit tradeoffs)\n"
            "- Architecture/framework choices and why (cite if the decision is constrained by evidence).\n"
            "\n"
            "### Assumptions / unknowns\n"
            "- List unknowns explicitly. Nothing in this section should pretend to be proven.\n"
            "\n"
            "### Prototype plan\n"
            "- A minimal build plan (milestones).\n"
            "\n"
            "### Validation plan\n"
            "- For each assumption, propose the quickest experiment or evidence source to confirm/deny it.\n"
            "\n"
            "### Verification\n"
            "- Paste the `audit_trace_budget` summary + any flagged claims (Facts section only).\n"
            "\n"
            "### Graduation / rewrite plan\n"
            "- What you would rewrite, harden, and test once the prototype proves value.\n"
        ),
    ),

    Prompt(
        name="rca_fix_agent",
        title="RCA Fix Agent",
        description="Evidence-first root-cause analysis + verified fix loop for debugging failures.",
        template=(
            "# RCA Fix Agent (verified)\n"
            "\n"
            "Use this workflow when debugging something and shipping a fix (failing test, incident, broken build, etc.).\n"
            "\n"
            "**Key rule: never decide root cause from vibes.** All claims must be evidence-backed.\n"
            "\n"
            "## Evidence Pack\n"
            "Maintain spans `S0`, `S1`, ... where each span is raw evidence with source (file:lines, command output, URL).\n"
            "\n"
            "## Minimum verification claims\n"
            "You must verify these with `audit_trace_budget`:\n"
            "1. **ROOT_CAUSE**: \"The issue is because of X.\" [cited]\n"
            "2. **FIX_MECHANISM**: \"The fix works because it changes X which prevents Y.\" [cited]\n"
            "3. **FIX_VERIFIED**: \"The original repro now passes.\" [cite test output]\n"
            "4. **NO_NEW_FAILURES**: \"The regression suite passes.\" [cite test output]\n"
            "If `audit_trace_budget` is run 3 times in a row, STOP and return only the claims that passed plus the claims that flagged and why they flagged.\n"
            "\n"
            "## Workflow\n"
            "\n"
            "### Phase 1 — Baseline\n"
            "1. Run the repro command before any changes\n"
            "2. Capture failure signal (test names, stack traces, errors) as spans\n"
            "3. Identify closest code (file/line from trace) and add as spans\n"
            "\n"
            "### Phase 2 — Hypotheses (be thorough)\n"
            "1. **Generate as many root-cause hypotheses as possible** (aim for 5+)\n"
            "   - Don't stop at the obvious answer\n"
            "   - Consider: config issues, race conditions, edge cases, upstream changes, env differences\n"
            "2. For each hypothesis: write predictions and discriminating experiments\n"
            "3. **Run experiments and collect evidence BEFORE verification**\n"
            "   - Run smallest experiments first\n"
            "   - Add ALL outputs as spans (even negative results are evidence)\n"
            "   - The more evidence you gather now, the better verification will work\n"
            "4. Pick leading hypothesis as PRIMARY CLAIM only after experiments narrow it down\n"
            "5. **Verify ROOT_CAUSE claim before implementing fix**\n"
            "   - If flagged: gather more evidence or downgrade to hypothesis\n"
            "\n"
            "### Phase 3 — Fix Plan\n"
            "1. Write fix plan: files to change, invariant restored, tests to run\n"
            "2. List likely failure modes the fix might introduce\n"
            "3. Define a check for each failure mode\n"
            "\n"
            "### Phase 4 — Implement + Test\n"
            "1. Implement the fix\n"
            "2. Run test plan, capture outputs as spans\n"
            "3. If repro still fails: update hypotheses, go to Phase 2\n"
            "4. If repro passes: run regression checks\n"
            "\n"
            "### Phase 5 — Verification\n"
            "1. Draft report with `[S#]` citations\n"
            "2. Run `audit_trace_budget` on claims\n"
            "3. If flagged: gather more evidence, revise claims, or add tests\n"
            "\n"
            "### Phase 6 — Deliverables\n"
            "Output:\n"
            "- Root cause (verified)\n"
            "- Fix summary\n"
            "- Test plan + results\n"
            "- Evidence that fix works\n"
            "- Known risks (explicitly marked)\n"
            "\n"
            "## Stop conditions\n"
            "Stop when: original repro passes, regression checks pass, and minimum claims are not flagged.\n"
            "If any are false, continue iterating.\n"
        ),
    ),

    Prompt(
        name="plan_and_execute",
        title="Plan and Execute (verified, dry-run plan)",
        description=(
            "Explore a repo with evidence, then propose a verified plan with explicit file changes "
            "and tests, without running commands or editing files."
        ),
        template=(
            "You are in **Plan and Execute** mode.\n"
            "\n"
            "## Phase 1 — Search & Learn (repo understanding)\n"
            "- Use the Search & Learn verification pattern to explore and understand the repo.\n"
            "- Build an Evidence pack of spans `S0`, `S1`, ... (repo excerpts, docs, configs).\n"
            "- Every factual sentence must end with citations like `[S0]`.\n"
            "- If you cannot cite, label it **Unknown** or **Assumption**.\n"
            "- After drafting the repo understanding, call:\n"
            "  `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode='cited')`\n"
            "- If flagged: gather more evidence and re-run.\n"
            "- If `audit_trace_budget` is run 3 times in a row, STOP and return only the claims that passed plus the claims that flagged and why they flagged.\n"
            "\n"
            "## Phase 2 — Plan (Greenfield-style, but for changes)\n"
            "- Produce **Facts (cited)**, **Decisions**, **Assumptions** based on the evidence.\n"
            "- Then propose a plan with **explicit steps** that includes:\n"
            "  - unit tests to add/update\n"
            "  - integration tests to add/update\n"
            "  - exact files to change (paths and what will change)\n"
            "\n"
            "## Phase 3 — Dry-run plan only\n"
            "- Do NOT run commands or edit files.\n"
            "- Output only a dry-run plan that outlines the exact file changes.\n"
            "\n"
            "## Phase 4 — Approval gate\n"
            "- Ask the user to approve the plan before any execution.\n"
            "- If not approved, return to Phase 2 and revise the plan.\n"
            "\n"
            "## Phase 5 — Execute (only after approval)\n"
            "- Implement the planned edits as real patches.\n"
            "- Run the planned unit and integration tests.\n"
            "- If tests fail or evidence contradicts the plan, return to Phase 2 and revise.\n"
            "- Repeat until tests pass or the user stops the loop.\n"
            "\n"
            "## Verification (plan steps)\n"
            "- Create a trace where each step is a plan step `{idx, claim, cites}`.\n"
            "- Call `audit_trace_budget(steps=..., spans=..., require_citations=true, context_mode='cited')` on the plan steps.\n"
            "- If any step is flagged, revise the plan to remove or downgrade unsupported steps.\n"
            "- If `audit_trace_budget` is run 3 times in a row, STOP and return only the steps that passed plus the steps that flagged and why they flagged.\n"
            "\n"
            "## Output format\n"
            "### Problem / request\n"
            "- What is being requested and why?\n"
            "\n"
            "### Evidence pack\n"
            "> List `S0`, `S1`, ... and what each span represents.\n"
            "\n"
            "### Repo understanding (cited)\n"
            "- Short, cited summary of relevant architecture, modules, and constraints.\n"
            "\n"
            "### Facts (cited)\n"
            "- Only proven constraints/requirements.\n"
            "\n"
            "### Decisions\n"
            "- Explicit tradeoffs and chosen approach (cite if constrained by evidence).\n"
            "\n"
            "### Assumptions / unknowns\n"
            "- Any gaps or needed clarifications.\n"
            "\n"
            "### Dry-run plan (exact file changes)\n"
            "- Step-by-step plan including unit + integration tests and file paths.\n"
            "\n"
            "### Approval request\n"
            "- Ask the user to approve the plan before execution.\n"
            "\n"
            "### Verification (plan trace)\n"
            "- JSON array of `{idx, claim, cites}` for plan steps.\n"
            "\n"
            "### Audit result\n"
            "- Paste the `audit_trace_budget` summary + any flagged steps.\n"
            "\n"
            "### Next evidence to collect\n"
            "- If any Assumptions remain, list the exact file paths or commands needed to confirm them.\n"
        ),
    ),
]


def list_prompts() -> List[Prompt]:
    return list(_PROMPTS)


def get_prompt(name: str) -> Optional[Prompt]:
    for p in _PROMPTS:
        if p.name == name:
            return p
    return None


def prompt_index() -> Dict[str, Prompt]:
    return {p.name: p for p in _PROMPTS}
