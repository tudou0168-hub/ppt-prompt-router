#!/usr/bin/env python3
"""Build the PPT Director single-Skill offline suite from pinned clean sources."""

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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "ppt-master"
OVERLAY_ROOT = ROOT / "integrations" / "ppt-master"
ROUTER_BASELINE = "3567a510bd64e3197e009f5af4e02b03ac69af2c"
FORBIDDEN_PARTS = {".git", ".claude-plugin", "examples", "docs", "projects", "tests", "__pycache__"}
FORBIDDEN_SUFFIXES = {".pptx", ".potx", ".ppsx", ".log", ".pyc"}


class BuildError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=source, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise BuildError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def lock() -> dict[str, Any]:
    return json_file(OVERLAY_ROOT / "upstream.lock")


def verify_clean_master(source: Path) -> None:
    expected = lock()
    if git(source, "remote", "get-url", "origin") != expected["repository"]:
        raise BuildError("Master origin does not match upstream.lock")
    if git(source, "rev-parse", "HEAD") != expected["commit"]:
        raise BuildError("Master HEAD does not match upstream.lock")
    if git(source, "status", "--porcelain"):
        raise BuildError("Master worktree is not clean")


def _ignored(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in FORBIDDEN_PARTS
        or name == ".DS_Store"
        or name.endswith((".pptx", ".potx", ".ppsx", ".pyc"))
    }


