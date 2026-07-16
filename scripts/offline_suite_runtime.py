"""Transactional installer for the PPT Director 3.0 single-Skill suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from installers import get_adapter, host_choices
from installers.base import HostError


class SuiteError(RuntimeError):
    pass


class SuiteConflict(SuiteError):
    def __init__(self, paths: list[Path]):
        self.paths = paths
        super().__init__("discoverable PPT Skill conflict")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _configure_utf8() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _bundle_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if not path.is_file():
        raise SuiteError("offline manifest.json is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "2.0" or not isinstance(data.get("files"), list):
        raise SuiteError("offline manifest is invalid")
    return data


def _verify_bundle(root: Path) -> dict[str, Any]:
    data = _manifest(root)
    checksum_file = root / "checksums.sha256"
    if not checksum_file.is_file():
        raise SuiteError("checksums.sha256 is missing")
    expected = {row["path"]: row["sha256"] for row in data["files"]}
    actual: dict[str, str] = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, relative = line.split("  ", 1)
            actual[relative] = digest
    if actual != expected:
        raise SuiteError("manifest and checksums.sha256 disagree")
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != digest:
            raise SuiteError(f"offline bundle hash mismatch: {relative}")
    installs = list(root.rglob("install.py"))
    if installs != [root / "install.py"]:
        raise SuiteError("offline suite must contain exactly one root install.py")
    return data


def _target(args: argparse.Namespace) -> Path:
    if args.skills_dir:
        return Path(args.skills_dir).expanduser().resolve()
    adapter = get_adapter(args.host)
    method = getattr(adapter, "canonical_skills_dir", None)
    if method is None:
        raise SuiteError("generic host requires --skills-dir")
    return Path(method()).resolve()


def _state_dir(target: Path) -> Path:
    return target / ".ppt-director"


def _receipt_path(target: Path) -> Path:
    return _state_dir(target) / "install_receipt.json"


def _backup(target: Path, name: str) -> Path:
    return _state_dir(target) / "backups" / name


def _read_skill_name(path: Path) -> str | None:
    skill = path / "SKILL.md"
    if not skill.is_file():
        return None
    for line in skill.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip()
    return path.name


def _known_discovery_roots(host: str) -> list[Path]:
    home = Path.home()
    if host == "claude-code":
        return [home / ".claude" / "plugins" / "cache", home / ".claude" / "plugins" / "marketplaces"]
    if host == "codex":
        return [home / ".codex" / "plugins" / "cache"]
    return []


def _discover(args: argparse.Namespace, target: Path) -> list[tuple[str, Path]]:
    adapter = get_adapter(args.host)
    roots = [target] if args.skills_dir and args.host == "generic" else adapter.discover_skills_dirs()
    roots.extend(path for path in _known_discovery_roots(args.host) if path.is_dir())
    found: dict[Path, str] = {}
    for root in roots:
        root = Path(root).expanduser().resolve(strict=False)
        if not root.is_dir():
            continue
        candidates = list(root.iterdir()) if root == target else [path.parent for path in root.rglob("SKILL.md")]
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            name = _read_skill_name(candidate)
            if name in {"ppt-master", "ppt-prompt-router"}:
                found[candidate.resolve(strict=False)] = name
    return sorted(((name, path) for path, name in found.items()), key=lambda item: str(item[1]))


def _load_receipt(target: Path) -> dict[str, Any] | None:
    path = _receipt_path(target)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_rows(target: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        relative, digest = row.get("path"), row.get("sha256")
        if not isinstance(relative, str) or not relative.startswith("skills/ppt-prompt-router/"):
            raise SuiteError("receipt contains an invalid managed path")
        path = target / relative.removeprefix("skills/")
        if not path.is_file() or _sha256(path) != digest:
            raise SuiteError(f"managed file changed: {relative}")


def _managed_old_master(target: Path, receipt: dict[str, Any] | None) -> bool:
    master = target / "ppt-master"
    if not master.is_dir() or not receipt:
        return False
    rows = [row for row in receipt.get("managed_files", []) if str(row.get("path", "")).startswith("skills/ppt-master/")]
    if not rows:
        return False
    for row in rows:
        path = target / str(row["path"]).removeprefix("skills/")
        if not path.is_file() or _sha256(path) != row.get("sha256"):
            return False
    return True


def _conflicts(args: argparse.Namespace, target: Path, receipt: dict[str, Any] | None) -> list[Path]:
    conflicts: list[Path] = []
    for name, path in _discover(args, target):
        if name == "ppt-master":
            if path == (target / "ppt-master").resolve(strict=False) and _managed_old_master(target, receipt):
                continue
            conflicts.append(path)
        elif path != (target / "ppt-prompt-router").resolve(strict=False):
            conflicts.append(path)
    return sorted(set(conflicts))


def _runtime_probe(target: Path) -> dict[str, str]:
    router = target / "ppt-prompt-router"
    route = router / "scripts" / "route.py"
    code = f"""
