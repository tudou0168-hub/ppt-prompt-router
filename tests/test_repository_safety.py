from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".txt"}
FORBIDDEN_TEXT = ("/" + "Users/", "五" + "寨")
FORBIDDEN_SUFFIXES = {".pptx", ".docx", ".pdf", ".zip", ".mp4", ".mp3", ".png", ".jpg", ".jpeg"}
VENDOR_FORBIDDEN_SUFFIXES = {".pptx", ".potx", ".ppsx", ".docx", ".pdf", ".zip", ".mp4", ".mp3"}
IGNORED_PARTS = {"projects", ".git", "__pycache__"}


class RepositorySafetyTest(unittest.TestCase):
    def test_no_customer_or_personal_path_in_publishable_text(self) -> None:
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            for marker in FORBIDDEN_TEXT:
                self.assertNotIn(marker, content, msg=str(path))

    def test_no_publishable_binary_or_large_file(self) -> None:
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
                continue
            is_vendor = path.is_relative_to(ROOT / "vendor")
            self.assertNotIn(
                path.suffix.lower(),
                VENDOR_FORBIDDEN_SUFFIXES if is_vendor else FORBIDDEN_SUFFIXES,
                msg=str(path),
            )
            self.assertLessEqual(path.stat().st_size, 5 * 1024 * 1024, msg=str(path))