def sync_vendor(source: Path) -> None:
    source = source.expanduser().resolve()
    verify_clean_master(source)
    skill = source / "skills" / "ppt-master"
    if not (source / "LICENSE").is_file() or not skill.is_dir():
        raise BuildError("Master source is missing LICENSE or skills/ppt-master")
    VENDOR.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".ppt-master-vendor-", dir=VENDOR.parent))
    target = stage / "ppt-master"
    old = VENDOR.with_name(".ppt-master-old")
    try:
        target.mkdir()
        shutil.copy2(source / "LICENSE", target / "LICENSE")
        shutil.copytree(skill, target / "skills" / "ppt-master", ignore=_ignored)
        (target / ".upstream.json").write_text(
            json.dumps(
                {
                    "repository": lock()["repository"],
                    "commit": lock()["commit"],
                    "skill_tree_hash": _tree_hash(target / "skills" / "ppt-master"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _validate_master(target / "skills" / "ppt-master", internal=False)
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


def _verify_vendor() -> None:
    provenance = VENDOR / ".upstream.json"
    if not provenance.is_file():
        raise BuildError("vendor provenance is missing; run sync-vendor")
    data = json_file(provenance)
    expected = lock()
    if data.get("repository") != expected["repository"] or data.get("commit") != expected["commit"]:
        raise BuildError("vendor provenance does not match upstream.lock")
    actual = _tree_hash(VENDOR / "skills" / "ppt-master")
    if data.get("skill_tree_hash") != actual:
        raise BuildError("vendor runtime differs from its clean synced tree")


def _local_import_closure(entry: Path, scripts: Path) -> list[str]:
    known = {path.stem: path for path in scripts.rglob("*.py") if path.name != "__init__.py"}
    pending, seen = [entry], set()
    while pending:
        current = pending.pop()
        if current in seen or not current.is_file():
            continue
        seen.add(current)
        tree = ast.parse(current.read_text(encoding="utf-8"), filename=str(current))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module.split(".", 1)[0]]
            pending.extend(known[module] for module in modules if module in known)
    return [str(path.relative_to(scripts.parent)) for path in seen]


def _apply_overlay(skill: Path) -> list[str]:
    closure: list[str] = []
    for item in manifest()["files"]:
        relative = Path(item["path"])
        if relative.parts[:2] != ("skills", "ppt-master"):
            raise BuildError(f"invalid overlay path: {relative}")
        source = OVERLAY_ROOT / "overlay" / relative
        target = skill / relative.relative_to("skills/ppt-master")
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
            closure.extend(_local_import_closure(target, skill / "scripts"))
    return sorted(set(closure))


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip()
    return text


def _inject_runtime_guard(skill: Path) -> None:
    guard = skill / "scripts" / "runtime_guard.py"
    if not guard.is_file():
        raise BuildError("runtime_guard.py is required before building the internal runtime")
    markers = ("if __name__ == '__main__':", 'if __name__ == "__main__":')
    for path in skill.rglob("*.py"):
        if path == guard:
            continue
        text = path.read_text(encoding="utf-8")
        marker = next((value for value in markers if value in text), None)
        if marker is None or "_ppt_director_guard.enforce_cli" in text:
            continue
        snippet = (
            f"{marker}\n"
            "    from pathlib import Path as _PptDirectorPath\n"
            "    import sys as _ppt_director_sys\n"
            "    _ppt_director_scripts = next(parent / 'scripts' for parent in _PptDirectorPath(__file__).resolve().parents if (parent / 'scripts' / 'runtime_guard.py').is_file())\n"
            "    _ppt_director_sys.path.insert(0, str(_ppt_director_scripts))\n"
            "    import runtime_guard as _ppt_director_guard\n"
            "    _ppt_director_guard.enforce_cli(__file__)\n"
        )
        path.write_text(text.replace(marker + "\n", snippet, 1), encoding="utf-8")


def _make_internal_master(skill: Path) -> None:
    source = skill / "SKILL.md"
    if not source.is_file():
        raise BuildError("Master SKILL.md is missing")
    master_text = _strip_frontmatter(source.read_text(encoding="utf-8"))
    master_text += (
        "\n\n## PPT Director managed projects\n\n"
        "For projects containing `analysis/director_contract.json`, first read "
        "`references/ppt-director-runtime.md` and use the Router command's "
        "required context. Planning also requires "
        "`references/ppt-director-strategist.md`.\n"
    )
    (skill / "MASTER.md").write_text(master_text, encoding="utf-8")
    source.unlink()
    _inject_typography_check(skill)
    _inject_controlled_renderer(skill)
    _inject_runtime_guard(skill)


def _inject_typography_check(skill: Path) -> None:
    """Connect the profile minimum check to Master's existing quality checker."""
    checker = skill / "scripts" / "svg_quality_checker.py"
    text = checker.read_text(encoding="utf-8")
    needle = "            if root is not None:\n                # 1. Check viewBox"
    replacement = (
        "            if root is not None:\n"
        "                from profile_typography import effective_font_size_errors\n"
        "                result['errors'].extend(effective_font_size_errors(svg_path, root))\n\n"
        "                # 1. Check viewBox"
    )
    if needle not in text:
        raise BuildError("cannot connect profile typography to svg_quality_checker.py")
    checker.write_text(text.replace(needle, replacement, 1), encoding="utf-8")


def _inject_controlled_renderer(skill: Path) -> None:
    """Expose single-file rendering through Master's existing visual_review module."""
    renderer = skill / "scripts" / "visual_review.py"
    text = renderer.read_text(encoding="utf-8")
    needle = "\ndef fetch_slide_text("
    helper = '''
def render_svg_file(source: Path, output: Path) -> dict:
    """Render one managed current.svg with the native Playwright backend."""
    from playwright.sync_api import sync_playwright
    from xml.etree import ElementTree as ET

    root = ET.parse(source).getroot()
    view_box = (root.get('viewBox') or '0 0 1280 720').split()
    width, height = max(1, int(float(view_box[2]))), max(1, int(float(view_box[3])))
    svg_text = source.read_text(encoding='utf-8')
    base_uri = source.parent.resolve().as_uri() + '/'
    html = '<html><head><base href="' + base_uri + '"><style>html,body{margin:0;overflow:hidden}svg{display:block}</style></head><body>' + svg_text + '</body></html>'
    output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.set_content(html, wait_until='networkidle')
            page.wait_for_timeout(100)
            png_bytes = page.screenshot(type='png', full_page=False)
        finally:
            browser.close()
    output.write_bytes(png_bytes)
    return {'page': source.name, 'ok': True, 'path': str(output), 'bytes': len(png_bytes), 'all_background': is_all_background(png_bytes)}


def fetch_slide_text('''
    if needle not in text:
        raise BuildError("cannot connect managed rendering to visual_review.py")
    renderer.write_text(text.replace(needle, "\n" + helper, 1), encoding="utf-8")


def _validate_master(skill: Path, *, internal: bool) -> None:
    required = (("MASTER.md" if internal else "SKILL.md"), "scripts", "templates", "references", "workflows", "requirements.txt")
    for name in required:
        if not (skill / name).exists():
            raise BuildError(f"runtime missing {name}")
    if internal and any(skill.rglob("SKILL.md")):
        raise BuildError("internal Master runtime must not expose SKILL.md")
    if any(skill.rglob("install.py")):
        raise BuildError("internal Master runtime must not contain install.py")


def _purge(root: Path) -> None:
    for path in sorted(root.rglob("__pycache__"), reverse=True):
        if path.is_dir():
            shutil.rmtree(path)
    for path in root.rglob("*"):
        if path.is_file() and (any(part in FORBIDDEN_PARTS for part in path.parts) or path.suffix.lower() in FORBIDDEN_SUFFIXES):
            raise BuildError(f"forbidden bundle file: {path}")


def _runtime_smoke(skill: Path) -> None:
    scripts = skill / "scripts"
    files = sorted(scripts.rglob("*.py"))
    result = subprocess.run([sys.executable, "-m", "py_compile", *(str(path) for path in files)], capture_output=True, text=True)
    if result.returncode:
        raise BuildError(result.stderr or "py_compile failed")
    command = "import sys; sys.path.insert(0, {!r}); import project_manager, director_plan, production, visual_review, runtime_guard".format(str(scripts))
    result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True)
    if result.returncode:
        raise BuildError(result.stderr or "runtime import failed")


def _tree_hash(root: Path) -> str:
    files = [
        path for path in sorted(p for p in root.rglob("*") if p.is_file())
        if "__pycache__" not in path.parts and path.suffix.lower() != ".pyc"
    ]
    def row(path: Path) -> str:
        return f"{path.relative_to(root).as_posix()}:{digest(path)}"
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(files)))) as pool:
        rows = list(pool.map(row, files))
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _payload_files(root: Path) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}
        for path in sorted((root / "skills" / "ppt-prompt-router").rglob("*"))
        if path.is_file()
    ]


