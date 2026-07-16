from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERLAY_SCRIPTS = ROOT / "integrations" / "ppt-master" / "overlay" / "skills" / "ppt-master" / "scripts"
sys.path.insert(0, str(OVERLAY_SCRIPTS))
sys.path.insert(1, str(ROOT / "vendor" / "ppt-master" / "skills" / "ppt-master" / "scripts"))

director_plan = importlib.import_module("director_plan")
production = importlib.import_module("production")
fact_guard = importlib.import_module("fact_guard")
profile_typography = importlib.import_module("profile_typography")
runtime_guard = importlib.import_module("runtime_guard")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def make_project(root: Path, pages: int = 4) -> tuple[Path, dict]:
    project = root / "项目 中文"
    for rel in ("analysis", "sources", "svg_output", "notes", ".preview", ".review", ".page_work", "exports"):
        (project / rel).mkdir(parents=True, exist_ok=True)
    source = project / "sources" / "材料.md"
    source.write_text("# 事实依据\n2026年由市政务服务中心启动，目标覆盖90%。\n" + "依据内容。\n" * 30, encoding="utf-8")
    contract = {
        "schema_version": "3.0", "profile": {"id": "government_strategy", "sha256": "x"},
        "page_count": pages, "template": {"intent": "none", "path": None},
    }
    write_json(project / "analysis" / "director_contract.json", contract)
    (project / "analysis" / "director_profile.md").write_text("profile", encoding="utf-8")
    production.initialize_project(project)
    page_rows = []
    for index in range(1, pages + 1):
        page_rows.append({
            "page_id": f"P{index:02d}", "chapter": "判断", "page_goal": f"goal {index}",
            "key_message": f"message {index}", "relationship_type": ("comparison", "process", "hierarchy", "timeline")[index - 1],
            "visual_anchor": ("matrix", "flow", "architecture", "roadmap")[index - 1],
            "image_strategy": "custom svg", "evidence_refs": ["sources/材料.md#H:事实依据"],
            "risk_tags": [], "rhythm_role": ("anchor", "build", "explain", "close")[index - 1],
        })
    plan = {
        "content_map": {"core_argument": "x"}, "fact_boundary": {"rule": "source"},
        "storyline": {"logic": "reorganized"}, "pages": page_rows,
        "sample_pages": [
            {"page_id": "P01", "risk_type": "information_density", "reason": "card stacking risk"},
            {"page_id": "P02", "risk_type": "complex_relationship", "reason": "dense process"},
            {"page_id": "P03", "risk_type": "visual_signature", "reason": "signature visual"},
        ],
    }
    candidate = root / "candidate.json"
    write_json(candidate, plan)
    director_plan.install_director_plan(project, candidate)
    return project, plan


def make_project31(root: Path) -> tuple[Path, dict]:
    project = root / "3.1 项目"
    for rel in ("analysis", "sources", "svg_output", "notes", ".preview", ".review", ".page_work", ".director", "exports"):
        (project / rel).mkdir(parents=True, exist_ok=True)
    source = project / "sources" / "材料.md"
    source.write_text("# 事实依据\n2026年启动。\n" + "复杂事实。\n" * 10, encoding="utf-8")
    write_json(project / "analysis" / "director_contract.json", {
        "schema_version": "3.1", "profile": {"id": "government_strategy", "sha256": "x"},
        "page_count": 4, "template": {"intent": "reference_elements", "path": "references/template.pptx", "sha256": "template-hash"},
    })
    (project / "analysis" / "director_profile.md").write_text("profile", encoding="utf-8")
    write_json(project / ".director" / "generation_mode.json", {"mode": "template", "sample_strategy": "three_groups"})
    production.initialize_project(project)
    pages = [
        {"page_id": "P01", "page_role": "cover", "page_intent": "建立汇报主题", "required_messages": ["主题"], "source_refs": [], "factual_constraints": [], "unresolved_questions": []},
        {"page_id": "P02", "page_role": "key_finding", "page_intent": "形成核心判断", "required_messages": ["判断"], "source_refs": ["sources/材料.md#H:事实依据"], "factual_constraints": ["年份需有来源"], "unresolved_questions": []},
        {"page_id": "P03", "page_role": "architecture", "page_intent": "解释复杂架构关系", "required_messages": ["能力层", "业务层", "治理层"], "source_refs": ["sources/材料.md#H:事实依据"], "factual_constraints": ["不得新增机构"], "unresolved_questions": []},
        {"page_id": "P04", "page_role": "action", "page_intent": "明确行动", "required_messages": ["行动"], "source_refs": ["sources/材料.md#H:事实依据"], "factual_constraints": [], "unresolved_questions": []},
    ]
    plan = {
        "schema_version": "3.1", "content_map": {"core_argument": "x"}, "fact_boundary": {"rule": "source"},
        "storyline": {"logic": "reorganized"}, "pages": pages,
        "sample_pages": [
            {"page_id": "P01", "sample_role": "overview", "reason": "验证封面与总体方向"},
            {"page_id": "P03", "sample_role": "complex", "reason": "验证复杂关系表达"},
        ],
    }
    candidate = root / "candidate31.json"; write_json(candidate, plan)
    director_plan.install_director_plan(project, candidate)
    return project, plan