import importlib, importlib.util, json, pathlib, sys
route = pathlib.Path({str(route)!r})
spec = importlib.util.spec_from_file_location('ppt_director_route_probe', route)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
paths = {{'route': str(route.resolve())}}
with module.master_modules():
    for name in ('project_manager', 'director_plan', 'production', 'visual_review', 'runtime_guard'):
        item = importlib.import_module(name)
        paths[name] = str(pathlib.Path(item.__file__).resolve())
print(json.dumps(paths))
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-c", code], cwd=target, env=env, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise SuiteError(f"installed runtime probe failed: {(result.stderr or result.stdout).strip()}")
    paths = json.loads(result.stdout.splitlines()[-1])
    runtime = (router / "runtime" / "ppt-master").resolve()
    for name, raw in paths.items():
        if name == "route":
            continue
        try:
            Path(raw).relative_to(runtime)
        except ValueError as exc:
            raise SuiteError(f"module loaded outside internal runtime: {name}={raw}") from exc
    return paths


def _verify_install(args: argparse.Namespace, target: Path) -> dict[str, Any]:
    receipt = _load_receipt(target)
    if not receipt or receipt.get("schema_version") != "3.0":
        raise SuiteError("install receipt is missing or invalid")
    if Path(receipt.get("skills_root", "")).resolve(strict=False) != target.resolve(strict=False):
        raise SuiteError("receipt skills_root does not match target")
    _verify_rows(target, list(receipt.get("managed_files") or []))
    router = target / "ppt-prompt-router"
    runtime = router / "runtime" / "ppt-master"
    if not (router / "SKILL.md").is_file() or not (runtime / "MASTER.md").is_file():
        raise SuiteError("installed single-Skill runtime is incomplete")
    if any(runtime.rglob("SKILL.md")) or any(runtime.rglob("install.py")):
        raise SuiteError("internal runtime exposes a Skill or installer")
    conflicts = _conflicts(args, target, receipt)
    if conflicts:
        raise SuiteConflict(conflicts)
    paths = _runtime_probe(target)
    return {"receipt": receipt, "module_files": paths}


def _dependency_status() -> dict[str, Any]:
    available, missing = [], []
    for module in ("pptx", "xlsxwriter"):
        try:
            __import__(module)
            available.append(module)
        except ImportError:
            missing.append(module)
    return {"python": sys.version.split()[0], "available": available, "missing": missing}


def _receipt(target: Path, manifest: dict[str, Any], bundle: Path, host: str) -> dict[str, Any]:
    rows = [row for row in manifest["files"] if row["path"].startswith("skills/ppt-prompt-router/")]
    return {
        "schema_version": "3.0",
        "suite_version": manifest["suite_version"],
        "router_baseline_commit": manifest["router_baseline_commit"],
        "master_baseline_commit": manifest["master_baseline_commit"],
        "overlay_version": manifest["overlay_version"],
        "overlay_hash": manifest["overlay_hash"],
        "runtime_hash": manifest["runtime_hash"],
        "skills_root": str(target),
        "router_path": str(target / "ppt-prompt-router"),
        "manifest_hash": _sha256(bundle / "manifest.json"),
        "checksums_hash": _sha256(bundle / "checksums.sha256"),
        "managed_files": rows,
        "host": host,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_existing(path: Path, destination: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir() and not path.is_symlink():
        shutil.copytree(path, destination)
    elif path.is_symlink():
        destination.symlink_to(path.readlink(), target_is_directory=True)
    else:
        shutil.copy2(path, destination)


def _install(bundle: Path, args: argparse.Namespace, *, upgrade: bool) -> dict[str, Any]:
    manifest = _verify_bundle(bundle)
    target = _target(args)
    target.mkdir(parents=True, exist_ok=True)
    old_receipt = _load_receipt(target)
    if upgrade:
        _verify_install(args, target)
    conflicts = _conflicts(args, target, old_receipt)
    if conflicts:
        raise SuiteConflict(conflicts)
    managed_master = _managed_old_master(target, old_receipt)
    stage = Path(tempfile.mkdtemp(prefix=".ppt-director-stage-", dir=target))
    staged_router = stage / "ppt-prompt-router"
    staged_receipt = stage / "install_receipt.json"
    backup = _backup(target, "previous" if old_receipt else "baseline")
    live_router = target / "ppt-prompt-router"
    live_master = target / "ppt-master"
    live_receipt = _receipt_path(target)
    try:
        shutil.copytree(bundle / "skills" / "ppt-prompt-router", staged_router)
        _write_json(staged_receipt, _receipt(target, manifest, bundle, args.host))
        if backup.exists():
            shutil.rmtree(backup)
        backup.mkdir(parents=True)
        _copy_existing(live_router, backup / "ppt-prompt-router")
        _copy_existing(live_receipt, backup / "install_receipt.json")
        if managed_master:
            _copy_existing(live_master, backup / "ppt-master")
        old_router = stage / "old-router"
        old_master = stage / "old-master"
        old_receipt_path = stage / "old-receipt.json"
        if live_router.exists() or live_router.is_symlink():
            os.replace(live_router, old_router)
        if managed_master:
            os.replace(live_master, old_master)
        if live_receipt.exists():
            os.replace(live_receipt, old_receipt_path)
        os.replace(staged_router, live_router)
        live_receipt.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_receipt, live_receipt)
        verified = _verify_install(args, target)
    except Exception:
        if live_router.exists() or live_router.is_symlink():
            shutil.rmtree(live_router) if live_router.is_dir() and not live_router.is_symlink() else live_router.unlink()
        if live_receipt.exists():
            live_receipt.unlink()
        if (stage / "old-router").exists():
            os.replace(stage / "old-router", live_router)
        if (stage / "old-master").exists():
            os.replace(stage / "old-master", live_master)
        if (stage / "old-receipt.json").exists():
            live_receipt.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / "old-receipt.json", live_receipt)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {
        "status": "COMPLETE",
        "skills_root": str(target),
        "receipt": str(live_receipt),
        "module_files": verified["module_files"],
        "dependencies": _dependency_status(),
    }


