from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from install import (
    apply_master_overlay,
    deploy_runtime_master,
    find_ppt_master_skill_dir,
    install_package,
    prepare_master_source,
    uninstall_master_overlay,
    validate_package_root,
    verify_runtime_integration,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_lock(package: Path) -> None:
    (package / "integrations" / "ppt-master" / "upstream.lock").write_text(
        json.dumps({"repository": "https://github.com/example/ppt-master.git", "commit": "a" * 40, "required_capabilities": ["router-accept"]}),
        encoding="utf-8",
    )


def create_master_fixture(root: Path) -> tuple[Path, Path]:
    package = root / "package"
    source = root / "source" / "skills" / "ppt-master"
    (source / "scripts").mkdir(parents=True)
    (source / "SKILL.md").write_text("skill\n", encoding="utf-8")
    (source / "scripts" / "project_manager.py").write_text("base\n", encoding="utf-8")
    overlay = package / "integrations" / "ppt-master" / "overlay" / "skills" / "ppt-master" / "scripts"
    overlay.mkdir(parents=True)
    changed = overlay / "project_manager.py"
    changed.write_text("overlay\n", encoding="utf-8")
    manifest = {"files": [{
        "path": "skills/ppt-master/scripts/project_manager.py",
        "upstream_hash": digest(source / "scripts" / "project_manager.py"),
        "overlay_hash": digest(changed),
    }]}
    metadata = package / "integrations" / "ppt-master"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_lock(package)
    (package / "VERSION").write_text("2.1.0\n", encoding="utf-8")
    return package, source.parents[1]


def zip_tree(source: Path) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, Path("ppt-master-test") / path.relative_to(source))
    return output.getvalue()


class InstallTest(unittest.TestCase):
    def test_copy_install_and_validate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-install-") as tmp:
            target = Path(tmp) / "skills"
            destination = install_package(target, source_root=ROOT)
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertFalse((destination / "projects").exists())
            validate_package_root(destination)

    def test_overlay_apply_and_uninstall_restore(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-overlay-") as tmp:
            root = Path(tmp)
            package = root / "package"
            overlay = package / "integrations" / "ppt-master" / "overlay" / "skills" / "ppt-master"
            target = root / "master" / "skills" / "ppt-master"
            target.mkdir(parents=True)
            base = target / "existing.py"
            base.write_text("base\n", encoding="utf-8")
            source = overlay / "existing.py"
            source.parent.mkdir(parents=True)
            source.write_text("overlay\n", encoding="utf-8")
            added = overlay / "new.py"
            added.write_text("new\n", encoding="utf-8")
            manifest = {
                "files": [
                    {"path": "skills/ppt-master/existing.py", "upstream_hash": digest(base), "overlay_hash": digest(source)},
                    {"path": "skills/ppt-master/new.py", "upstream_hash": None, "overlay_hash": digest(added)},
                ]
            }
            (package / "integrations" / "ppt-master").mkdir(parents=True, exist_ok=True)
            (package / "integrations" / "ppt-master" / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            write_lock(package)
            (package / "VERSION").write_text("2.1.0\n", encoding="utf-8")
            apply_master_overlay(package, root / "master")
            self.assertEqual(base.read_text(encoding="utf-8"), "overlay\n")
            self.assertTrue((target / "new.py").is_file())
            uninstall_master_overlay(root / "master")
            self.assertEqual(base.read_text(encoding="utf-8"), "base\n")
            self.assertFalse((target / "new.py").exists())

    def test_overlay_rejects_changed_upstream(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-overlay-") as tmp:
            root = Path(tmp)
            package = root / "package"
            overlay = package / "integrations" / "ppt-master" / "overlay" / "skills" / "ppt-master"
            target = root / "master" / "skills" / "ppt-master"
            target.mkdir(parents=True)
            base = target / "existing.py"
            base.write_text("changed\n", encoding="utf-8")
            source = overlay / "existing.py"
            source.parent.mkdir(parents=True)
            source.write_text("overlay\n", encoding="utf-8")
            manifest = {"files": [{"path": "skills/ppt-master/existing.py", "upstream_hash": hashlib.sha256(b"base\n").hexdigest(), "overlay_hash": digest(source)}]}
            (package / "integrations" / "ppt-master").mkdir(parents=True, exist_ok=True)
            (package / "integrations" / "ppt-master" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            write_lock(package)
            (package / "VERSION").write_text("2.1.0\n", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "does not match upstream.lock"):
                apply_master_overlay(package, root / "master")
            self.assertEqual(base.read_text(encoding="utf-8"), "changed\n")

    def test_local_zip_with_chinese_windows_style_path_deploys_runtime(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-安装-") as tmp:
            root = Path(tmp)
            package, master = create_master_fixture(root)
            source_zip = root / "中文 空格" / "上游.zip"
            source_zip.parent.mkdir()
            source_zip.write_bytes(zip_tree(master))
            stage = root / "临时目录"
            prepared, verification = prepare_master_source(package, stage, source_zip=str(source_zip))
            apply_master_overlay(package, prepared)
            target = root / "Claude Skills 中文"
            deploy_runtime_master(package, prepared, target, verification, force=False)
            status = verify_runtime_integration(package, target)
            self.assertEqual(status["status"], "verified")
            self.assertEqual((target / "ppt-master" / "scripts" / "project_manager.py").read_text(encoding="utf-8"), "overlay\n")

    def test_local_source_directory_is_copied_before_overlay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-local-source-") as tmp:
            root = Path(tmp)
            package, master = create_master_fixture(root)
            prepared, verification = prepare_master_source(package, root / "stage", source_dir=str(master))
            self.assertEqual(verification["source"], "local_directory")
            self.assertNotEqual(prepared, master)
            apply_master_overlay(package, prepared)
            self.assertEqual((master / "skills" / "ppt-master" / "scripts" / "project_manager.py").read_text(encoding="utf-8"), "base\n")

    def test_codeload_zip_source_does_not_require_git(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-codeload-") as tmp:
            root = Path(tmp)
            package, master = create_master_fixture(root)
            archive = zip_tree(master)
            with patch("urllib.request.urlopen", return_value=io.BytesIO(archive)):
                prepared, verification = prepare_master_source(package, root / "stage", codeload_url="https://codeload.example.test/master.zip")
            self.assertEqual(verification["source"], "codeload_zip")
            self.assertFalse((prepared / ".git").exists())

    def test_router_can_discover_host_runtime_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-runtime-") as tmp:
            skills = Path(tmp) / "Claude" / "skills"
            manager = skills / "ppt-master" / "scripts" / "project_manager.py"
            manager.parent.mkdir(parents=True)
            manager.write_text("# placeholder\n", encoding="utf-8")
            self.assertEqual(
                find_ppt_master_skill_dir(str(skills)),
                (skills / "ppt-master").resolve(strict=False),
            )

    @unittest.skipUnless(os.name == "nt", "仅在 Windows 验证盘符路径")
    def test_windows_drive_path_install_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-windows-") as tmp:
            root = Path(tmp)
            package, master = create_master_fixture(root)
            prepared, verification = prepare_master_source(package, root / "阶段目录", source_dir=str(master))
            self.assertEqual(verification["source"], "local_directory")
            self.assertTrue((prepared / "skills" / "ppt-master").is_dir())
