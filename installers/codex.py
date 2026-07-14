"""Codex adapter; all host-specific discovery stays here."""

import os
from pathlib import Path

from .base import HostAdapter, expand_path, process_context


class CodexAdapter(HostAdapter):
    host_id = "codex"

    def detection_score(self) -> int:
        if os.environ.get("CODEX_HOME") or os.environ.get("CODEX_THREAD_ID"):
            return 80
        if "codex" in process_context():
            return 70
        if (Path.cwd() / ".codex").is_dir():
            return 40
        return 10 if (Path.home() / ".codex").is_dir() else 0

    def detection_reasons(self) -> list[str]:
        return ["Codex environment/process/config evidence"] if self.detection_score() else []

    def canonical_skills_dir(self, scope: str = "user") -> Path:
        # New installs use the generic Agent skills root; CODEX_HOME is discovery-only.
        return expand_path(Path.cwd() / ".agents" / "skills" if scope == "workspace" else Path.home() / ".agents" / "skills")

    def candidate_skills_dirs(self) -> list[Path]:
        root = expand_path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") else Path.home() / ".codex"
        return [Path.home() / ".agents" / "skills", root / "skills", Path.cwd() / ".codex" / "skills", *super().candidate_skills_dirs()]
