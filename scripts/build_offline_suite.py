#!/usr/bin/env python3
"""Build the PPT Director offline suite from a clean, pinned source tree."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "ppt-master"
OVERLAY_ROOT = ROOT / "integrations" / "ppt-master"
FORBIDDEN_PARTS = {".git", ".claude-plugin", "examples", "docs", "projects", "tests", "__pycache__"}
FORBIDDEN_SUFFIXES = {".pptx", ".potx", ".ppsx", ".log", ".pyc"}


class BuildError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(source: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=source, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise BuildError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def lock() -> dict[str, Any]:
    return json_file(OVERLAY_ROOT / "upstream.lock")


def verify_clean_master(source: Path) -> None:
    home = Path.home()
    forbidden = (
        home / "Documents" / "ppt-master",
        home / "Claude-ppt_master",
        home / ".claude" / "skills" / "ppt-master",
        home / ".claude" / "plugins",
    )
    source_resolved = source.resolve()
    for blocked in forbidden:
        try:
            source_resolved.relative_to(blocked.resolve())
        except ValueError:
            continue
        raise BuildError("Master source is a forbidden local runtime directory")
    expected = lock()
    if git(source, "remote", "get-url", "origin") != expected["repository"]:
        raise BuildError("Master origin does not match upstream.lock")
    if git(source, "rev-parse", "HEAD") != expected["commit"]:
        raise BuildError("Master HEAD does not match upstream.lock")
    if git(source, "status", "--porcelain"):
        raise BuildError("Master worktree is not clean")


def ignored(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in FORBIDDEN_PARTS or name == ".DS_Store"}


def sync_vendor(source: Path) -> None:
    source = source.resolve()
    verify_clean_master(source)
    skill = source / "skills" / "ppt-master"
    if not (source / "LICENSE").is_file() or not skill.is_dir():
        raise BuildError("Master source is missing LICENSE or skills/ppt-master")
    stage = Path(tempfile.mkdtemp(prefix=".ppt-master-vendor-", dir=str(ROOT / "vendor" if (ROOT / "vendor").exists() else ROOT)))
    target = stage / "ppt-master"
    try:
        target.mkdir(parents=True)
        shutil.copy2(source / "LICENSE", target / "LICENSE")
        shutil.copytree(skill, target / "skills" / "ppt-master", ignore=ignored)
        validate_runtime(target / "skills" / "ppt-master")
        VENDOR.parent.mkdir(parents=True, exist_ok=True)
        old = VENDOR.with_name(".ppt-master-old")
        if old.exists():
            shutil.rmtree(old)
        if VENDOR.exists():
            os.replace(VENDOR, old)
        os.replace(target, VENDOR)
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def manifest() -> dict[str, Any]:
    data = json_file(OVERLAY_ROOT / "manifest.json")
    if not isinstance(data.get("files"), list):
        raise BuildError("overlay manifest is invalid")
    return data


def verify_and_apply_overlay(master_root: Path) -> list[str]:
    files = manifest()["files"]
    closure: list[str] = []
    for item in files:
        relative = Path(item["path"])
        source = OVERLAY_ROOT / "overlay" / relative
        target = master_root / relative
        if not source.is_file() or digest(source) != item["overlay_hash"]:
            raise BuildError(f"overlay hash mismatch: {relative}")
        if item["action"] == "modify":
            if not target.is_file() or digest(target) != item["upstream_hash"]:
                raise BuildError(f"overlay upstream mismatch: {relative}")
        elif item["action"] == "add":
            if target.exists():
                raise BuildError(f"overlay add target already exists: {relative}")
        else:
            raise BuildError(f"unsupported overlay action: {item['action']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if target.suffix == ".py":
            closure.extend(local_import_closure(target, master_root / "skills" / "ppt-master" / "scripts"))
    return sorted(set(closure))


def local_import_closure(entry: Path, scripts: Path) -> list[str]:
    known = {path.stem: path for path in scripts.rglob("*.py") if path.name != "__init__.py"}
    seen: set[Path] = set()
    pending = [entry]
    while pending:
        current = pending.pop()
        if current in seen or not current.is_file():
            continue
        seen.add(current)
        tree = ast.parse(current.read_text(encoding="utf-8"), filename=str(current))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".", 1)[0]
                    if module in known:
                        pending.append(known[module])
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.split(".", 1)[0]
                if module in known:
                    pending.append(known[module])
    return [str(path.relative_to(scripts.parent)) for path in seen]


def validate_runtime(skill: Path) -> None:
    required = ("SKILL.md", "scripts", "templates", "references", "workflows", "requirements.txt")
    for name in required:
        if not (skill / name).exists():
            raise BuildError(f"runtime missing {name}")
    for path in skill.rglob("*"):
        if not path.is_file():
            continue
        if any(part in FORBIDDEN_PARTS for part in path.parts) or path.name == ".DS_Store" or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise BuildError(f"forbidden runtime file: {path}")


def purge_and_validate_bundle(root: Path) -> None:
    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            shutil.rmtree(path)
    for path in list(root.rglob(".DS_Store")):
        path.unlink()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in FORBIDDEN_PARTS for part in path.parts) or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise BuildError(f"forbidden offline bundle file: {path}")


def runtime_smoke(root: Path, workspace: Path) -> None:
    scripts = root / "skills" / "ppt-master" / "scripts"
    python_files = sorted(scripts.rglob("*.py"))
    result = subprocess.run([sys.executable, "-m", "py_compile", *(str(path) for path in python_files)], capture_output=True, text=True)
    if result.returncode:
        raise BuildError(result.stderr or "py_compile failed")
    imports = "import sys; sys.path.insert(0, {!r}); import project_manager, director_plan, production, reference_elements, visual_review".format(str(scripts))
    result = subprocess.run([sys.executable, "-c", imports], capture_output=True, text=True)
    if result.returncode:
        raise BuildError(result.stderr or "runtime import failed")
    sys.path.insert(0, str(root / "skills" / "ppt-prompt-router"))
    from install import run_master_overlay_smoke  # type: ignore
    smoke = run_master_overlay_smoke(root, workspace)
    if smoke.get("status") != "passed":
        raise BuildError("router-accept smoke did not pass")


def payload_files(root: Path) -> list[dict[str, str]]:
    files = []
    for base in (root / "skills" / "ppt-prompt-router", root / "skills" / "ppt-master"):
        for file in sorted(path for path in base.rglob("*") if path.is_file()):
            relative = str(file.relative_to(root))
            files.append({"path": relative, "sha256": digest(file)})
    return files


def write_entries(stage: Path) -> None:
    entry = """#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parent\nsys.path.insert(0, str(ROOT / 'skills' / 'ppt-prompt-router'))\nfrom scripts.offline_suite_runtime import main\nif __name__ == '__main__':\n    raise SystemExit(main())\n"""
    (stage / "install.py").write_text(entry, encoding="utf-8")
    (stage / "uninstall.py").write_text(entry.replace("main())", "main(['uninstall', *sys.argv[1:]]))"), encoding="utf-8")


