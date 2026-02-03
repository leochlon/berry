from __future__ import annotations

import json
import os
from typing import Dict

from .paths import mcp_env_path


def load_mcp_env() -> Dict[str, str]:
    """Load default env vars to apply when launching Berry as an MCP server.

    Precedence (last wins):
    1) File: ~/.berry/mcp_env.json (or $BERRY_HOME/mcp_env.json)
    2) Env:  BERRY_MCP_ENV_JSON (JSON object string)

    This is intentionally separate from Berry's main config schema.
    """

    env: Dict[str, str] = {}

    # File-based defaults.
    try:
        p = mcp_env_path()
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    kk = str(k).strip()
                    if not kk:
                        continue
                    if v is None:
                        continue
                    env[kk] = str(v)
    except Exception:
        # Fail open: env injection is optional.
        pass

    # Explicit env override.
    try:
        j = os.environ.get("BERRY_MCP_ENV_JSON")
        if j:
            raw = json.loads(j)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    kk = str(k).strip()
                    if not kk:
                        continue
                    if v is None:
                        continue
                    env[kk] = str(v)
    except Exception:
        pass

    return env
