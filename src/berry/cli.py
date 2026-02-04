from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Optional

from . import __version__
from .audit import export_events, prune_events
from .clients import (
    berry_server_spec,
    berry_server_specs,
    render_claude_mcp_json,
    render_codex_config_toml,
    render_cursor_deeplink,
    render_cursor_mcp_json,
    render_gemini_settings_json,
    write_claude_mcp_json,
    write_codex_config_toml,
    write_cursor_mcp_json,
    write_gemini_settings_json,
)
from .config import BerryConfig, load_config, save_global_config
from .mcp_server import main as mcp_classic_main
from .recipes import (
    builtin_recipes,
    export_recipes,
    get_builtin_recipe,
    install_recipe_file_to_project,
    install_recipe_to_project,
)
from .support import create_support_bundle
from .verify import verify_blob_with_cosign
from .paths import ensure_berry_home, license_path, mcp_env_path
from .integration import integrate, results_as_json
from .auth_flow import run_login_flow

# --------------------------------------------------------------------
# Claude Code skill file content (repo-scoped).
# Written by `berry init` unless --no-claude-skill is passed.
# --------------------------------------------------------------------

_CLAUDE_BERRY_SKILL_MD = """# Berry: evidence-first workflow

You have access to Berry MCP tools that *verify* claims against gathered evidence.

## Which tool to use
- Use **berry_solve** to answer questions.
- Use **berry_change** to produce a verified *plan* for code changes.
- Use **berry_status** to see what the server can do (web/exec/write, baseline mode).
- Use **berry_approve** only after the user explicitly approves a pending grant.
- Use **berry_health** for a quick self-test.

## Read the tool state machine (do not guess)
Berry responses include **state**:

- **state=need_grant**
  - Action: Show the user what scopes are being requested (from **grant_scopes** and **grant_summary**).
  - Ask: "Approve? (yes/no)".
  - Only if the user says yes: call **berry_approve(run_id, grant_token)**.
  - Then retry the original call with the same **run_id**.

- **state=ask_user**
  - Action: Ask the user the returned **questions** verbatim.
  - Then retry with the same **run_id**, passing answers in **user_context** (or append to the question).

- **state=done**
  - Action: Use the returned verified **answer** / **plan**.

- **state=cannot**
  - Action: Switch to a different tool surface or ask the user for the missing artifact.

## Evidence rules (how to avoid hallucinations)
- Treat Berry's evidence spans as the only source of truth for factual claims.
- Prefer repo-baseline evidence (git) over working-tree evidence.
- If the repo is empty (greenfield), ask the user for requirements unless they explicitly say "use best judgement".

## Common pitfalls
- Do not keep re-calling Berry when it returns **state=ask_user**. Ask the user first.
- Do not answer Berry's clarifying questions yourself unless the user delegated ("use best judgement").
- If you need working-tree evidence, capture it explicitly as spans (e.g., `add_file_span`) rather than relying on unstated context.
"""



def _find_repo_root(start: Path) -> Path:
    p = Path(start).resolve()
    for _ in range(50):
        if (p / ".git").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(start).resolve()