def _write_install_entry(stage: Path) -> None:
    entry = """#!/usr/bin/env python3
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'ppt-prompt-router'))
from scripts.offline_suite_runtime import main
if __name__ == '__main__':
    raise SystemExit(main())
"""
    (stage / "install.py").write_text(entry, encoding="utf-8")


def build(output_dir: Path) -> Path:
    if not VENDOR.is_dir():
        raise BuildError("vendor/ppt-master is missing; run sync-vendor first")
    _verify_vendor()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    master_commit = lock()["commit"]
    name = f"ppt-director-{version}-master-{master_commit[:7]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_parent = Path(tempfile.mkdtemp(prefix=".ppt-director-build-", dir=output_dir))
    stage = stage_parent / name
    try:
        router_skill = stage / "skills" / "ppt-prompt-router"
        shutil.copytree(
            ROOT,
            router_skill,
            ignore=shutil.ignore_patterns(
                ".git", ".github", "vendor", "dist", "docs", "tests", "projects", "integrations",
                "install.py", "__pycache__", ".DS_Store", "*.pyc", "build_offline_suite.py", "sync_master_overlay.py",
            ),
        )
        master_skill = router_skill / "runtime" / "ppt-master"
        master_skill.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(VENDOR / "skills" / "ppt-master", master_skill)
        closure = _apply_overlay(master_skill)
        _make_internal_master(master_skill)
        _validate_master(master_skill, internal=True)
        _runtime_smoke(master_skill)
        _purge(stage)
        (stage / "LICENSES").mkdir()
        shutil.copy2(VENDOR / "LICENSE", stage / "LICENSES" / "ppt-master-MIT.txt")
        _write_install_entry(stage)
        if len(list(stage.rglob("install.py"))) != 1:
            raise BuildError("offline suite must contain exactly one install.py")
        skill_files = list((stage / "skills").rglob("SKILL.md"))
        if skill_files != [router_skill / "SKILL.md"]:
            raise BuildError("offline suite must expose exactly one Skill")
        files = _payload_files(stage)
        for relative in ("install.py", "LICENSES/ppt-master-MIT.txt"):
            path = stage / relative
            files.append({"path": relative, "sha256": digest(path)})
        data = {
            "schema_version": "2.0",
            "suite_version": version,
            "router_baseline_commit": ROUTER_BASELINE,
            "master_baseline_commit": master_commit,
            "overlay_version": manifest()["overlay_version"],
            "overlay_hash": digest(OVERLAY_ROOT / "manifest.json"),
            "runtime_hash": _tree_hash(master_skill),
            "overlay_dependency_closure": closure,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "files": sorted(files, key=lambda item: item["path"]),
        }
        (stage / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "checksums.sha256").write_text("".join(f"{row['sha256']}  {row['path']}\n" for row in data["files"]), encoding="utf-8")
        final = output_dir / name
        archive = output_dir / f"{name}.zip"
        if final.exists() or archive.exists():
            raise BuildError(f"release output already exists: {final}")
        os.replace(stage, final)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as package:
            for path in sorted(p for p in final.rglob("*") if p.is_file()):
                package.write(path, path.relative_to(final.parent))
        return final
    finally:
        shutil.rmtree(stage_parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the PPT Director 4.0 Phase 1 offline suite")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync-vendor")
    sync.add_argument("--master-source", required=True)
    package = sub.add_parser("build")
    package.add_argument("--output-dir", default=str(ROOT / "dist"))
    args = parser.parse_args()
    try:
        if args.command == "sync-vendor":
            sync_vendor(Path(args.master_source))
            result = {"status": "VENDOR_SYNCED", "vendor": str(VENDOR)}
        else:
            result = {"status": "BUILT", "output": str(build(Path(args.output_dir).expanduser().resolve()))}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (BuildError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
