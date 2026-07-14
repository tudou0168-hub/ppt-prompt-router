"""OpenClaw adapter; all host-specific discovery stays here."""

import os
from pathlib import Path

from .base import HostAdapter, expand_path, process_context


class OpenClawAdapter(HostAdapter):
    host_id = "openclaw"

    def detection_score(self) -> int:
        if os.environ.get("OPENCLAW_HOME") or os.environ.get("OPENCLAW_AGENT"):
            return 80
        if "openclaw" in process_context():
            return 70
        if (Path.cwd() / ".openclaw").is_dir():
            return 40
        return 10 if (Path.home() / ".openclaw").is_dir() else 0

    def detection_reasons(self) -> list[str]:
        return ["OpenClaw environment/process/config evidence"] if self.detection_score() else []

    def candidate_skills_dirs(self) -> list[Path]:
        root = expand_path(os.environ["OPENCLAW_HOME"]) if os.environ.get("OPENCLAW_HOME") else Path.home() / ".openclaw"
        return [root / "skills", Path.cwd() / "skills", Path.home() / ".agents" / "skills", *super().candidate_skills_dirs()]
