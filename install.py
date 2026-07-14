#!/usr/bin/env python3
"""Cross-platform installer for ppt-prompt-router itself."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import hashlib
from pathlib import Path
from typing import Any

from installers import get_adapter, host_choices
from installers.base import HostError


PACKAGE_NAME = "ppt-prompt-router"
REQUIRED_ROOT_FILES = (
    "SKILL.md", "README.md", "VERSION", "prompt-index.json", "install.py", "CHANGELOG.md", ".gitignore",
)
REQUIRED_ROOT_DIRS = ("prompts", "installers", "scripts", "integrations", "docs", "tests", ".github")
SUPPORTED_INDEX_SCHEMAS = {"1.0", "2.0"}
EXPECTED_CATEGORY_COUNTS = {
    "01_workplace_office": 7,
    "02_student_campus": 4,
    "03_promotion_showcase": 4,
    "04_personal_general": 4,
    "05_professional_scenarios": 6,
}
PROFILE_FIELDS = (
    "communication_job",
    "audience_register",
    "required_story_beats",
    "required_content_fields",
    "title_voice",
    "opening_task",
    "closing_task",
    "visual_posture",
    "evidence_standard",
    "key_failure_modes",
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
FOCUSED_PROFILE_IDS = {
    "government_strategy",
    "business_bid",
    "data_report",
    "classroom_lesson",
    "brand_presentation",
    "fundraising_bp",
}


class PackageError(RuntimeError):
    pass


def expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve(strict=False)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_root(source_root: Path | None = None) -> Path:
    return (source_root or Path(__file__).resolve().parent).resolve(strict=False)


def destination_root(target_dir: Path) -> Path:
    return target_dir / PACKAGE_NAME


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def source_target_conflict(source_root: Path, target_dir: Path, dest_root: Path) -> bool:
    source = source_root.resolve(strict=False)
    return any(
        source == path.resolve(strict=False)
        or _is_relative_to(source, path.resolve(strict=False))
        or _is_relative_to(path.resolve(strict=False), source)
        for path in (target_dir, dest_root)
    )


def load_index(root: Path) -> dict:
    path = root / "prompt-index.json"
    if not path.is_file():
        raise PackageError(f"missing prompt-index.json: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError(f"invalid prompt-index.json: {exc}") from exc


def prompt_body(root: Path, entry: dict) -> str:
    prompt_path = root / Path(entry["file"])
    if not prompt_path.is_file():
        raise PackageError(f"missing prompt file: {entry['file']}")
    return prompt_path.read_text(encoding="utf-8")


def _profile_value(value: str, field: str) -> Any:
    if field in PROFILE_LIST_FIELDS:
        return [item.strip() for item in value.split("|") if item.strip()]
    return value.strip()


def profile_fields(root: Path, entry: dict) -> tuple[dict[str, Any], set[str]]:
    """Read the lightweight Router Profile block and fill public defaults."""
    text = prompt_body(root, entry)
    lines = text.splitlines()
    in_block = False
    explicit: dict[str, Any] = {}
    for line in lines:
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
    fields = {key: explicit.get(key, PROFILE_DEFAULTS[key]) for key in PROFILE_FIELDS}
    return fields, set(explicit)


def lint_profiles(root: Path, entries: list[dict]) -> None:
    for entry in entries:
        fields, explicit = profile_fields(root, entry)
        if entry["id"] in FOCUSED_PROFILE_IDS and explicit != set(PROFILE_FIELDS):
            missing = sorted(set(PROFILE_FIELDS) - explicit)
            raise PackageError(f"focused profile {entry['id']} missing fields: {', '.join(missing)}")
        if len(fields["key_failure_modes"]) > 3:
            raise PackageError(f"profile {entry['id']} has more than 3 key_failure_modes")
        required_nonempty = [field for field in PROFILE_FIELDS if field != "required_content_fields"]
        if not all(fields[field] for field in required_nonempty):
            raise PackageError(f"profile {entry['id']} has an empty compiled field")


def compile_director_profile(root: Path, entry: dict) -> str:
    """Compile shared direction plus one scenario profile into the handoff file."""
    fields, explicit = profile_fields(root, entry)
    lint_profiles(root, [entry])
    protocol_path = root / "prompts" / "_shared" / "director_protocol.md"
    if not protocol_path.is_file():
        raise PackageError(f"missing shared director protocol: {protocol_path}")

    lines = [
        "# Director Profile",
        "",
        f"- profile_id: {entry['id']}",
        f"- validation_status: {entry.get('validation_status', 'experimental')}",
        "",
        "## Universal Director Protocol",
        "",
        protocol_path.read_text(encoding="utf-8").strip(),
        "",
        "## Scene Profile",
        "",
    ]
    for field in PROFILE_FIELDS:
        value = fields[field]
        rendered = " | ".join(value) if field in PROFILE_LIST_FIELDS else value
        lines.append(f"- {field}: {rendered}")
    if entry["id"] not in FOCUSED_PROFILE_IDS:
        lines.extend([
            "",
            "## Experimental Source Guidance",
            "",
            prompt_body(root, entry).strip(),
        ])
    return "\n".join(lines).rstrip() + "\n"


def prompt_entries(index: dict) -> list[dict]:
    prompts = index.get("prompts")
    if isinstance(prompts, list):
        return [dict(entry) for entry in prompts]
    if isinstance(prompts, dict):
        return [{"id": prompt_id, **value} for prompt_id, value in prompts.items() if isinstance(value, dict)]
    raise PackageError("prompt-index prompts must be a list or object")


def validate_prompt_index(index: dict) -> list[dict]:
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
        ids.add(entry["id"])
        files.add(entry["file"])
        categories[entry["category"]] += 1
    if categories != EXPECTED_CATEGORY_COUNTS:
        raise PackageError(f"category counts mismatch: {categories}")
    return entries


def select_prompt(index: dict, task: str, *, prompt_id: str | None = None) -> dict | None:
    """Return one matching prompt, or None when the task is genuinely unclear."""
    entries = validate_prompt_index(index)
    if prompt_id:
        return next((entry for entry in entries if entry["id"] == prompt_id), None)
    text = task.lower()
    ranked: list[tuple[int, str, dict]] = []
    for entry in entries:
        terms = [entry["id"], entry["name_zh"], *entry.get("required_signals", []), *entry.get("strong_signals", []), *entry.get("supporting_signals", [])]
        score = sum(1 for term in terms if str(term).lower() in text)
        if score:
            ranked.append((score, entry["id"], entry))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][2]


def copy_package_tree(source_root: Path, staging_root: Path) -> None:
    entries = validate_prompt_index(load_index(source_root))
    staging_root.mkdir(parents=True, exist_ok=False)
    for name in REQUIRED_ROOT_FILES:
        source = source_root / name
        if not source.is_file():
            raise PackageError(f"missing required file: {name}")
        shutil.copy2(source, staging_root / name)

    for entry in entries:
        relative = Path(entry["file"])
        source = source_root / relative
        destination = staging_root / relative
        if not source.is_file():
            raise PackageError(f"missing prompt file: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shared_protocol = source_root / "prompts" / "_shared" / "director_protocol.md"
    if not shared_protocol.is_file():
        raise PackageError("missing prompts/_shared/director_protocol.md")
    shared_destination = staging_root / "prompts" / "_shared"
    shared_destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(shared_protocol, shared_destination / shared_protocol.name)

    adapters = source_root / "installers"
    if not adapters.is_dir():
        raise PackageError("missing host adapters directory")
    shutil.copytree(
        adapters,
        staging_root / "installers",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".git"),
    )
    for name in ("scripts", "integrations", "docs", "tests", ".github"):
        source = source_root / name
        if not source.is_dir():
            raise PackageError(f"missing package directory: {name}")
        shutil.copytree(
            source,
            staging_root / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".git", "projects", "*.pptx", "*.docx", "*.pdf"),
        )


def validate_package_root(root: Path) -> None:
    root = root.resolve(strict=False)
    if not root.is_dir():
        raise PackageError(f"package root not found: {root}")
    expected_top = set(REQUIRED_ROOT_FILES) | set(REQUIRED_ROOT_DIRS)
    actual_top = {path.name for path in root.iterdir()}
    allowed_local_extras = {"projects", ".DS_Store", "__pycache__", "COMMERCIAL_LICENSE.md", "THIRD_PARTY_NOTICES.md"}
    unexpected = actual_top - expected_top - allowed_local_extras
    if expected_top - actual_top or unexpected:
        raise PackageError(f"top-level structure mismatch; missing={sorted(expected_top - actual_top)}, extra={sorted(unexpected)}")
    for name in REQUIRED_ROOT_FILES:
        path = root / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            raise PackageError(f"missing or empty root file: {name}")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if f"version: {version}" not in (root / "SKILL.md").read_text(encoding="utf-8"):
        raise PackageError("VERSION and SKILL.md frontmatter version mismatch")

    entries = validate_prompt_index(load_index(root))
    lint_profiles(root, entries)
    expected_paths = {entry["file"] for entry in entries}
    actual_paths = {
        str(path.relative_to(root).as_posix())
        for path in (root / "prompts").rglob("*.md")
        if "_shared" not in path.relative_to(root / "prompts").parts
    }
    if actual_paths != expected_paths:
        raise PackageError("prompt tree does not match prompt-index.json")
    for relative in expected_paths:
        if not (root / relative).read_text(encoding="utf-8").strip():
            raise PackageError(f"empty prompt file: {relative}")
    if not (root / "prompts" / "_shared" / "director_protocol.md").is_file():
        raise PackageError("missing shared director protocol")
    for name in ("__init__.py", "base.py", "claude_code.py", "codex.py", "openclaw.py", "hermes.py", "generic.py"):
        if not (root / "installers" / name).is_file():
            raise PackageError(f"missing host adapter: installers/{name}")
    if not (root / "scripts" / "route.py").is_file():
        raise PackageError("missing Router 2.1 entrypoint: scripts/route.py")
    manifest = root / "integrations" / "ppt-master" / "manifest.json"
    lock = root / "integrations" / "ppt-master" / "upstream.lock"
    if not manifest.is_file() or not lock.is_file():
        raise PackageError("missing PPT Master integration manifest or upstream lock")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError(f"invalid PPT Master manifest: {exc}") from exc
    if not isinstance(payload.get("files"), list) or not payload["files"]:
        raise PackageError("PPT Master manifest must contain overlay files")
    for item in payload["files"]:
        relative = item.get("path")
        if not isinstance(relative, str) or not relative.startswith("skills/ppt-master/"):
            raise PackageError("invalid PPT Master overlay path")
        overlay = root / "integrations" / "ppt-master" / "overlay" / relative
        if not overlay.is_file():
            raise PackageError(f"missing overlay file: {relative}")
        if item.get("overlay_hash") != sha256_file(overlay):
            raise PackageError(f"overlay hash mismatch: {relative}")


def find_ppt_master_root(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(expand_path(explicit))
    if os.environ.get("PPT_MASTER_ROOT"):
        candidates.append(expand_path(os.environ["PPT_MASTER_ROOT"]))
    candidates.extend([
        Path.home() / "Documents" / "ppt-master",
        package_root().parent / "ppt-master",
        Path.cwd() / "ppt-master",
    ])
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve(strict=False)
        if candidate in seen:
            continue
        seen.add(candidate)
        script = candidate / "skills" / "ppt-master" / "scripts" / "project_manager.py"
        if script.is_file():
            return candidate
    raise PackageError("ppt-master not found; pass --ppt-master-root or set PPT_MASTER_ROOT")


def run_tool(args: list[str], *, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except FileNotFoundError as exc:
        raise PackageError(f"missing executable: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise PackageError(details or f"command failed: {' '.join(args)}") from exc
    output = (result.stdout or "").strip()
    if output:
        print(output)
    err = (result.stderr or "").strip()
    if err:
        print(err)
    return output


def build_handoff_markdown(
    *,
    project_name: str,
    request_text: str,
    entry: dict,
    prompt_text: str,
    source_paths: list[str],
    page_count: str | None,
    audience: str | None,
    template_paths: list[str],
) -> str:
    source_lines = [f"- {path}" for path in source_paths] if source_paths else ["- none provided"]
    template_lines = [f"- {path}" for path in template_paths] if template_paths else ["- none provided"]
    lines = [
        "# Router Handoff",
        "",
        "## Project",
        "",
        f"- project_name: {project_name}",
        "",
        "## Request",
        "",
        request_text.strip(),
        "",
        "## Sources",
        "",
    ]
    lines.extend(source_lines)
    lines.extend([
        "",
        "## Templates",
        "",
    ])
    lines.extend(template_lines)
    lines.extend([
        "",
        "## Constraints",
        "",
        f"- page_count: {page_count or 'unspecified'}",
        f"- audience: {audience or 'unspecified'}",
        f"- templates: {', '.join(template_paths) if template_paths else 'unspecified'}",
        "",
        "## Selected Prompt",
        "",
        f"- prompt_id: {entry['id']}",
        f"- prompt_name: {entry['name_zh']}",
        f"- prompt_file: {entry['file']}",
        "",
        "```text",
        prompt_text.rstrip(),
        "```",
        "",
    ])
    return "\n".join(lines)


def cmd_route(args: argparse.Namespace) -> int:
    route_script = package_root() / "scripts" / "route.py"
    if not route_script.is_file():
        raise PackageError(f"Router 2.1 entrypoint not found: {route_script}")
    forwarded = [sys.executable, str(route_script)]
    for key in (
        "request", "page_count", "audience", "purpose", "prompt_id", "format",
        "project_name", "project_base", "ppt_master_root", "template_intent",
        "director_plan", "host",
    ):
        value = getattr(args, key, None)
        if value is not None:
            forwarded.extend([f"--{key.replace('_', '-')}", str(value)])
    for source in args.source:
        forwarded.extend(["--source", source])
    for template in args.template:
        forwarded.extend(["--template", template])
    if args.move:
        forwarded.append("--move")
    return subprocess.run(forwarded, check=False).returncode


def install_package(
    target_dir: Path,
    *,
    force: bool = False,
    source_root: Path | None = None,
    mode: str = "copy",
) -> Path:
    source_root = package_root(source_root)
    target_dir = target_dir.resolve(strict=False)
    destination = destination_root(target_dir)
    if source_target_conflict(source_root, target_dir, destination):
        raise PackageError("source and target paths overlap; refusing recursive install")
    if destination.exists() and not force:
        raise PackageError(f"destination already exists: {destination}")
    target_dir.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=f".{PACKAGE_NAME}-stage-", dir=str(target_dir.parent)))
    staging = staging_parent / PACKAGE_NAME
    backup = None
    try:
        if mode == "copy":
            copy_package_tree(source_root, staging)
            validate_package_root(staging)
        elif mode == "symlink":
            validate_package_root(source_root)
            staging.symlink_to(source_root, target_is_directory=True)
        else:
            raise PackageError("mode must be copy or symlink")
        if destination.exists():
            backup = staging_parent / f"{PACKAGE_NAME}.backup"
            os.replace(destination, backup)
        os.replace(staging, destination)
        return destination
    except Exception:
        if backup and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def uninstall_package(target_dir: Path) -> Path:
    destination = destination_root(target_dir.resolve(strict=False))
    if destination.exists():
        shutil.rmtree(destination)
    return destination


def _integration_files(root: Path) -> list[dict[str, Any]]:
    manifest = root / "integrations" / "ppt-master" / "manifest.json"
    try:
        return list(json.loads(manifest.read_text(encoding="utf-8"))["files"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PackageError(f"invalid PPT Master manifest: {exc}") from exc


def _installation_record(master_root: Path) -> Path:
    return master_root / ".ppt-prompt-router-install.json"


def apply_master_overlay(root: Path, master_root: Path) -> Path:
    """Apply only manifest-listed files and preserve every original for rollback."""
    root = package_root(root)
    master_root = master_root.resolve(strict=False)
    if not (master_root / ".git").exists():
        raise PackageError("PPT Master root must be a Git worktree")
    record_path = _installation_record(master_root)
    files = _integration_files(root)
    if record_path.exists():
        current = json.loads(record_path.read_text(encoding="utf-8"))
        if current.get("package_version") == (root / "VERSION").read_text(encoding="utf-8").strip():
            for item in files:
                target = master_root / item["path"]
                if not target.is_file() or sha256_file(target) != item["overlay_hash"]:
                    raise PackageError(f"existing PPT Master overlay was changed: {item['path']}")
            return record_path
        raise PackageError("PPT Master already has a different Router overlay; uninstall it first")

    backup = master_root / ".ppt-prompt-router-backup"
    staged: list[tuple[Path, Path | None]] = []
    try:
        for item in files:
            relative = Path(item["path"])
            target = master_root / relative
            source = root / "integrations" / "ppt-master" / "overlay" / relative
            upstream_hash = item.get("upstream_hash")
            if target.exists() and upstream_hash and sha256_file(target) != upstream_hash:
                raise PackageError(f"PPT Master upstream hash mismatch: {relative}")
            if not target.exists() and upstream_hash:
                raise PackageError(f"PPT Master file missing: {relative}")
            backup_file = backup / relative if target.exists() else None
            if backup_file:
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_file)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            staged.append((target, backup_file))
        record_path.write_text(json.dumps({
            "package_version": (root / "VERSION").read_text(encoding="utf-8").strip(),
            "files": [{"path": item["path"], "overlay_hash": item["overlay_hash"]} for item in files],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record_path
    except Exception:
        for target, backup_file in reversed(staged):
            if backup_file and backup_file.exists():
                shutil.copy2(backup_file, target)
            elif target.exists():
                target.unlink()
        raise


def uninstall_master_overlay(master_root: Path) -> None:
    master_root = master_root.resolve(strict=False)
    record_path = _installation_record(master_root)
    if not record_path.is_file():
        return
    record = json.loads(record_path.read_text(encoding="utf-8"))
    backup = master_root / ".ppt-prompt-router-backup"
    for item in record.get("files", []):
        relative = Path(item["path"])
        target = master_root / relative
        if target.exists() and sha256_file(target) != item["overlay_hash"]:
            raise PackageError(f"refusing to overwrite changed PPT Master file: {relative}")
        backup_file = backup / relative
        if backup_file.exists():
            shutil.copy2(backup_file, target)
        elif target.exists():
            target.unlink()
    shutil.rmtree(backup, ignore_errors=True)
    record_path.unlink(missing_ok=True)


def cmd_detect(args: argparse.Namespace) -> int:
    skills_dir = expand_path(args.skills_dir) if args.skills_dir else None
    adapter = get_adapter(args.host, skills_dir=skills_dir)
    print(json.dumps({
        "host": adapter.host_id,
        "detected": adapter.detect(),
        "skills_dirs": [str(path) for path in adapter.discover_skills_dirs()],
        "platform": platform.system().lower(),
    }, ensure_ascii=False, indent=2))
    return 0


def _target_for_install(args: argparse.Namespace) -> Path:
    if args.router_target:
        return expand_path(args.router_target)
    if args.target:
        return expand_path(args.target)
    adapter = get_adapter(args.host)
    return adapter.canonical_skills_dir()


def cmd_install(args: argparse.Namespace) -> int:
    target = _target_for_install(args)
    source = package_root()
    destination = destination_root(target)
    rollback_dir: Path | None = None
    rollback_copy: Path | None = None
    if destination.exists() or destination.is_symlink():
        if not args.force:
            raise PackageError(f"destination already exists: {destination}")
        rollback_dir = Path(tempfile.mkdtemp(prefix=f".{PACKAGE_NAME}-rollback-", dir=str(target.parent)))
        rollback_copy = rollback_dir / PACKAGE_NAME
        if destination.is_symlink():
            rollback_copy.symlink_to(destination.readlink(), target_is_directory=True)
        else:
            shutil.copytree(destination, rollback_copy)
    destination = install_package(target, force=args.force, source_root=source, mode=args.mode)
    try:
        if args.master_root:
            apply_master_overlay(destination, expand_path(args.master_root))
    except Exception:
        # Restore the Router destination when Master installation fails.
        if destination.exists() or destination.is_symlink():
            uninstall_package(target)
        if rollback_copy and (rollback_copy.exists() or rollback_copy.is_symlink()):
            os.replace(rollback_copy, destination)
        raise
    finally:
        if rollback_dir:
            shutil.rmtree(rollback_dir, ignore_errors=True)
    print(f"已安装 Router：{destination}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    target = _target_for_install(args)
    destination = destination_root(target)
    validate_package_root(destination)
    if args.master_root:
        master = expand_path(args.master_root)
        record = _installation_record(master)
        if not record.is_file():
            raise PackageError("未找到 PPT Master 覆盖层安装记录")
        for item in json.loads(record.read_text(encoding="utf-8")).get("files", []):
            target_file = master / item["path"]
            if not target_file.is_file() or sha256_file(target_file) != item["overlay_hash"]:
                raise PackageError(f"PPT Master 覆盖层校验失败：{item['path']}")
    print(f"已验证：{destination}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    if not args.yes:
        raise PackageError("uninstall requires --yes")
    target = _target_for_install(args)
    if args.master_root:
        uninstall_master_overlay(expand_path(args.master_root))
    print(f"已卸载 Router：{uninstall_package(target)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="install.py")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--host", choices=host_choices(), default="auto")
    install.add_argument("--target", help="兼容旧版：Agent skills parent directory")
    install.add_argument("--router-target", help="Router 安装到的技能父目录")
    install.add_argument("--master-root", help="标准 PPT Master 根目录")
    install.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    install.add_argument("--force", action="store_true")
    install.set_defaults(func=cmd_install)
    validate = sub.add_parser("validate")
    validate.add_argument("--host", choices=host_choices(), default="auto")
    validate.add_argument("--target", help="兼容旧版：Agent skills parent directory")
    validate.add_argument("--router-target", help="Router 安装到的技能父目录")
    validate.add_argument("--master-root", help="标准 PPT Master 根目录")
    validate.set_defaults(func=cmd_validate)
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("--host", choices=host_choices(), default="auto")
    uninstall.add_argument("--target", help="兼容旧版：Agent skills parent directory")
    uninstall.add_argument("--router-target", help="Router 安装到的技能父目录")
    uninstall.add_argument("--master-root", help="标准 PPT Master 根目录")
    uninstall.add_argument("--yes", action="store_true")
    uninstall.set_defaults(func=cmd_uninstall)
    detect = sub.add_parser("detect")
    detect.add_argument("--host", choices=host_choices(), default="auto")
    detect.add_argument("--skills-dir")
    detect.set_defaults(func=cmd_detect)
    route = sub.add_parser("route")
    route.add_argument("--request", required=True, help="Original user request text")
    route.add_argument("--source", action="append", default=[], help="Source file paths")
    route.add_argument("--template", action="append", default=[], help="Template file paths")
    route.add_argument("--page-count")
    route.add_argument("--audience")
    route.add_argument("--purpose")
    route.add_argument("--prompt-id")
    route.add_argument("--format", default="ppt169")
    route.add_argument("--project-name")
    route.add_argument("--project-base")
    route.add_argument("--ppt-master-root")
    route.add_argument("--template-intent", choices=["reference_elements", "native_fill", "reusable_template", "none"])
    route.add_argument("--director-plan")
    route.add_argument("--host", choices=["codex", "hermes", "claude-code", "generic"], default="codex")
    route.add_argument("--move", action="store_true", help="Move source files instead of copying them")
    route.set_defaults(func=cmd_route)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.func(args)
    except (PackageError, HostError) as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
