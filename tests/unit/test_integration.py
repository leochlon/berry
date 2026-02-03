from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from berry.clients import berry_server_spec
from berry.integration import integrate_with_claude, integrate_with_codex


def _write_dummy_cli(path: Path, log: Path, exit_code: int = 0) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
echo "$0 $*" >> "{log}"
exit {code}
""".format(log=str(log), code=int(exit_code)),
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_integrate_with_claude_skips_when_missing(tmp_path: Path, monkeypatch):
    # The integration now writes to ~/.claude.json file first, so it returns "ok"
    # even when the CLI is not found (file-based integration is primary)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))  # Use tmp_path as home to avoid writing to real home
    res = integrate_with_claude(spec=berry_server_spec(name="berry"))
    assert res.status == "ok"
    assert "claude CLI not found" in res.message


@pytest.mark.skipif(sys.platform == "win32", reason="Bash-based dummy CLI does not work on Windows")
def test_integrate_with_claude_invokes_cli(tmp_path: Path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "claude.log"
    _write_dummy_cli(bindir / "claude", log, exit_code=0)

    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("HOME", str(tmp_path))  # Use tmp_path as home
    res = integrate_with_claude(spec=berry_server_spec(name="berry"))
    assert res.status == "ok"
    text = log.read_text(encoding="utf-8")
    assert "claude mcp add berry" in text
    assert " -- " in text
    after = text.split(" -- ", 1)[1]
    assert "berry" in after
    # Berry now uses "classic" instead of "science"
    assert after.strip().endswith("classic")


@pytest.mark.skipif(sys.platform == "win32", reason="Bash-based dummy CLI does not work on Windows")
def test_integrate_with_codex_invokes_cli(tmp_path: Path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "codex.log"
    _write_dummy_cli(bindir / "codex", log, exit_code=0)

    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("HOME", str(tmp_path))  # Use tmp_path as home
    res = integrate_with_codex(spec=berry_server_spec(name="berry"))
    assert res.status == "ok"
    text = log.read_text(encoding="utf-8")
    assert "codex mcp add berry" in text
    assert " -- " in text
    after = text.split(" -- ", 1)[1]
    assert "berry" in after
    # Berry now uses "classic" instead of "science"
    assert after.strip().endswith("classic")


@pytest.mark.skipif(sys.platform == "win32", reason="Bash-based dummy CLI does not work on Windows")
def test_integrate_with_claude_nonzero_is_failure(tmp_path: Path, monkeypatch):
    # Even with non-zero CLI exit, the file-based integration succeeds,
    # so the overall status is "ok" with a note about CLI failure
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "claude.log"
    _write_dummy_cli(bindir / "claude", log, exit_code=7)

    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("HOME", str(tmp_path))  # Use tmp_path as home
    res = integrate_with_claude(spec=berry_server_spec(name="berry"), timeout_s=5)
    # File integration succeeds, so status is "ok" even if CLI fails
    assert res.status == "ok"
    assert "cli failed" in res.message.lower() or "non-fatal" in res.message.lower()