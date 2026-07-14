"""Offline suite installer shared by the released install entrypoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from installers import get_adapter, host_choices
from installers.base import HostError


class SuiteError(RuntimeError):
    pass


MANAGED_PREFIXES = ("skills/ppt-prompt-router/", "skills/ppt-master/")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def suite_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if not path.is_file():
        raise SuiteError("offline manifest.json is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0" or not isinstance(data.get("files"), list):
        raise SuiteError("offline manifest is invalid")
    return data


def verify_bundle(root: Path) -> dict[str, Any]:
    manifest = _load_manifest(root)
    checksums = root / "checksums.sha256"
    if not checksums.is_file():
        raise SuiteError("checksums.sha256 is missing")
    expected = {
        row["path"]: row["sha256"]
        for row in manifest["files"]
        if isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str)
    }
    if not expected:
        raise SuiteError("offline manifest has no managed files")
    checksum_rows = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        checksum_rows[relative] = digest
    if checksum_rows != expected:
        raise SuiteError("manifest and checksums.sha256 disagree")
    for relative, digest in expected.items():
        target = root / relative
        if not target.is_file() or sha256(target) != digest:
            raise SuiteError(f"offline bundle hash mismatch: {relative}")
    return manifest


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


def _live(target: Path) -> dict[str, Path]:
    return {
        "router": target / "ppt-prompt-router",
        "master": target / "ppt-master",
        "receipt": _receipt_path(target),
    }


def _copy_if_present(source: Path, destination: Path) -> None:
    if not (source.exists() or source.is_symlink()):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(source.readlink(), target_is_directory=True)
    elif source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _move_set(source: dict[str, Path], destination: dict[str, Path]) -> None:
    for name, path in source.items():
        if path.exists() or path.is_symlink():
            target = destination[name]
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, target)


def _paths_from_receipt(target: Path, receipt: dict[str, Any]) -> dict[str, Path]:
    paths = receipt.get("paths") or {}
    expected = _live(target)
    resolved = {name: Path(str(paths.get(name, ""))).resolve(strict=False) for name in ("router", "master")}
    if any(resolved[name] != expected[name].resolve(strict=False) for name in resolved):
        raise SuiteError("receipt paths do not match this skills directory")
    return expected


def verify_install(target: Path) -> dict[str, Any]:
    receipt_path = _receipt_path(target)
    if not receipt_path.is_file():
        raise SuiteError("install receipt is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "1.0":
        raise SuiteError("unsupported install receipt")
    _paths_from_receipt(target, receipt)
    for row in receipt.get("managed_files", []):
        relative = row.get("path")
        digest = row.get("sha256")
        if not isinstance(relative, str) or not relative.startswith(MANAGED_PREFIXES):
            raise SuiteError("invalid managed file in receipt")
        target_file = target / relative.removeprefix("skills/")
        if not target_file.is_file() or sha256(target_file) != digest:
            raise SuiteError(f"managed file changed: {relative}")
    return receipt


def _dependency_status() -> dict[str, Any]:
    modules = ("pptx", "xlsxwriter")
    available, missing = [], []
    for module in modules:
        try:
            __import__(module)
            available.append(module)
        except ImportError:
            missing.append(module)
    return {"python": sys.version.split()[0], "available": available, "missing": missing}


def _receipt(target: Path, manifest: dict[str, Any], bundle: Path, host: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "suite_version": manifest["suite_version"],
        "router_version": manifest["router_version"],
        "master_upstream_commit": manifest["master_upstream_commit"],
        "overlay_version": manifest["overlay_version"],
        "overlay_hash": manifest["overlay_hash"],
        "skills_root": str(target),
        "paths": {"router": str(target / "ppt-prompt-router"), "master": str(target / "ppt-master")},
        "manifest_hash": sha256(bundle / "manifest.json"),
        "checksums_hash": sha256(bundle / "checksums.sha256"),
        "managed_files": [row for row in manifest["files"] if row["path"].startswith(MANAGED_PREFIXES)],
        "host": host,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _install(bundle: Path, args: argparse.Namespace, *, upgrade: bool) -> dict[str, Any]:
    manifest = verify_bundle(bundle)
    target = _target(args)
    target.mkdir(parents=True, exist_ok=True)
    state = _state_dir(target)
    state.mkdir(parents=True, exist_ok=True)
    live = _live(target)
    receipt_exists = live["receipt"].is_file()
    if receipt_exists:
        verify_install(target)
    elif upgrade:
        raise SuiteError("upgrade requires an existing managed offline suite")

    stage = Path(tempfile.mkdtemp(prefix=".ppt-director-stage-", dir=str(target)))
    staged = {"router": stage / "ppt-prompt-router", "master": stage / "ppt-master", "receipt": stage / "install_receipt.json"}
    backup_name = "previous" if receipt_exists else "baseline"
    backup = _backup(target, backup_name)
    backup_paths = {name: backup / name for name in live}
    moved = False
    try:
        shutil.copytree(bundle / "skills" / "ppt-prompt-router", staged["router"])
        shutil.copytree(bundle / "skills" / "ppt-master", staged["master"])
        _write_receipt(staged["receipt"], _receipt(target, manifest, bundle, args.host))
        if backup.exists():
            shutil.rmtree(backup)
        backup.mkdir(parents=True)
        _move_set(live, backup_paths)
        moved = True
        os.replace(staged["router"], live["router"])
        os.replace(staged["master"], live["master"])
        os.replace(staged["receipt"], live["receipt"])
    except Exception:
        for path in (live["router"], live["master"], live["receipt"]):
            if path.exists() or path.is_symlink():
                shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()
        if moved:
            _move_set(backup_paths, live)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"status": "COMPLETE", "skills_root": str(target), "receipt": str(live["receipt"]), "dependencies": _dependency_status()}


def _rollback(target: Path) -> dict[str, Any]:
    verify_install(target)
    previous = _backup(target, "previous")
    if not previous.is_dir():
        raise SuiteError("no previous suite is available for rollback")
    stage = Path(tempfile.mkdtemp(prefix=".ppt-director-rollback-", dir=str(target)))
    live = _live(target)
    try:
        staged = {name: stage / name for name in live}
        previous_paths = {name: previous / name for name in live}
        _move_set(live, staged)
        _move_set(previous_paths, live)
        _move_set(staged, previous_paths)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"status": "ROLLED_BACK", "skills_root": str(target)}


def _uninstall(target: Path) -> dict[str, Any]:
    verify_install(target)
    live = _live(target)
    baseline = _backup(target, "baseline")
    stage = Path(tempfile.mkdtemp(prefix=".ppt-director-uninstall-", dir=str(target)))
    try:
        staged = {name: stage / name for name in live}
        _move_set(live, staged)
        if baseline.is_dir():
            _move_set({name: baseline / name for name in live}, live)
    except Exception:
        _move_set(staged, live)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"status": "REMOVED", "skills_root": str(target), "baseline_restored": baseline.is_dir()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PPT Director offline suite")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "upgrade", "rollback", "validate", "uninstall"):
        item = sub.add_parser(command)
        item.add_argument("--host", choices=host_choices(), default="auto")
        item.add_argument("--skills-dir")
        if command == "uninstall":
            item.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = suite_root()
        if args.command in {"install", "upgrade"}:
            result = _install(root, args, upgrade=args.command == "upgrade")
        else:
            target = _target(args)
            if args.command == "validate":
                receipt = verify_install(target)
                result = {
                    "status": "VERIFIED",
                    "skills_root": str(target),
                    "suite_version": receipt["suite_version"],
                    "master_upstream_commit": receipt["master_upstream_commit"],
                    "managed_file_count": len(receipt["managed_files"]),
                    "dependencies": _dependency_status(),
                }
            elif args.command == "rollback":
                result = _rollback(target)
            else:
                if not args.yes:
                    raise SuiteError("uninstall requires --yes")
                result = _uninstall(target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SuiteError, HostError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