def _write_claude_skill_file(project_root: Path, *, force: bool) -> Optional[Path]:
    """Write a repo-scoped Claude Code rules/skill file for Berry.

    This reduces agent thrash by teaching the Berry state machine and tool roles.
    """
    dst = project_root / ".claude" / "rules" / "berry.md"
    try:
        if dst.exists() and not force:
            return None
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_CLAUDE_BERRY_SKILL_MD, encoding="utf-8")
        return dst
    except Exception:
        return None


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    argv: list[str] = []
    if args.transport:
        argv += ["--transport", str(args.transport)]
    if args.host:
        argv += ["--host", str(args.host)]
    if args.port is not None:
        argv += ["--port", str(int(args.port))]
    if args.project_root:
        argv += ["--project-root", str(args.project_root)]
    # Berry ships a single MCP surface (classic). Older configs may still pass
    # `--server science` or `--server forge`; treat them as aliases for classic.
    _server = str(getattr(args, "server", "classic") or "classic").strip().lower()
    if _server != "classic":
        _server = "classic"
    mcp_classic_main(argv=argv)
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    # Resolve the intended project root.
    #
    # Safety: if we can't find a .git root and the user didn't explicitly set
    # --project-root, we fail closed by default to avoid accidentally treating a
    # broad directory (e.g. $HOME) as the "project".
    if getattr(args, "project_root", None):
        project_root = Path(args.project_root).expanduser().resolve()
    else:
        project_root = _find_repo_root(Path.cwd())
        allow_non_git = os.environ.get("BERRY_ALLOW_NON_GIT_ROOT", "").strip().lower() in {"1", "true", "yes", "y", "on"}
        if not (project_root / ".git").exists() and not allow_non_git:
            raise SystemExit(
                "Could not find a .git directory from the current working directory. "
                "Run `berry init` from inside a git repo, pass --project-root, or set BERRY_ALLOW_NON_GIT_ROOT=1."
            )
    force = bool(args.force)
    strict = bool(getattr(args, "strict", False))

    # Preflight: avoid partial state by checking for any conflicts before writing.
    targets: list[Path] = [
        project_root / ".cursor" / "mcp.json",
        project_root / ".codex" / "config.toml",
        project_root / ".mcp.json",
        project_root / ".gemini" / "settings.json",
    ]
    if strict:
        targets.append(project_root / ".berry" / "config.json")
    if not force:
        conflicts = [t for t in targets if t.exists()]
        if conflicts:
            raise FileExistsError("Refusing to overwrite existing files (use --force): " + ", ".join(str(c) for c in conflicts))

    created: list[Path] = []
    # Berry now ships a single MCP surface (classic). Any profile value is treated as classic.
    profile = str(getattr(args, "profile", "classic") or "classic")
    specs = berry_server_specs(profile=profile, name="berry")

    created.append(write_cursor_mcp_json(project_root=project_root, spec=specs, force=force))
    created.append(write_codex_config_toml(project_root=project_root, spec=specs, force=force))
    created.append(write_claude_mcp_json(project_root=project_root, spec=specs, force=force))
    created.append(write_gemini_settings_json(project_root=project_root, spec=specs, force=force))



    # Optional: install a repo-scoped Claude Code skill file so agents understand Berry's state machine.
    if not bool(getattr(args, "no_claude_skill", False)):
        p = _write_claude_skill_file(project_root, force=force)
        if p is not None:
            created.append(p)



    # Project-local Berry config folder (optional but useful for recipes/workflows).
    berry_dir = project_root / ".berry"
    berry_dir.mkdir(parents=True, exist_ok=True)
    if strict:
        cfg_path = berry_dir / "config.json"
        if cfg_path.exists() and not force:
            raise FileExistsError(f"Refusing to overwrite: {cfg_path} (use --force)")
        cfg_path.write_text(json.dumps({"enforce_verification": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        created.append(cfg_path)

    for p in created:
        print(str(p))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    cfg = load_config(project_root=project_root)

    checks = {
        "python": sys.version.split()[0],
        "project_root": str(project_root),
        "allow_write": cfg.allow_write,
        "allow_exec": cfg.allow_exec,
        "allow_web": cfg.allow_web,
        "enforce_verification": cfg.enforce_verification,
        "require_plan_approval": cfg.require_plan_approval,
        "audit_log_enabled": cfg.audit_log_enabled,
        "diagnostics_opt_in": cfg.diagnostics_opt_in,
    }
    print(json.dumps(checks, indent=2))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    cfg = load_config(project_root=project_root)
    print(json.dumps(asdict(cfg), indent=2, sort_keys=True))
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    cfg = load_config(project_root=None)
    key = str(args.key)
    raw = str(args.value)

    bool_keys = {
        "allow_write",
        "allow_exec",
        "allow_web",
        "allow_web_private",
        "enforce_verification",
        "require_plan_approval",
        "diagnostics_opt_in",
        "audit_log_enabled",
        "paid_features_enabled",
    }
    float_keys = {
        "verification_write_default_target",
        "verification_output_default_target",
        "verification_min_target",
    }
    int_keys = {
        "audit_log_retention_days",
    }

    str_keys = {
        # Execution
        "exec_network_mode",  # inherit|deny|deny_if_possible
        # Web search
        "web_search_provider",  # duckduckgo|brave|searxng|stub
        "searxng_url",
        "brave_search_api_key",
    }

    if key in bool_keys:
        truthy = raw.strip().lower() in {"1", "true", "yes", "y", "on"}
        new_cfg = replace(cfg, **{key: bool(truthy)})
    elif key in float_keys:
        new_cfg = replace(cfg, **{key: float(raw)})
    elif key in int_keys:
        new_cfg = replace(cfg, **{key: int(raw)})
    elif key == "exec_allowed_commands":
        cmds = [c.strip() for c in raw.split(",") if c.strip()]
        if not cmds:
            raise SystemExit("exec_allowed_commands must be a non-empty comma-separated list")
        new_cfg = replace(cfg, exec_allowed_commands=cmds)
    elif key in str_keys:
        v = raw.strip()
        if key == "exec_network_mode":
            if v not in {"inherit", "deny", "deny_if_possible"}:
                raise SystemExit("exec_network_mode must be one of: inherit, deny, deny_if_possible")
            new_cfg = replace(cfg, exec_network_mode=v)
        elif key == "web_search_provider":
            if v not in {"duckduckgo", "brave", "searxng", "stub"}:
                raise SystemExit("web_search_provider must be one of: duckduckgo, brave, searxng, stub")
            new_cfg = replace(cfg, web_search_provider=v)
        elif key == "searxng_url":
            # Empty string unsets.
            new_cfg = replace(cfg, searxng_url=(v if v else None))
        elif key == "brave_search_api_key":
            # Empty string unsets.
            new_cfg = replace(cfg, brave_search_api_key=(v if v else None))
        else:
            new_cfg = replace(cfg, **{key: v})
    else:
        raise SystemExit(f"Unsupported key: {key}")

    p = save_global_config(new_cfg)
    print(str(p))
    return 0


def cmd_config_add_root(args: argparse.Namespace) -> int:
    cfg = load_config(project_root=None)
    root = str(Path(args.path).expanduser().resolve())
    if root in cfg.allowed_roots:
        print("already-present")
        return 0
    new_cfg = replace(cfg, allowed_roots=[*cfg.allowed_roots, root])
    p = save_global_config(new_cfg)
    print(str(p))
    return 0


def cmd_config_remove_root(args: argparse.Namespace) -> int:
    cfg = load_config(project_root=None)
    root = str(Path(args.path).expanduser().resolve())
    new_roots = [r for r in cfg.allowed_roots if r != root]
    new_cfg = replace(cfg, allowed_roots=new_roots)
    p = save_global_config(new_cfg)
    print(str(p))
    return 0


def cmd_auth_login(args: argparse.Namespace) -> int:
    """Browser-based authentication flow (like Claude Code, Codex, Gemini CLI).

    Opens a browser for authentication via the Strawberry website.
    For headless environments, use --device to display a code instead.
    """
    force_device = bool(getattr(args, "device", False))
    force_localhost = bool(getattr(args, "localhost", False))
    no_integrate = bool(getattr(args, "no_integrate", False))
    verbose = bool(getattr(args, "verbose", False))

    return run_login_flow(
        force_device=force_device,
        force_localhost=force_localhost,
        no_integrate=no_integrate,
        interactive=True,
        verbose=verbose,
    )


def cmd_auth_status(_: argparse.Namespace) -> int:
    """Show current authentication status."""
    p = mcp_env_path()

    if not p.exists():
        print("Not authenticated.")
        print(f"Run 'berry auth login' to authenticate.")
        return 1

    try:
        env = json.loads(p.read_text(encoding="utf-8"))
        api_key = env.get("OPENAI_API_KEY", "")

        if not api_key:
            print("Not authenticated.")
            print(f"Run 'berry auth login' to authenticate.")
            return 1

        # Mask the API key
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"

        print("Authenticated")
        print(f"  API Key: {masked}")
        print(f"  Config:  {p}")

        base_url = env.get("OPENAI_BASE_URL", "")
        if base_url:
            print(f"  Base URL: {base_url}")

        return 0
    except Exception as e:
        print(f"Error reading config: {e}")
        return 1


def cmd_auth_logout(_: argparse.Namespace) -> int:
    """Remove saved credentials."""
    p = mcp_env_path()

    if not p.exists():
        print("No credentials found.")
        return 0

    try:
        env = json.loads(p.read_text(encoding="utf-8"))
        env.pop("OPENAI_API_KEY", None)

        if env:
            # Keep other settings
            p.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            # Remove empty file
            p.unlink()

        print("Logged out successfully.")
        print(f"Removed credentials from: {p}")
        return 0
    except Exception as e:
        print(f"Error removing credentials: {e}")
        return 1


def cmd_auth_default(args: argparse.Namespace) -> int:
    """Default auth command - show help if no subcommand."""
    # Check if user passed a positional argument (legacy `berry auth <key>` usage)
    # This maintains backwards compatibility
    if hasattr(args, "api_key") and args.api_key:
        # Legacy mode: treat as `berry auth set <key>`
        return cmd_auth(args)

    # No subcommand - show help
    print("Berry Authentication")
    print("")
    print("Commands:")
    print("  berry auth login     Authenticate via browser (recommended)")
    print("  berry auth set       Set API key directly (for CI/CD)")
    print("  berry auth status    Show current authentication status")
    print("  berry auth logout    Remove saved credentials")
    print("")
    print("Examples:")
    print("  berry auth login             # Opens browser for authentication")
    print("  berry auth login --device    # For headless environments (SSH, containers)")
    print("  berry auth set sk-xxx        # Set API key directly")
    print("  echo sk-xxx | berry auth set --stdin")
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    """Store API keys / env defaults for MCP launches.

    This writes a JSON object to `~/.berry/mcp_env.json` (or `$BERRY_HOME/mcp_env.json`).
    That file is then:
      - embedded into generated client config files (`berry init`, `berry print-config`, ...)
      - applied at server startup (without overriding explicit process env)

    Usage:
      - `berry auth --interactive` (guided setup; writes global client configs)
      - `berry auth sk-...` (quick, but shows in shell history)
      - `berry auth` (prompts securely)
      - `echo sk-... | berry auth --stdin` (no history)
    """
    ensure_berry_home()
    p = mcp_env_path()

    # Static defaults for this distribution.
    # OPENAI_BASE_URL: LiteLLM gateway for direct LLM calls
    # BERRY_SERVICE_URL: Berry verification service with auth/budget middleware
    DEFAULT_BASE_URL = "http://20.232.57.156/v1"
    DEFAULT_BERRY_SERVICE_URL = "http://52.191.234.157:8000"

    # Load existing env defaults (if any).
    env: dict[str, str] = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                env = {str(k): str(v) for k, v in raw.items() if k and v is not None}
        except Exception:
            env = {}

    unset = bool(getattr(args, "unset", False))
    stdin = bool(getattr(args, "stdin", False))
    interactive = bool(getattr(args, "interactive", False))
    no_integrate = bool(getattr(args, "no_integrate", False))
    base_url = getattr(args, "base_url", None)
    api_key = getattr(args, "api_key", None)

    if interactive:
        print("Berry auth (guided setup)")
        print("- Stores your API key locally")
        print("- Updates global MCP configs for supported clients (Cursor, Claude Code, Codex, Gemini CLI)")
        print("")
        print("If you don't have an API key, please sign up at https://strawberry.hassana.io/")
        print("")

    if unset:
        env.pop("OPENAI_API_KEY", None)
    else:
        key = ""
        if stdin:
            key = (sys.stdin.read() or "").strip()
        else:
            key = str(api_key or "").strip()
        if not key:
            print("If you don't have an API key, please sign up at https://strawberry.hassana.io/")
            key = getpass.getpass("API key (will be saved locally): ").strip()
        if not key:
            raise SystemExit("No API key provided.")
        env["OPENAI_API_KEY"] = key

    if base_url:
        env["OPENAI_BASE_URL"] = str(base_url).strip()
    elif "OPENAI_BASE_URL" not in env or not str(env.get("OPENAI_BASE_URL") or "").strip():
        # Keep base URL pinned unless the user explicitly overrides it.
        env["OPENAI_BASE_URL"] = DEFAULT_BASE_URL

    # Set Berry service URL for verification middleware
    if "BERRY_SERVICE_URL" not in env or not str(env.get("BERRY_SERVICE_URL") or "").strip():
        env["BERRY_SERVICE_URL"] = DEFAULT_BERRY_SERVICE_URL

    # Write.
    p.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Best-effort: lock down permissions on POSIX.
    try:
        if os.name != "nt":
            p.chmod(0o600)
    except Exception:
        pass

    # IMPORTANT: After updating credentials, immediately propagate them into
    # global client config deployments (where those clients read MCP servers).
    # This is what makes a .pkg installer feel "installed" without requiring
    # a separate `berry integrate` step.
    results = []
    if not no_integrate:
        if interactive:
            print("Updating global MCP client configs...")
        try:
            results = integrate(
                clients=["cursor", "claude", "codex", "gemini"],
                name="berry",
                timeout_s=20,
                dry_run=False,
                managed=True,
                managed_only=False,
            )
        except Exception as e:
            if interactive:
                print(f"warn: saved credentials but failed to update global MCP configs: {e}")

    # Print only the path + what keys are present (never echo secrets).
    keys = sorted([k for k in env.keys()])
    print(str(p))
    print("saved_keys=" + ",".join(keys) if keys else "saved_keys=(none)")

    # Summarize integration results.
    if results:
        if interactive:
            print("\nGlobal MCP config update results:")
            for r in results:
                print(f"- {r.client}: {r.status} ({r.message})")
        else:
            # Non-interactive: only surface failures.
            for r in results:
                if r.status != "ok":
                    print(f"{r.client}: {r.status} - {r.message}")

    return 0


def cmd_support_bundle(args: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    out = Path(args.out).resolve() if args.out else None
    p = create_support_bundle(project_root=project_root, out_path=out)
    print(str(p))
    return 0


def cmd_support_issue(args: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    out = Path(args.out).resolve() if args.out else None
    bundle = create_support_bundle(project_root=project_root, out_path=out)

    print(f"Support bundle: {bundle}")
    print("")
    print("Issue template (copy/paste):")
    print("")
    print("## Summary")
    print("- What did you try to do?")
    print("- What happened instead?")
    print("")
    print("## Repro steps")
    print("1) ...")
    print("2) ...")
    print("")
    print("## Expected vs actual")
    print("- Expected: ...")
    print("- Actual: ...")
    print("")
    print("## Attachments")
    print(f"- Support bundle: {bundle}")
    return 0


def cmd_audit_export(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    export_events(out)
    print(str(out))
    return 0


def cmd_audit_prune(args: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    cfg = load_config(project_root=project_root)
    removed = prune_events(retention_days=int(cfg.audit_log_retention_days))
    print(str(removed))
    return 0


def cmd_recipes_list(_: argparse.Namespace) -> int:
    for r in builtin_recipes():
        print(f"{r.name}\t{r.title}\t{r.author}")
    return 0


def cmd_recipes_export(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    export_recipes(builtin_recipes(), out)
    print(str(out))
    return 0


def cmd_recipes_install(args: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    r = get_builtin_recipe(args.name)
    if r is None:
        raise SystemExit(f"Unknown recipe: {args.name}")
    p = install_recipe_to_project(r, project_root=project_root, force=bool(args.force))
    print(str(p))
    return 0


def cmd_recipes_import(args: argparse.Namespace) -> int:
    project_root = _find_repo_root(Path.cwd())
    src = Path(args.path).expanduser().resolve()
    p = install_recipe_file_to_project(src, project_root=project_root, force=bool(args.force))
    print(str(p))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    res = verify_blob_with_cosign(
        artifact=Path(args.artifact).resolve(),
        signature=Path(args.signature).resolve(),
        public_key=(Path(args.public_key).resolve() if args.public_key else None),
    )
    print(json.dumps({"ok": res.ok, "message": res.message}, indent=2))
    return 0 if res.ok else 2


def cmd_license_set(args: argparse.Namespace) -> int:
    ensure_berry_home()
    p = license_path()
    features = [f.strip() for f in (args.features or "").split(",") if f.strip()]
    payload = {"plan": str(args.plan), "features": features}
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(p))
    return 0


def cmd_license_show(_: argparse.Namespace) -> int:
    p = license_path()
    try:
        print(p.read_text(encoding="utf-8"), end="")
        return 0
    except FileNotFoundError:
        print("{}")
        return 0


def cmd_print_config(args: argparse.Namespace) -> int:
    profile = str(getattr(args, "profile", "science") or "science")
    specs = berry_server_specs(profile=profile, name=str(args.name))
    if args.client == "cursor":
        print(render_cursor_mcp_json(specs), end="")
    elif args.client == "codex":
        print(render_codex_config_toml(specs), end="")
    elif args.client == "claude":
        print(render_claude_mcp_json(specs), end="")
    elif args.client == "gemini":
        print(render_gemini_settings_json(specs), end="")
    else:
        raise SystemExit(f"Unknown client: {args.client}")
    return 0


def cmd_deeplink(args: argparse.Namespace) -> int:
    profile = str(getattr(args, "profile", "science") or "science")
    specs = berry_server_specs(profile=profile, name=str(args.name))
    spec = specs[0]
    if args.client == "cursor":
        print(render_cursor_deeplink(spec), end="")
    else:
        raise SystemExit(f"Unknown client: {args.client}")
    return 0


def cmd_integrate(args: argparse.Namespace) -> int:
    # Default: attempt integration for all supported clients and skip those
    # not present.
    clients = list(getattr(args, "clients", None) or [])
    if not clients:
        # Default: integrate everywhere that supports global config files.
        clients = ["cursor", "claude", "codex", "gemini"]

    managed_only = bool(getattr(args, "managed_only", False))
    managed = bool(getattr(args, "managed", False)) or managed_only

    results = integrate(
        clients=clients,
        name=str(getattr(args, "name", "berry")),
        timeout_s=int(getattr(args, "timeout", 20)),
        dry_run=bool(getattr(args, "dry_run", False)),
        managed=managed,
        managed_only=managed_only,
    )

    if bool(getattr(args, "json", False)):
        print(results_as_json(results), end="")
    else:
        for r in results:
            print(f"{r.client}: {r.status} - {r.message}")

    failed = [r for r in results if r.status == "failed"]
    return 0 if not failed else 2


def cmd_quickstart(_: argparse.Namespace) -> int:
    print("1) Install Berry so `berry` is on PATH (e.g., via pipx).")
    print("2) Set your verifier API key (recommended): `berry auth` (writes ~/.berry/mcp_env.json).")
    print("3) Optional: run `berry integrate` to register Berry globally in supported clients (Cursor, Claude Code, Codex, Gemini CLI).")
    print("4) In your repo root: run `berry init` to create repo-scoped MCP config files.")
    print("5) In your MCP client (Cursor/Codex/Claude Code/Gemini CLI), reload MCP servers for the repo.")
    print("6) Run a prompt/workflow (Search & Learn, Generate Boilerplate/Content, Inline completion guard, Greenfield prototyping, RCA Fix Agent).")
    return 0


def cmd_instructions(args: argparse.Namespace) -> int:
    name = str(args.name)
    if args.client in (None, "cursor"):
        print(
            "Cursor (repo-scoped): commit `.cursor/mcp.json` (or copy/paste via "
            "`berry print-config cursor`, or install via `berry deeplink cursor`)."
        )
    if args.client in (None, "codex"):
        print("Codex (repo-scoped): commit `.codex/config.toml` (or copy/paste via `berry print-config codex`).")
    if args.client in (None, "claude"):
        print("Claude Code (repo-scoped): commit `.mcp.json` (or copy/paste via `berry print-config claude`).")
    if args.client in (None, "gemini"):
        print("Gemini CLI (repo-scoped): commit `.gemini/settings.json` (or copy/paste via `berry print-config gemini`).")
    if args.client is None:
        print(f"Server name in configs: {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="berry")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version").set_defaults(fn=cmd_version)

    mcp = sub.add_parser("mcp", help="Run Berry MCP server (stdio by default)")
    mcp.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    mcp.add_argument(
        "--server",
        # Berry now ships a single MCP surface (classic). We intentionally keep
        # the flag for backwards compatibility with older configs that may still
        # reference "science"/"forge"; those values are treated as aliases.
        default="classic",
        help="Which MCP surface to expose (classic). Legacy values may be accepted for older configs.",
    )
    mcp.add_argument("--host", type=str, default=None)
    mcp.add_argument("--port", type=int, default=None)
    mcp.add_argument("--project-root", type=str, default=None)
    mcp.set_defaults(fn=cmd_mcp)

    init = sub.add_parser("init", help="Create repo-scoped MCP config files for Cursor/Codex/Claude/Gemini")
    init.add_argument(
        "--profile",
        # Backwards compat: older docs/configs used profiles; any value now yields classic.
        default="classic",
        help="Which MCP server(s) to install into repo configs (classic)",
    )
    init.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Explicit project root (otherwise inferred by walking up to a .git directory)",
    )
    init.add_argument("--force", action="store_true", help="Overwrite existing config files")
    init.add_argument("--strict", action="store_true", help="Also write .berry/config.json with enforce_verification=true")
    init.add_argument("--no-claude-skill", action="store_true", help="Do not write .claude/rules/berry.md (Berry skill file)")
    init.set_defaults(fn=cmd_init)

    doc = sub.add_parser("doctor", help="Run health checks / self-test")
    doc.set_defaults(fn=cmd_doctor)

    status = sub.add_parser("status", help="Show Berry config (effective)")
    status.set_defaults(fn=cmd_status)

    cfg = sub.add_parser("config", help="Edit global Berry config")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd", required=True)
    cfg_show = cfg_sub.add_parser("show")
    cfg_show.set_defaults(fn=cmd_status)
    cfg_set = cfg_sub.add_parser("set")
    cfg_set.add_argument(
        "key",
        choices=["allow_write", "enforce_verification", "diagnostics_opt_in", "audit_log_enabled", "paid_features_enabled"],
    )
    cfg_set.add_argument("value")
    cfg_set.set_defaults(fn=cmd_config_set)
    cfg_add = cfg_sub.add_parser("add-root")
    cfg_add.add_argument("path")
    cfg_add.set_defaults(fn=cmd_config_add_root)
    cfg_rm = cfg_sub.add_parser("remove-root")
    cfg_rm.add_argument("path")
    cfg_rm.set_defaults(fn=cmd_config_remove_root)

    auth = sub.add_parser("auth", help="Authentication commands")
    auth_sub = auth.add_subparsers(dest="auth_cmd")

    # `berry auth login` - browser-based auth flow (like Claude Code, Codex, Gemini CLI)
    auth_login = auth_sub.add_parser(
        "login",
        help="Authenticate via browser (recommended)",
    )
    auth_login.add_argument(
        "--device",
        action="store_true",
        help="Use device code flow (for headless/remote environments)",
    )
    auth_login.add_argument(
        "--localhost",
        action="store_true",
        help="Force localhost callback flow",
    )
    auth_login.add_argument(
        "--no-integrate",
        action="store_true",
        help="Do not update global client config files",
    )
    auth_login.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed polling information for debugging",
    )
    auth_login.set_defaults(fn=cmd_auth_login)

    # `berry auth set` - direct API key entry (backwards compatible with old `berry auth <key>`)
    auth_set = auth_sub.add_parser(
        "set",
        help="Set API key directly (for CI/CD)",
    )
    auth_set.add_argument(
        "api_key",
        nargs="?",
        default=None,
        help="API key (optional; if omitted, you'll be prompted)",
    )
    auth_set.add_argument("--stdin", action="store_true", help="Read API key from stdin")
    auth_set.add_argument("--base-url", default=None, help="Optional OpenAI-compatible base URL")
    auth_set.add_argument(
        "--no-integrate",
        action="store_true",
        help="Do not update global client config files",
    )
    auth_set.set_defaults(fn=cmd_auth)

    # `berry auth status` - show current auth status
    auth_status = auth_sub.add_parser(
        "status",
        help="Show current authentication status",
    )
    auth_status.set_defaults(fn=cmd_auth_status)

    # `berry auth logout` - remove saved credentials
    auth_logout = auth_sub.add_parser(
        "logout",
        help="Remove saved credentials",
    )
    auth_logout.set_defaults(fn=cmd_auth_logout)

    # Default: if no subcommand, show help or run legacy behavior
    auth.set_defaults(fn=cmd_auth_default)

    sup = sub.add_parser("support", help="Support tooling")
    sup_sub = sup.add_subparsers(dest="support_cmd", required=True)
    bundle = sup_sub.add_parser("bundle", help="Create a redacted support bundle zip")
    bundle.add_argument("--out", type=str, default=None, help="Output path (optional)")
    bundle.set_defaults(fn=cmd_support_bundle)
    issue = sup_sub.add_parser("issue", help="Create a support bundle and print an issue template")
    issue.add_argument("--out", type=str, default=None, help="Output path (optional)")
    issue.set_defaults(fn=cmd_support_issue)

    audit = sub.add_parser("audit", help="Audit log tooling")
    audit_sub = audit.add_subparsers(dest="audit_cmd", required=True)
    audit_export = audit_sub.add_parser("export", help="Export audit log as JSON")
    audit_export.add_argument("--out", type=str, required=True)
    audit_export.set_defaults(fn=cmd_audit_export)
    audit_prune = audit_sub.add_parser("prune", help="Prune audit log based on retention window")
    audit_prune.set_defaults(fn=cmd_audit_prune)

    recipes = sub.add_parser("recipes", help="Recipes system (public workflow packs)")
    recipes_sub = recipes.add_subparsers(dest="recipes_cmd", required=True)
    recipes_list = recipes_sub.add_parser("list")
    recipes_list.set_defaults(fn=cmd_recipes_list)
    recipes_export = recipes_sub.add_parser("export")
    recipes_export.add_argument("--out", type=str, required=True)
    recipes_export.set_defaults(fn=cmd_recipes_export)
    recipes_import = recipes_sub.add_parser("import", help="Import a recipe JSON file")
    recipes_import.add_argument("path")
    recipes_import.add_argument("--force", action="store_true")
    recipes_import.set_defaults(fn=cmd_recipes_import)
    recipes_install = recipes_sub.add_parser("install")
    recipes_install.add_argument("name")
    recipes_install.add_argument("--force", action="store_true")
    recipes_install.set_defaults(fn=cmd_recipes_install)

    lic = sub.add_parser("license", help="License/entitlements (paid layer scaffolding)")
    lic_sub = lic.add_subparsers(dest="license_cmd", required=True)
    lic_set = lic_sub.add_parser("set")
    lic_set.add_argument("--plan", default="pro")
    lic_set.add_argument("--features", default="")
    lic_set.set_defaults(fn=cmd_license_set)
    lic_show = lic_sub.add_parser("show")
    lic_show.set_defaults(fn=cmd_license_show)

    quick = sub.add_parser("quickstart", help="Print the fastest path to first value")
    quick.set_defaults(fn=cmd_quickstart)

    inst = sub.add_parser("instructions", help="Per-client setup copy/paste guidance")
    inst.add_argument("--client", choices=["cursor", "codex", "claude", "gemini"], default=None)
    inst.add_argument("--name", default="berry")
    inst.set_defaults(fn=cmd_instructions)

    pc = sub.add_parser("print-config", help="Print per-client config for copy/paste")
    pc.add_argument("client", choices=["cursor", "codex", "claude", "gemini"])
    pc.add_argument("--name", default="berry")
    pc.add_argument(
        "--profile",
        default="classic",
        help="Which MCP servers to render (classic). Legacy values may be accepted for older configs.",
    )
    pc.set_defaults(fn=cmd_print_config)

    dl = sub.add_parser("deeplink", help="Print a client install deeplink")
    dl.add_argument("client", choices=["cursor"])
    dl.add_argument("--name", default="berry")
    dl.add_argument(
        "--profile",
        default="classic",
        help="Which MCP server to deeplink (classic)",
    )
    dl.set_defaults(fn=cmd_deeplink)

    verify = sub.add_parser("verify", help="Verify a signed artifact (integrity verification)")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--signature", required=True)
    verify.add_argument("--public-key", default=None)
    verify.set_defaults(fn=cmd_verify)

    integ = sub.add_parser(
        "integrate",
        help="Register Berry with supported clients globally (best-effort)",
    )
    integ.add_argument(
        "--client",
        action="append",
        dest="clients",
        choices=["cursor", "claude", "codex", "gemini"],
        default=None,
        help="Client to integrate (repeatable). Defaults to all supported clients.",
    )
    integ.add_argument("--name", default="berry", help="MCP server name to register")
    integ.add_argument("--timeout", type=int, default=20, help="Per-client command timeout in seconds")
    integ.add_argument("--dry-run", action="store_true", help="Print what would be done without modifying anything")
    integ.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    # Flags reserved for installer / future expansion.
    integ.add_argument("--global", action="store_true", help="Register globally (default behavior)")
    integ.add_argument("--noninteractive", action="store_true", help="Do not prompt (reserved)")
    integ.add_argument(
        "--managed",
        action="store_true",
        help="Also write system-managed config files where supported (requires admin rights).",
    )
    integ.add_argument(
        "--managed-only",
        dest="managed_only",
        action="store_true",
        help="Only write system-managed config files (implies --managed).",
    )
    integ.set_defaults(fn=cmd_integrate)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
