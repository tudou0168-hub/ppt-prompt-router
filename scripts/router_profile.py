"""Runtime-only Router profile compilation.

The released suite excludes the development ``install.py``. Keeping this
small module separate lets ``route.py`` compile the director profile without
exposing a second installer entrypoint.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


SUPPORTED_INDEX_SCHEMAS = {"1.0", "2.0"}
EXPECTED_CATEGORY_COUNTS = {
    "01_workplace_office": 7,
    "02_student_campus": 4,
    "03_promotion_showcase": 4,
    "04_personal_general": 4,
    "05_professional_scenarios": 6,
}
PROFILE_FIELDS = (
    "communication_job", "audience_register", "required_story_beats", "required_content_fields",
    "title_voice", "opening_task", "closing_task", "visual_posture", "evidence_standard", "key_failure_modes",
)
PROFILE_LIST_FIELDS = {"required_story_beats", "required_content_fields", "key_failure_modes"}
PROFILE_DEFAULTS: dict[str, Any] = {
    "communication_job": "帮助受众理解材料重点，并形成与场景匹配的下一步判断或行动。",
    "audience_register": "专业、清晰、面向真实决策或学习场景。",
    "required_story_beats": ["背景与问题", "核心判断", "路径或行动"],
    "required_content_fields": [],
    "title_voice": "面向受众的结论式标题。",
    "opening_task": "建立主题、受众关切和本次材料要回答的问题。",
    "closing_task": "收束核心结论并明确下一步。",
    "visual_posture": "专业、克制，以内容关系为中心。",
    "evidence_standard": "事实、数据、案例和承诺必须来自材料或明确标注边界。",
    "key_failure_modes": ["机械拆页", "重复卡片化", "把推断写成事实"],
}
FOCUSED_PROFILE_IDS = {"government_strategy", "business_bid", "data_report", "classroom_lesson", "brand_presentation", "fundraising_bp"}


class PackageError(RuntimeError):
    pass


def load_index(root: Path) -> dict[str, Any]:
    path = root / "prompt-index.json"
    if not path.is_file():
        raise PackageError(f"missing prompt-index.json: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError(f"invalid prompt-index.json: {exc}") from exc


def prompt_body(root: Path, entry: dict[str, Any]) -> str:
    path = root / Path(str(entry["file"]))
    if not path.is_file():
        raise PackageError(f"missing prompt file: {entry['file']}")
    return path.read_text(encoding="utf-8")


def _profile_value(value: str, field: str) -> Any:
    return [item.strip() for item in value.split("|") if item.strip()] if field in PROFILE_LIST_FIELDS else value.strip()


def profile_fields(root: Path, entry: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    in_block = False
    explicit: dict[str, Any] = {}
    for line in prompt_body(root, entry).splitlines():
        if line.strip() == "## Router Profile":
            in_block = True
            continue
        if in_block and line.startswith("## "):
            break
        if not in_block or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lstrip("-").strip()
        if key in PROFILE_FIELDS and value.strip():
            explicit[key] = _profile_value(value, key)
    return ({key: explicit.get(key, PROFILE_DEFAULTS[key]) for key in PROFILE_FIELDS}, set(explicit))


def prompt_entries(index: dict[str, Any]) -> list[dict[str, Any]]:
    prompts = index.get("prompts")
    if isinstance(prompts, list):
        return [dict(entry) for entry in prompts]
    if isinstance(prompts, dict):
        return [{"id": prompt_id, **value} for prompt_id, value in prompts.items() if isinstance(value, dict)]
    raise PackageError("prompt-index prompts must be a list or object")


def validate_prompt_index(index: dict[str, Any]) -> list[dict[str, Any]]:
    if str(index.get("schema_version", "1.0")) not in SUPPORTED_INDEX_SCHEMAS:
        raise PackageError("prompt-index schema_version must be 1.0 or 2.0")
    entries = prompt_entries(index)
    if len(entries) != 25:
        raise PackageError("prompt-index must contain exactly 25 prompts")
    ids, files = set(), set()
    categories = {key: 0 for key in EXPECTED_CATEGORY_COUNTS}
    for entry in entries:
        for key in ("id", "name_zh", "category", "file", "use_when", "strong_signals", "avoid_when", "conflicts_with"):
            if key not in entry or not entry[key]:
                raise PackageError(f"prompt-index entry missing {key}")
        if entry["id"] in ids or entry["file"] in files:
            raise PackageError("prompt-index contains duplicate id or file")
        if entry["category"] not in categories:
            raise PackageError(f"unexpected category: {entry['category']}")
        ids.add(entry["id"]); files.add(entry["file"]); categories[entry["category"]] += 1
    if categories != EXPECTED_CATEGORY_COUNTS:
        raise PackageError(f"category counts mismatch: {categories}")
    return entries


def lint_profiles(root: Path, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        fields, explicit = profile_fields(root, entry)
        if entry["id"] in FOCUSED_PROFILE_IDS and explicit != set(PROFILE_FIELDS):
            missing = sorted(set(PROFILE_FIELDS) - explicit)
            raise PackageError(f"focused profile {entry['id']} missing fields: {', '.join(missing)}")
        if len(fields["key_failure_modes"]) > 3:
            raise PackageError(f"profile {entry['id']} has more than 3 key_failure_modes")
        if not all(fields[field] for field in PROFILE_FIELDS if field != "required_content_fields"):
            raise PackageError(f"profile {entry['id']} has an empty compiled field")


def compile_director_profile(root: Path, entry: dict[str, Any]) -> str:
    fields, _ = profile_fields(root, entry)
    lint_profiles(root, [entry])
    protocol = root / "prompts" / "_shared" / "director_protocol.md"
    if not protocol.is_file():
        raise PackageError(f"missing shared director protocol: {protocol}")
    lines = ["# Director Profile", "", f"- profile_id: {entry['id']}", f"- validation_status: {entry.get('validation_status', 'experimental')}", "", "## Universal Director Protocol", "", protocol.read_text(encoding="utf-8").strip(), "", "## Scene Profile", ""]
    for field in PROFILE_FIELDS:
        value = fields[field]
        lines.append(f"- {field}: {' | '.join(value) if field in PROFILE_LIST_FIELDS else value}")
    if entry["id"] not in FOCUSED_PROFILE_IDS:
        lines.extend(["", "## Experimental Source Guidance", "", prompt_body(root, entry).strip()])
    return "\n".join(lines).rstrip() + "\n"


def run_tool(args: list[str], *, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    try:
        result = subprocess.run(args, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    except FileNotFoundError as exc:
        raise PackageError(f"missing executable: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise PackageError((exc.stderr or exc.stdout or "").strip() or f"command failed: {' '.join(args)}") from exc
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.stdout.strip()
