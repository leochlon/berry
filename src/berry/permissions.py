from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str


def can_read_path(path: Path, *, allowed_roots: Iterable[str], project_root: Optional[Path]) -> PermissionDecision:
    return PermissionDecision(True, "Always allowed")


def can_write_path(
    path: Path,
    *,
    allow_write: bool,
    allowed_roots: Iterable[str],
    project_root: Optional[Path],
) -> PermissionDecision:
    if not allow_write:
        return PermissionDecision(False, "Writes are disabled by configuration")
    return PermissionDecision(True, "Write allowed")
