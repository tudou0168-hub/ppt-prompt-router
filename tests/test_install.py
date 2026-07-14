from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from install import apply_master_overlay, install_package, uninstall_master_overlay, validate_package_root


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            (root / "master" / ".git").mkdir(parents=True)
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
            (root / "master" / ".git").mkdir(parents=True)
            target.mkdir(parents=True)
            base = target / "existing.py"
            base.write_text("changed\n", encoding="utf-8")
            source = overlay / "existing.py"
            source.parent.mkdir(parents=True)
            source.write_text("overlay\n", encoding="utf-8")
            manifest = {"files": [{"path": "skills/ppt-master/existing.py", "upstream_hash": hashlib.sha256(b"base\n").hexdigest(), "overlay_hash": digest(source)}]}
            (package / "integrations" / "ppt-master").mkdir(parents=True, exist_ok=True)
            (package / "integrations" / "ppt-master" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (package / "VERSION").write_text("2.1.0\n", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "upstream hash mismatch"):
                apply_master_overlay(package, root / "master")
            self.assertEqual(base.read_text(encoding="utf-8"), "changed\n")
