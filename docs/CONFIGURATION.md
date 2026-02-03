# Berry configuration

## Global config

Berry stores global config at:

- `~/.berry/config.json`
- or `$BERRY_HOME/config.json` if `BERRY_HOME` is set.

Default schema:

```json
{
  "allow_write": false,
  "allow_exec": false,
  "allow_web": false,
  "allow_web_private": false,
  "allowed_roots": [],
  "enforce_verification": false,
  "require_plan_approval": false,
  "verification_write_default_target": 0.95,
  "verification_output_default_target": 0.95,
  "verification_min_target": 0.55,
  "exec_allowed_commands": [
    "python",
    "python3",
    "pytest",
    "git",
    "npm",
    "node",
    "yarn",
    "pnpm",
    "make"
  ],
  "exec_network_mode": "inherit",
  "web_search_provider": "duckduckgo",
  "brave_search_api_key": null,
  "searxng_url": null,
  "web_search_stub_results": [],
  "diagnostics_opt_in": false,
  "audit_log_enabled": true,
  "audit_log_retention_days": 30,
  "paid_features_enabled": false
}
```

## Project config override

If present, `./.berry/config.json` overrides global keys for that repo.

## Environment variables

Used by the MCP server:

- `BERRY_HOME` — override the Berry home directory.
- `BERRY_HOST` — default host for non‑stdio transports.
- `BERRY_PORT` — default port for non‑stdio transports.
- `BERRY_PROJECT_ROOT` — force the project root for the server.
- `BERRY_ENFORCE_VERIFICATION` — override `enforce_verification` (truthy values: `1,true,yes,y,on`).
- `BERRY_WEB_SEARCH_PROVIDER` — override `web_search_provider` (duckduckgo|brave|searxng|stub).
- `BRAVE_SEARCH_API_KEY` — Brave Search token (when using the brave provider).
- `SEARXNG_URL` — base URL of your SearXNG instance (when using the searxng provider).
- `BERRY_EXEC_NETWORK_MODE` — override `exec_network_mode` (inherit|deny|deny_if_possible).
- `BERRY_MCP_ENV_JSON` — JSON object string of env vars to apply when Berry runs as an MCP server
  (and to embed into generated client config files).
- `OPENAI_API_KEY` — required for `detect_hallucination` / `audit_trace_budget` (OpenAI backend).
- `OPENAI_BASE_URL` — optional override for OpenAI-compatible endpoints.
- `BERRY_MODEL` — default model name used by Berry (default: `chat`).
- `BERRY_VERIFIER_MODEL` — model name used by the verifier (default: `BERRY_MODEL`).
- `BERRY_VERIFIER_BACKEND` — verifier backend for budgets (`openai` default; `dummy` for offline tests).

### MCP env defaults

Berry can optionally read `~/.berry/mcp_env.json` (or `$BERRY_HOME/mcp_env.json`) on startup and apply
any key/value pairs as process environment variables (without overriding existing env vars). This is
useful for configuring verifier endpoints (e.g., `OPENAI_BASE_URL`) without requiring every client
to support per-server env injection.

Be careful: this file may contain secrets (API keys). Keep it out of repos.

Tip: you can manage this file via the CLI:

```bash
berry auth            # prompts, then writes ~/.berry/mcp_env.json
berry auth sk-...     # non-interactive
berry auth --unset    # remove key
```

## Safety model

- `add_file_span` respects `allowed_roots` and the project root for file access.
- Config options like `allow_write`, `allow_exec`, `allow_web` are preserved for future tool expansions.
- When writes are enabled (future), paths must be inside the repo root or an allowed root.

## Files created by Berry

- Audit log: `~/.berry/audit.log.jsonl`
- Support bundles: `~/.berry/support_bundles/`
- License payload: `~/.berry/license.json`
- MCP env defaults (optional): `~/.berry/mcp_env.json` (used for injecting env vars like `OPENAI_BASE_URL` / `OPENAI_API_KEY`)
