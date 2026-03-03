# Berry

Berry is a local MCP server for evidence-first workflows. It gives agents a small, repo-scoped toolset for collecting evidence and verifying whether claims are supported.

## Workflow playbooks

Start with `docs/workflows/README.md` (index of workflow playbooks). Each playbook includes:

- a short checklist
- a worked example without verification (common failure modes)
- a worked example with verification (evidence pack + verifier call)
- a copy/paste prompt you can pin in your client

## MCP surface

Berry ships a single MCP surface: **classic**.

Classic includes:
- Verification tools (`detect_hallucination`, `audit_trace_budget`)
- Run & evidence notebook tools (start/load runs, add/list/search spans)

See `docs/MCP.md` and `docs/workflows/README.md` for details.

Berry integrates with Cursor, Codex, Claude Code, and Gemini CLI via config files committed to your repo.

## Supported verifier backends

Berry’s current verification method requires token logprobs (Chat Completions-style `logprobs` + `top_logprobs`).

Supported today:
- `openai` (default): OpenAI-compatible Chat Completions endpoints with logprobs (OpenAI, OpenRouter, local vLLM, or any compatible `base_url`)
- `gemini`: Gemini Developer API `generateContent` with token logprobs via `logprobsResult` (when enabled for the model)
- `vertex`: Vertex AI `generateContent` (Gemini models) with token logprobs via `logprobsResult`
- `dummy`: deterministic offline backend for tests/dev

Not supported yet:
- Anthropic (OpenAI-compat layer ignores `logprobs`)

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
berry setup
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

Optional: register Berry globally (user-level configs) so you do not need to commit repo files:

```bash
berry integrate

# macOS .pkg installers may also deploy system-managed configs:
#   berry integrate --managed-only
```

4) Use a prompt/workflow (Search & Learn (verified), Generate Boilerplate/Content (verified), Inline completion guard, Greenfield prototyping, RCA Fix Agent).

## Docs

- `docs/USAGE.md` — task-oriented guides
- `docs/CLI.md` — command reference
- `docs/CONFIGURATION.md` — config files, defaults, and env vars
- `docs/MCP.md` — tools/prompts and transport details
- `docs/PACKAGING.md` — release pipeline (macOS pkg + Homebrew cask)

## Tests

```bash
pytest
```
