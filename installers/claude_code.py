"""Claude Code adapter; all host-specific discovery stays here."""

import os
from pathlib import Path

from .base import HostAdapter, expand_path, process_context


class ClaudeCodeAdapter(HostAdapter):
    host_id = "claude-code"

    def detection_score(self) -> int:
        if os.environ.get("CLAUDE_CODE") or os.environ.get("CLAUDE_CODE_VERSION"):
            return 80
        if "claude" in process_context():
            return 70
        if (Path.cwd() / ".claude").is_dir():
            return 40
        return 10 if (Path.home() / ".claude").is_dir() else 0

    def detection_reasons(self) -> list[str]:
        return ["Claude Code environment/process/config evidence"] if self.detection_score() else []

    def canonical_skills_dir(self, scope: str = "user") -> Path:
        return expand_path((Path.cwd() / ".claude" / "skills") if scope == "workspace" else (Path.home() / ".claude" / "skills"))

    def candidate_skills_dirs(self) -> list[Path]:
        values = []
        for key in ("CLAUDE_CODE_SKILLS_DIR", "CLAUDE_SKILLS_DIR"):
            if os.environ.get(key):
                values.append(expand_path(os.environ[key]))
        values.extend([Path.home() / ".claude" / "skills", Path.cwd() / ".claude" / "skills"])
        values.extend(super().candidate_skills_dirs())
        return values
