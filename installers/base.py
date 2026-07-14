"""Host detection helpers for Router registration discovery."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class HostError(RuntimeError):
    pass


def expand_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve(strict=False)


def process_context() -> str:
    parts = [sys.argv[0], os.environ.get("TERM_PROGRAM", ""), os.environ.get("AGENT_HOST", "")]
    try:
        parts.append(subprocess.check_output(["ps", "-p", str(os.getppid()), "-o", "command="], text=True, stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return " ".join(parts).lower()


class HostAdapter:
    host_id = "generic"

    def __init__(self, *, skills_dir: Path | None = None):
        self.explicit_skills_dir = expand_path(skills_dir) if skills_dir else None

    def detection_score(self) -> int:
        return 0

    def detect(self) -> bool:
        return self.detection_score() > 0

    def candidate_skills_dirs(self) -> list[Path]:
        values = [Path.home() / ".agents" / "skills", Path.cwd() / "skills"]
        for key in ("AGENT_SKILLS_DIR", "SKILLS_DIR"):
            if os.environ.get(key):
                values.insert(0, expand_path(os.environ[key]))
        return values

    def discover_skills_dirs(self) -> list[Path]:
        paths = [self.explicit_skills_dir] if self.explicit_skills_dir else []
        for candidate in self.candidate_skills_dirs():
            path = expand_path(candidate)
            if path.is_dir() and path not in paths:
                paths.append(path)
        return paths
