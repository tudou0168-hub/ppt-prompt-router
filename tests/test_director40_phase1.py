from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import director_runtime


ROOT = Path(__file__).resolve().parents[1]
OVERLAY_SCRIPTS = ROOT / "integrations" / "ppt-master" / "overlay" / "skills" / "ppt-master" / "scripts"
if str(OVERLAY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OVERLAY_SCRIPTS))
production = importlib.import_module("production")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def plan() -> dict:
    pages = []
    for number, role in enumerate(("key_finding", "mechanism", "architecture", "action"), start=1):
        pages.append({
            "page_id": f"P{number:02d}", "page_role": role,
            "page_intent": f"说明第{number}个关键判断", "required_messages": ["结论", "依据"],
            "source_refs": ["sources/source.md#H:事实"], "factual_constraints": ["不得新增事实"],
            "unresolved_questions": [],
        })
    return {
        "schema_version": "3.1", "content_map": {"core_argument": "形成统一判断"},
        "fact_boundary": {"rule": "source only"}, "storyline": {"logic": "判断—机制—架构—行动"},
        "pages": pages,
        "sample_pages": [
            {"page_id": "P01", "sample_role": "density", "expression_task": "information_density", "reason": "信息密度最高"},
            {"page_id": "P02", "sample_role": "relationship", "expression_task": "complex_relationship", "reason": "机制关系复杂"},
            {"page_id": "P03", "sample_role": "signature", "expression_task": "visual_signature", "reason": "视觉签名页"},
        ],
    }


def genome() -> dict:
    return {
        "visual_direction": "克制、层次清晰的政务叙事", "template_inheritance": "延续有效模板证据的设计语言",
        "color_system": "深蓝与留白", "font_system": "清晰中文无衬线", "canvas": "16:9",
        "safe_margins": "统一安全边距", "information_hierarchy": "结论先行，证据分层",
        "image_strategy": "只使用任务相关图像", "relationship_principles": "以内容语义决定关系表达",
        "page_rhythm": "结论、机制、架构、行动递进",
        "design_probes": [
            {"page_id": "P01", "expression_task": "information_density"},
            {"page_id": "P02", "expression_task": "complex_relationship"},
            {"page_id": "P03", "expression_task": "visual_signature"},
        ],
        "page_visual_tasks": [
            {"page_id": "P01", "task": "让高密度证据服务单一结论"},
            {"page_id": "P02", "task": "清楚解释机制关系"},
            {"page_id": "P03", "task": "形成项目视觉记忆点"},
        ],
    }


def make_project(root: Path, mode: str = "standard") -> Path:
    project = root / "phase1-project"
    for relative in ("analysis", "sources", ".director", ".page_work", ".preview", ".review", "svg_output", "notes", "exports"):
        (project / relative).mkdir(parents=True, exist_ok=True)
    source = project / "sources" / "source.md"
    source.write_text("# 事实\n2026年推进改革。\n", encoding="utf-8")
    write_json(project / "analysis" / "director_contract.json", {
        "request": "形成政务汇报", "audience": "决策者", "purpose": "决策", "page_count": 4,
        "profile": {"id": "government_strategy"},
        "source_files": [{"path": str(source), "sha256": director_runtime.sha256(source)}],
        "template": {"path": None, "sha256": None},
    })
    (project / "analysis" / "director_profile.md").write_text("profile", encoding="utf-8")
    write_json(project / ".director" / "generation_mode.json", {"mode": mode, "sample_strategy": "design_probes"})
    production.initialize_project(project)
    return project


