"""Host adapters for Router installation discovery."""

from .base import HostError
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .generic import GenericAdapter
from .hermes import HermesAdapter
from .openclaw import OpenClawAdapter

ADAPTERS = {
    "claude-code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "openclaw": OpenClawAdapter,
    "hermes": HermesAdapter,
    "generic": GenericAdapter,
}


def host_choices() -> tuple[str, ...]:
    return ("auto", *ADAPTERS.keys())


def get_adapter(host: str, *, skills_dir=None):
    if host == "auto":
        scores = [(adapter_cls(skills_dir=skills_dir).detection_score(), adapter_cls) for adapter_cls in ADAPTERS.values() if adapter_cls is not GenericAdapter]
        scores.sort(key=lambda item: item[0], reverse=True)
        if not scores or scores[0][0] <= 0:
            if skills_dir is None:
                raise HostError("无法准确识别当前 Agent；请使用 --host 或 --skills-dir 明确指定。")
            return GenericAdapter(skills_dir=skills_dir)
        if len(scores) > 1 and scores[0][0] == scores[1][0] and scores[0][0] >= 40:
            raise HostError("检测到多个同等可能的 Agent；请使用 --host 明确指定。")
        return scores[0][1](skills_dir=skills_dir)
    if host not in ADAPTERS:
        raise HostError(f"unsupported host: {host}")
    return ADAPTERS[host](skills_dir=skills_dir)