class DirectorPlanAndProductionTest(unittest.TestCase):
    def test_template_plan_uses_one_overview_and_one_complex_page(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-plan-") as temp:
            project, plan = make_project31(Path(temp))
            state = production._load(project)
            self.assertEqual(state["samples"]["strategy"], "three_groups")
            self.assertEqual(state["samples"]["page_ids"], ["P01", "P03"])
            self.assertEqual(set(state["samples"]["directions"]), {"A", "B", "C"})
            self.assertNotIn("visual_anchor", plan["pages"][2])

            invalid = json.loads(json.dumps(plan))
            invalid["sample_pages"][1]["page_id"] = "P02"
            invalid["pages"][1]["page_role"] = "plain_text"
            with self.assertRaisesRegex(director_plan.DirectorPlanError, "complex sample"):
                director_plan.validate_director_plan(project, invalid)

    def test_grouped_samples_require_identical_inputs_and_distinct_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-groups-") as temp:
            project, _ = make_project31(Path(temp))
            state = production._load(project)
            for direction in ("A", "B", "C"):
                for page_id in state["samples"]["page_ids"]:
                    svg, png, review = production._sample_paths(project, state, direction, page_id)
                    svg.parent.mkdir(parents=True, exist_ok=True); png.parent.mkdir(parents=True, exist_ok=True); review.parent.mkdir(parents=True, exist_ok=True)
                    svg.write_text("<svg/>", encoding="utf-8"); png.write_bytes(b"same"); write_json(review, {"status": "ok"})
                    record = production._sample_record(state, direction, page_id)
                    record.update({
                        "state": "passed", "svg_hash": production._sha256(svg), "png_hash": production._sha256(png),
                        "review_report_hash": production._sha256(review), "reviewed_png_hash": production._sha256(png),
                        "review_passed": True, "blocking_issues": [], "input_hash": f"input-{page_id}",
                    })
            with self.assertRaisesRegex(production.ProductionError, "duplicate artifacts"):
                production._validate_grouped_samples(project, state)

            for direction in ("A", "B", "C"):
                for page_id in state["samples"]["page_ids"]:
                    svg, png, review = production._sample_paths(project, state, direction, page_id)
                    svg.write_text(f"<svg>{direction}-{page_id}</svg>", encoding="utf-8")
                    png.write_bytes(f"{direction}-{page_id}".encode())
                    record = production._sample_record(state, direction, page_id)
                    record.update({"svg_hash": production._sha256(svg), "png_hash": production._sha256(png), "reviewed_png_hash": production._sha256(png)})
            fingerprints = production._validate_grouped_samples(project, state)
            self.assertEqual(len(set(fingerprints.values())), 3)
            production._sample_record(state, "C", "P03")["input_hash"] = "different-content"
            with self.assertRaisesRegex(production.ProductionError, "content inputs differ"):
                production._validate_grouped_samples(project, state)

    def test_state_has_exact_top_level_and_samples_block_full_production(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project, _ = make_project(Path(temp))
            state = json.loads((project / "analysis" / "production_state.json").read_text(encoding="utf-8"))
            self.assertEqual(set(state), production.TOP_LEVEL_FIELDS)
            self.assertEqual(state["stage"], "design_pending")
            (project / "design_spec.md").write_text("design", encoding="utf-8")
            (project / "spec_lock.md").write_text("minimum_font_sizes: body=20px supporting=16px footnote=12px", encoding="utf-8")
            production.lock_spec(project)
            with self.assertRaisesRegex(production.ProductionError, "only selected samples"):
                production.begin_page(project, "P04", ROOT, ROOT)
            result = production.begin_page(project, "P01", ROOT, ROOT)
            self.assertEqual(result["director_requirements"]["relationship_type"], "comparison")

    def test_sample_confirmation_a_b_c_semantics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project, _ = make_project(Path(temp))
            state = production._load(project)
            state["stage"] = "sample_confirmation"
            for page_id in state["samples"]["page_ids"]:
                (project / "svg_output" / f"{page_id}.svg").write_text("<svg/>", encoding="utf-8")
                (project / ".preview" / f"{page_id}.png").write_bytes(b"png")
                write_json(project / ".review" / f"{page_id}.json", {"status": "ok"})
                state["pages"][page_id].update({
                    "state": "passed",
                    "svg_hash": production._sha256(project / "svg_output" / f"{page_id}.svg"),
                    "png_hash": production._sha256(project / ".preview" / f"{page_id}.png"),
                    "review_report_hash": production._sha256(project / ".review" / f"{page_id}.json"),
                })
            production._save(project, state)
            approved = production.sample_confirm(project, "A")
            self.assertEqual(approved["stage"], "production")

            state = production._load(project); state["stage"] = "sample_confirmation"; production._save(project, state)
            revised = production.sample_confirm(project, "B", page_id="P02")
            self.assertEqual(revised["stage"], "sample_production")
            self.assertEqual(production._load(project)["pages"]["P02"]["state"], "repair_required")

            state = production._load(project); state["stage"] = "sample_confirmation"; production._save(project, state)
            changed = production.sample_confirm(project, "C", replacements=["P02", "P03", "P04"])
            self.assertEqual(changed["stage"], "design_pending")
            self.assertIsNone(production._load(project)["global_hashes"]["spec_lock_hash"])
            self.assertEqual([item["page_id"] for item in director_plan.load_plan(project)["sample_pages"]], ["P02", "P03", "P04"])

    def test_midpoint_returns_to_production_then_deck_becomes_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project, plan = make_project(Path(temp))
            state = production._load(project)
            for page in plan["pages"]:
                state["pages"][page["page_id"]]["state"] = "passed"
            state["stage"] = "midpoint_required"
            production._save(project, state)
            reviewed = production._review_expected(project, state, "midpoint")
            result = production.record_review(project, "midpoint", "passed", reviewed_pages=reviewed)
            self.assertEqual(result["stage"], "production")
            self.assertEqual(production.status(project)["stage"], "deck_review_required")

    def test_svg_notes_and_exported_inputs_invalidate_downstream_hashes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project, _ = make_project(Path(temp))
            state = production._load(project)
            page_id = "P01"
            svg = project / "svg_output" / f"{page_id}.svg"; svg.write_text("<svg/>", encoding="utf-8")
            png = project / ".preview" / f"{page_id}.png"; png.write_bytes(b"png")
            review = project / ".review" / f"{page_id}.json"; write_json(review, {"status": "ok"})
            state["pages"][page_id].update({
                "state": "passed", "svg_hash": production._sha256(svg),
                "png_hash": production._sha256(png), "review_report_hash": production._sha256(review),
                "reviewed_png_hash": production._sha256(png), "review_passed": True,
            })
            state["samples"].update({"status": "approved", "approved_hashes": {page_id: production._sample_snapshot(project, page_id)}})
            state["stage"] = "exported"
            production._save(project, state)
            svg.write_text("<svg><!-- changed --></svg>", encoding="utf-8")
            result = production.status(project)
            self.assertEqual(result["stage"], "repair_required")
            record = production._load(project)["pages"][page_id]
            self.assertIsNone(record["png_hash"])
            self.assertIsNone(record["review_report_hash"])
            self.assertFalse(record["review_passed"])

            state = production._load(project)
            state["pages"]["P02"].update({"state": "passed", "notes_hash": None, "review_passed": True})
            production._save(project, state)
            (project / "notes" / "P02.md").write_text("new notes", encoding="utf-8")
            production.status(project)
            self.assertEqual(production._load(project)["pages"]["P02"]["state"], "repair_required")

    def test_director_plan_is_not_overwritten_and_evidence_is_project_bound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            root = Path(temp); project, plan = make_project(root)
            candidate = root / "second.json"; write_json(candidate, plan)
            with self.assertRaisesRegex(director_plan.DirectorPlanError, "immutable"):
                director_plan.install_director_plan(project, candidate)
            resolved = director_plan.resolve_evidence_ref(project, "sources/材料.md#H:事实依据")
            self.assertIn("2026年", resolved["text"])
            with self.assertRaises(director_plan.DirectorPlanError):
                director_plan.resolve_evidence_ref(project, "../outside.md#L1-L1")


class GuardAndQualityTest(unittest.TestCase):
    def test_runtime_guard_blocks_managed_project_without_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project = Path(temp) / "project"; (project / "analysis").mkdir(parents=True)
            write_json(project / "analysis" / "director_contract.json", {})
            with self.assertRaises(SystemExit) as blocked:
                runtime_guard.enforce_cli("internal.py", [str(project)])
            self.assertEqual(blocked.exception.code, 3)

    def test_effective_font_size_uses_parent_transform_and_tspan_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project = Path(temp) / "project"; (project / "analysis").mkdir(parents=True); (project / ".page_work").mkdir()
            write_json(project / "analysis" / "director_contract.json", {"profile": {"id": "government_strategy"}})
            svg = project / ".page_work" / "current.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><g transform="scale(2)"><text font-size="10">合格</text><text font-size="10"><tspan font-size="7">过小</tspan></text></g></svg>', encoding="utf-8")
            errors = profile_typography.effective_font_size_errors(svg)
            self.assertTrue(any("14.00px" in error for error in errors), errors)
            self.assertFalse(any("合格" in error for error in errors), errors)
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="640" height="360"><text font-size="40">根视口合格</text><text y="80" font-size="30">根视口过小</text></svg>', encoding="utf-8")
            errors = profile_typography.effective_font_size_errors(svg)
            self.assertFalse(any("根视口合格" in error for error in errors), errors)
            self.assertTrue(any("15.00px" in error and "根视口过小" in error for error in errors), errors)

    def test_fact_gate_scans_svg_and_notes_and_allows_labeled_targets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director3-") as temp:
            project, _ = make_project(Path(temp))
            (project / "svg_output" / "P01.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><text font-size="20">2025年增长38%</text></svg>', encoding="utf-8")
            (project / "notes" / "P02.md").write_text("由市大数据局负责。", encoding="utf-8")
            (project / "svg_output" / "P03.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><text font-size="20">[目标] 2027年覆盖90%</text></svg>', encoding="utf-8")
            (project / "svg_output" / "P04.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><text font-size="20">行动</text></svg>', encoding="utf-8")
            (project / "notes" / "total.md").write_text("# P04\n案例使效率提升50%。\n", encoding="utf-8")
            issues = fact_guard.scan_deck_facts(project)
            self.assertTrue(any(item["page_id"] == "P01" for item in issues), issues)
            self.assertTrue(any(item["page_id"] == "P02" for item in issues), issues)
            self.assertFalse(any(item["page_id"] == "P03" for item in issues), issues)
            self.assertTrue(any(item["page_id"] == "P04" for item in issues), issues)


if __name__ == "__main__":
    unittest.main()
