"""Hermes adapter; all host-specific discovery stays here."""

import os
from pathlib import Path

from .base import HostAdapter, expand_path, process_context


class HermesAdapter(HostAdapter):
    host_id = "hermes"

    def detection_score(self) -> int:
        if os.environ.get("HERMES_HOME") or os.environ.get("HERMES_AGENT"):
            return 80
        if "hermes" in process_context():
            return 70
        if (Path.cwd() / ".hermes").is_dir():
            return 40
        return 10 if (Path.home() / ".hermes").is_dir() else 0



    def canonical_skills_dir(self, scope: str = "user") -> Path:
        if scope == "workspace":
            raise HostError("Hermes 不支持 workspace 技能安装；请使用 user 或 --skills-dir。")
        return expand_path(Path.home() / ".hermes" / "skills")

    def candidate_skills_dirs(self) -> list[Path]:
        root = expand_path(os.environ["HERMES_HOME"]) if os.environ.get("HERMES_HOME") else Path.home() / ".hermes"
        return [root / "skills", Path.cwd() / ".hermes" / "skills", *super().candidate_skills_dirs()]