def build(output_dir: Path) -> Path:
    if not VENDOR.is_dir():
        raise BuildError("vendor/ppt-master is missing; run sync-vendor first")
    expected = lock()["commit"]
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    name = f"ppt-prompt-router-{version}-master-{expected[:7]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_parent = Path(tempfile.mkdtemp(prefix=".ppt-director-build-", dir=str(output_dir)))
    stage = stage_parent / name
    try:
        (stage / "skills").mkdir(parents=True)
        shutil.copytree(ROOT, stage / "skills" / "ppt-prompt-router", ignore=shutil.ignore_patterns(".git", "vendor", "dist", "docs", "tests", "__pycache__", ".DS_Store", "*.pyc"))
        shutil.copytree(VENDOR / "skills" / "ppt-master", stage / "skills" / "ppt-master")
        (stage / "LICENSES").mkdir()
        shutil.copy2(VENDOR / "LICENSE", stage / "LICENSES" / "ppt-master-MIT.txt")
        closure = verify_and_apply_overlay(stage)
        validate_runtime(stage / "skills" / "ppt-master")
        runtime_smoke(stage, stage_parent / "smoke")
        write_entries(stage)
        purge_and_validate_bundle(stage)
        files = payload_files(stage)
        for root_file in ("install.py", "uninstall.py", "LICENSES/ppt-master-MIT.txt"):
            file = stage / root_file
            files.append({"path": root_file, "sha256": digest(file)})
        overlay_hash = digest(OVERLAY_ROOT / "manifest.json")
        data = {
            "schema_version": "1.0",
            "suite_version": version,
            "router_version": version,
            "master_upstream_commit": expected,
            "overlay_version": manifest().get("overlay_version"),
            "overlay_hash": overlay_hash,
            "overlay_dependency_closure": closure,
            "files": sorted(files, key=lambda item: item["path"]),
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
        (stage / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "checksums.sha256").write_text("".join(f"{row['sha256']}  {row['path']}\n" for row in data["files"]), encoding="utf-8")
        final = output_dir / name
        archive = output_dir / f"{name}.zip"
        retired = output_dir / f".{name}.retired"
        if retired.exists():
            shutil.rmtree(retired, ignore_errors=True)
        if final.exists():
            os.replace(final, retired)
        os.replace(stage, final)
        shutil.rmtree(retired, ignore_errors=True)
        purge_and_validate_bundle(final)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as package:
            for file in sorted(path for path in final.rglob("*") if path.is_file()):
                package.write(file, file.relative_to(final.parent))
        return final
    finally:
        shutil.rmtree(stage_parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the PPT Director offline suite")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync-vendor")
    sync.add_argument("--master-source", required=True)
    package = sub.add_parser("build")
    package.add_argument("--output-dir", default=str(ROOT / "dist"))
    args = parser.parse_args()
    try:
        if args.command == "sync-vendor":
            sync_vendor(Path(args.master_source))
            print(json.dumps({"status": "VENDOR_SYNCED", "vendor": str(VENDOR)}, ensure_ascii=False))
        else:
            output = build(Path(args.output_dir).expanduser().resolve())
            print(json.dumps({"status": "COMPLETE", "output": str(output)}, ensure_ascii=False))
        return 0
    except (BuildError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
