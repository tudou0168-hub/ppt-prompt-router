"""Adapter for unknown SKILL.md-compatible hosts."""

from __future__ import annotations

import os
from pathlib import Path

from .base import HostAdapter, HostError, expand_path


class GenericAdapter(HostAdapter):
    host_id = "generic"

    def detection_score(self) -> int:
        return 0

    def candidate_skills_dirs(self) -> list[Path]:
        values = []
        for key in ("AGENT_SKILLS_DIR", "SKILLS_DIR"):
            value = os.environ.get(key)
            if value:
                values.append(expand_path(value))
        return values

    def default_skills_dir(self) -> Path:
        if not self.explicit_skills_dir:
            raise HostError("generic 模式必须使用 --skills-dir 或 AGENT_SKILLS_DIR 明确指定技能目录。")
        return self.explicit_skills_dir
