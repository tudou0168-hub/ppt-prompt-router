#!/usr/bin/env python3
"""Reject direct internal CLI use for Router-managed projects."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROUTER_MARKER = "PPT_DIRECTOR_INTERNAL_CALL"
BLOCKED_EXIT = 3


def managed_project(path: str | Path) -> Path | None:
    candidate = Path(path).expanduser().resolve(strict=False)
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / "analysis" / "director_contract.json").is_file():
            return parent
    return None


def _candidate_paths(argv: list[str]) -> list[Path]:
    paths = [Path.cwd()]
    for value in argv:
        if not value or value.startswith("-"):
            continue
        candidate = Path(value).expanduser()
        if candidate.exists():
            paths.append(candidate)
    return paths


def enforce_cli(script_file: str | Path, argv: list[str] | None = None) -> None:
    """Fail before business logic when an internal CLI targets a managed project."""
    if os.environ.get(ROUTER_MARKER):
        return
    for candidate in _candidate_paths(list(sys.argv[1:] if argv is None else argv)):
        project = managed_project(candidate)
        if project is None:
            continue
        print(
            "PPT Director managed project: use scripts/route.py instead of an internal "
            f"PPT Master CLI ({Path(script_file).name}); project={project}",
            file=sys.stderr,
        )
        raise SystemExit(BLOCKED_EXIT)