class Phase1Test(unittest.TestCase):
    def _registered_project(self, root: Path) -> Path:
        project = make_project(root)
        candidate = root / "director_plan.json"; write_json(candidate, plan())
        director_runtime.submit_role_artifact(project, role="content_strategist", artifact=candidate)
        production.register_director_plan(project)
        return project

    def test_context_is_role_scoped_and_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = self._registered_project(Path(temp))
            with self.assertRaisesRegex(director_runtime.DirectorRuntimeError, "brief approval"):
                director_runtime.assemble_role_context(project, role="visual_director", runtime_root=ROOT / "runtime" / "ppt-master")
            production.approve_phase1(project, "brief", "A")
            first = director_runtime.assemble_role_context(project, role="visual_director", runtime_root=ROOT / "runtime" / "ppt-master")
            second = director_runtime.assemble_role_context(project, role="visual_director", runtime_root=ROOT / "runtime" / "ppt-master")
            self.assertEqual(first["path"], second["path"])
            payload = json.loads(Path(second["path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["role"], "visual_director")
            input_paths = [item.get("path", "") for item in payload["inputs"] if isinstance(item, dict)]
            self.assertFalse(any("production_state" in path for path in input_paths))
            self.assertFalse(any("capability_snapshot" in path for path in input_paths))

    def test_submit_rejects_role_ownership_and_genome_forbidden_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = self._registered_project(Path(temp))
            candidate = Path(temp) / "bad.json"; write_json(candidate, plan())
            with self.assertRaisesRegex(director_runtime.DirectorRuntimeError, "cannot submit"):
                director_runtime.submit_role_artifact(project, role="director", artifact=candidate)
            bad = genome(); bad["column_count"] = 3
            write_json(candidate, bad)
            with self.assertRaisesRegex(director_runtime.DirectorRuntimeError, "forbidden"):
                director_runtime.submit_role_artifact(project, role="visual_director", artifact=candidate)

    def test_brief_genome_compilation_and_semantic_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); project = self._registered_project(root)
            baseline = director_runtime.semantic_plan_hashes(project)
            production.approve_phase1(project, "brief", "A")
            candidate = root / "design_genome.json"; write_json(candidate, genome())
            director_runtime.submit_role_artifact(project, role="visual_director", artifact=candidate)
            locked = production.lock_spec(project)
            self.assertEqual(locked["stage"], "sample_production")
            self.assertIn(director_runtime.sha256(project / "design_genome.json"), (project / "spec_lock.md").read_text(encoding="utf-8"))
            value = plan(); value["pages"][3]["page_intent"] = "更新行动意图"
            write_json(project / "analysis" / "director_plan.json", value)
            changed = director_runtime.semantic_plan_hashes(project)
            self.assertEqual(baseline["deck_plan_hash"], changed["deck_plan_hash"])
            self.assertNotEqual(baseline["page_semantic_hashes"]["P04"], changed["page_semantic_hashes"]["P04"])

    def test_design_approval_and_page_approval_are_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); project = self._registered_project(root)
            production.approve_phase1(project, "brief", "A")
            candidate = root / "design_genome.json"; write_json(candidate, genome())
            director_runtime.submit_role_artifact(project, role="visual_director", artifact=candidate)
            production.lock_spec(project)
            state = production._load(project)
            for page_id in state["samples"]["page_ids"]:
                state["pages"][page_id]["state"] = "passed"
                state["pages"][page_id]["review_passed"] = True
            state["stage"] = "sample_confirmation"; production._save(project, state)
            approved = production.approve_phase1(project, "design", "A")
            self.assertEqual(approved["stage"], "production")
            with self.assertRaisesRegex(production.ProductionError, "host_user_message"):
                production.approve_phase1(project, "page", "A", source="host_user_message")

    def test_template_profile_reference_and_external_context_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as snapshots:
            root = Path(temp); project = make_project(root, mode="template")
            template = project / "references" / "template.pptx"; template.parent.mkdir(exist_ok=True); template.write_bytes(b"pptx")
            contract_path = project / "analysis" / "director_contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["template"] = {"path": str(template), "sha256": director_runtime.sha256(template)}
            write_json(contract_path, contract)
            artifact = project / "analysis" / "template-reference.png"; artifact.write_bytes(b"png")
            profile = root / "profile.json"
            write_json(profile, {
                "visual_identity": "政务蓝", "spatial_grammar": "留白", "page_archetypes": [],
                "relationship_patterns": [], "image_treatment": "克制", "reusable_components": [],
                "reference_slides": [{"path": "analysis/template-reference.png", "sha256": director_runtime.sha256(artifact)}],
            })
            director_runtime.submit_role_artifact(project, role="template_analyst", artifact=profile)
            old = os.environ.get("PPT_DIRECTOR_CONTEXT_SNAPSHOT_DIR")
            os.environ["PPT_DIRECTOR_CONTEXT_SNAPSHOT_DIR"] = snapshots
            try:
                result = director_runtime.assemble_role_context(project, role="template_analyst", runtime_root=ROOT / "runtime" / "ppt-master")
            finally:
                if old is None:
                    os.environ.pop("PPT_DIRECTOR_CONTEXT_SNAPSHOT_DIR", None)
                else:
                    os.environ["PPT_DIRECTOR_CONTEXT_SNAPSHOT_DIR"] = old
            self.assertTrue(Path(result["path"]).is_file())
            self.assertTrue(list(Path(snapshots).rglob("*.json")))


if __name__ == "__main__":
    unittest.main()
