# Berry

## Workflow verification playbooks

Want the “with vs without hallucination detector” experience? Start here:

- `docs/workflows/README.md` — index of workflow playbooks
  - Search & Learn
  - Generate Boilerplate/Content
  - Inline Completions
  - Refactoring & Bug Fixes (RCA-gated)
  - Greenfield Prototyping

Each playbook includes a **maximally contrasting** worked example (❌ vibes vs ✅ evidence + verifier).

Berry runs a local MCP server with a safe, repo‑scoped toolpack plus verification tools (`detect_hallucination`, `audit_trace_budget`).

Berry ships a single MCP surface: **classic**.

Classic includes:
- Strawberry verification tools (`detect_hallucination`, `audit_trace_budget`)
- Run & evidence notebook tools (start/load runs, add/list/search spans)

See `docs/MCP.md` and `docs/workflows/README.md`.

Berry integrates with Cursor, Codex, Claude Code, and Gemini CLI via config files committed to your repo.

## Quickstart

1) Install (from this repo):

```bash
pipx install -e .
```

Fallback:

```bash
pip install -e .
```

2) In the repo you want to use:

First, set your verifier API key (recommended):

```bash
berry auth
```

Then install repo-scoped MCP config files:

```bash
berry init
```

Optional: enable strict verification gates for that repo:

```bash
berry init --strict
```

3) Reload MCP servers in your client.

Optional: register Berry globally (user-level configs) so you don't have to commit repo files:

```bash
berry integrate

# macOS .pkg installers may also deploy system-managed configs:
#   berry integrate --managed-only
```

4) Use a prompt/workflow (Prepare PR, Trace failing test, Summarize repo architecture, Search & Learn (verified), Generate Boilerplate/Content (verified), Inline completion guard, Greenfield prototyping).

## Docs

- `docs/USAGE.md` — task‑oriented guides
- `docs/CLI.md` — command reference
- `docs/CONFIGURATION.md` — config files, defaults, and env vars
- `docs/MCP.md` — tools/prompts and transport details
- `docs/PACKAGING.md` — release pipeline (macOS pkg + Homebrew cask)

## Tests

```bash
pytest
```