def _rollback(args: argparse.Namespace, target: Path) -> dict[str, Any]:
    _verify_install(args, target)
    previous = _backup(target, "previous")
    if not previous.is_dir():
        raise SuiteError("no previous version is available")
    live_router, live_receipt = target / "ppt-prompt-router", _receipt_path(target)
    stage = Path(tempfile.mkdtemp(prefix=".ppt-director-rollback-", dir=target))
    try:
        os.replace(live_router, stage / "ppt-prompt-router")
        os.replace(live_receipt, stage / "install_receipt.json")
        os.replace(previous / "ppt-prompt-router", live_router)
        os.replace(previous / "install_receipt.json", live_receipt)
        os.replace(stage / "ppt-prompt-router", previous / "ppt-prompt-router")
        os.replace(stage / "install_receipt.json", previous / "install_receipt.json")
        _verify_install(args, target)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"status": "ROLLED_BACK", "skills_root": str(target)}


def _uninstall(args: argparse.Namespace, target: Path) -> dict[str, Any]:
    _verify_install(args, target)
    baseline = _backup(target, "baseline")
    router, receipt = target / "ppt-prompt-router", _receipt_path(target)
    shutil.rmtree(router)
    receipt.unlink()
    restored = False
    if baseline.is_dir():
        if (baseline / "ppt-prompt-router").exists():
            os.replace(baseline / "ppt-prompt-router", router)
        if (baseline / "ppt-master").exists():
            os.replace(baseline / "ppt-master", target / "ppt-master")
        if (baseline / "install_receipt.json").exists():
            os.replace(baseline / "install_receipt.json", receipt)
        restored = True
    return {"status": "REMOVED", "skills_root": str(target), "baseline_restored": restored}


def main(argv: list[str] | None = None) -> int:
    _configure_utf8()
    parser = argparse.ArgumentParser(description="PPT Director 3.0 offline suite")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "upgrade", "rollback", "validate", "uninstall"):
        item = sub.add_parser(command)
        item.add_argument("--host", choices=host_choices(), default="auto")
        item.add_argument("--skills-dir")
        if command == "uninstall":
            item.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        root, target = _bundle_root(), _target(args)
        if args.command == "install":
            result = _install(root, args, upgrade=False)
        elif args.command == "upgrade":
            result = _install(root, args, upgrade=True)
        elif args.command == "validate":
            verified = _verify_install(args, target)
            result = {"status": "VERIFIED", "skills_root": str(target), "suite_version": verified["receipt"]["suite_version"], "module_files": verified["module_files"], "dependencies": _dependency_status()}
        elif args.command == "rollback":
            result = _rollback(args, target)
        else:
            if not args.yes:
                raise SuiteError("uninstall requires --yes")
            result = _uninstall(args, target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except SuiteConflict as exc:
        print(json.dumps({"status": "CONFLICT", "conflicts": [str(path) for path in exc.paths]}, ensure_ascii=False, indent=2))
        return 4
    except (SuiteError, HostError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
