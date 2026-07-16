from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfflineSuite3Test(unittest.TestCase):
    def test_builder_and_installer_expose_one_skill_and_one_installer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-suite3-") as temp:
            output = Path(temp) / "dist"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_offline_suite.py"), "build", "--output-dir", str(output)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            bundle = Path(json.loads(result.stdout)["output"])
            self.assertEqual(list(bundle.rglob("install.py")), [bundle / "install.py"])
            self.assertEqual(list((bundle / "skills").rglob("SKILL.md")), [bundle / "skills" / "ppt-prompt-router" / "SKILL.md"])
            runtime = bundle / "skills" / "ppt-prompt-router" / "runtime" / "ppt-master"
            self.assertTrue((runtime / "MASTER.md").is_file())
            self.assertFalse(any(runtime.rglob("SKILL.md")))

            skills = Path(temp) / "中文 skills"
            for command in ("install", "validate", "upgrade", "rollback"):
                installed = subprocess.run(
                    [sys.executable, str(bundle / "install.py"), command, "--host", "generic", "--skills-dir", str(skills)],
                    cwd=temp, capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            managed = Path(temp) / "managed"; (managed / "analysis").mkdir(parents=True)
            (managed / "analysis" / "director_contract.json").write_text("{}", encoding="utf-8")
            direct_export = subprocess.run(
                [sys.executable, str(skills / "ppt-prompt-router" / "runtime" / "ppt-master" / "scripts" / "svg_to_pptx.py"), str(managed)],
                cwd=temp, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(direct_export.returncode, 3, direct_export.stdout + direct_export.stderr)
            self.assertIn("use scripts/route.py", direct_export.stderr)
            removed = subprocess.run(
                [sys.executable, str(bundle / "install.py"), "uninstall", "--host", "generic", "--skills-dir", str(skills), "--yes"],
                cwd=temp, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            self.assertFalse((skills / "ppt-prompt-router").exists())

    def test_nonmanaged_master_conflict_causes_zero_install_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-suite3-conflict-") as temp:
            output = Path(temp) / "dist"
            built = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_offline_suite.py"), "build", "--output-dir", str(output)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            bundle = Path(json.loads(built.stdout)["output"])
            skills = Path(temp) / "skills"; master = skills / "ppt-master"; master.mkdir(parents=True)
            (master / "SKILL.md").write_text("---\nname: ppt-master\n---\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(bundle / "install.py"), "install", "--host", "generic", "--skills-dir", str(skills)],
                cwd=temp, capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn('"status": "CONFLICT"', result.stdout)
            self.assertFalse((skills / "ppt-prompt-router").exists())
            self.assertTrue((master / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
