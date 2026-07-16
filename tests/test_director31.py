from __future__ import annotations

import json
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import director_runtime, route


ROOT = Path(__file__).resolve().parents[1]
OVERLAY_SCRIPTS = ROOT / "integrations" / "ppt-master" / "overlay" / "skills" / "ppt-master" / "scripts"
if str(OVERLAY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OVERLAY_SCRIPTS))
production = importlib.import_module("production")
director_plan = importlib.import_module("director_plan")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def make_runtime(root: Path) -> Path:
    runtime = root / "runtime" / "ppt-master"
    scripts = runtime / "scripts"
    (scripts / "svg_to_pptx" / "pptx_package").mkdir(parents=True)
    for package in (scripts / "svg_to_pptx", scripts / "svg_to_pptx" / "pptx_package"):
        (package / "__init__.py").write_text("", encoding="utf-8")
    tool = """from __future__ import annotations
import argparse
from pathlib import Path

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('input', nargs='?')
    parser.add_argument('-o', '--output')
    parser.add_argument('--icons-dir')
    parser.add_argument('--inplace', action='store_true')
    parser.add_argument('--id-prefix')
    parser.add_argument('--min-decoration-bytes')
    parser.add_argument('--clean-stale', action='store_true')
    args = parser.parse_args(argv)
    if args.output:
        output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
        (output / 'manifest.json').write_text('{}', encoding='utf-8')
        (output / 'native_structure.json').write_text('{}', encoding='utf-8')
        (output / 'summary.md').write_text('# Summary', encoding='utf-8')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
"""
    tools = {
        "svg_quality_checker.py": tool,
        "visual_review.py": tool,
        "pptx_intake.py": tool,
        "pptx_template_import.py": tool,
        "svg_authoring_view.py": tool,
        "extract_svg_assets.py": tool,
        "production.py": tool,
        "svg_to_pptx/pptx_package/cli.py": tool,
    }
    for relative, content in tools.items():
        path = scripts / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    documents = {
        "MASTER.md": "# Master\nStrategist creates design_spec. Executor authors each SVG page. Template source_profile analysis is required.\n",
        "references/strategist.md": "# Strategist\nCreate design_spec and inspect template source_profile before planning.\n",
        "references/executor-base.md": "# Executor\nAuthor one complete SVG page at a time and inspect its rendered result.\n",
        "references/shared-standards.md": "# Standards\nEach SVG page follows the shared page safety and readability standards.\n",
        "references/template-designer.md": "# Template Designer\nDesign a fidelity template or perform mirror restoration from the complete source contract.\n",
        "workflows/create-template.md": "# Create Template\nCreate a fidelity template. Mirror restoration reads the source and preserves its contract.\n",
    }
    for relative, content in documents.items():
        path = runtime / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + ("Execution steps are concrete and use the verified tools.\n" * 3), encoding="utf-8")
    return runtime


def make_project(root: Path, *, with_template: bool = True) -> Path:
    project = root / "项目 中文"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir()
    source = project / "sources" / "材料.md"
    source.write_text("# 材料\n事实。", encoding="utf-8")
    template = project / "references" / "模板.pptx"
    if with_template:
        template.parent.mkdir()
        template.write_bytes(b"pptx fixture")
    write_json(project / "analysis" / "director_contract.json", {
        "request": "形成汇报版",
        "audience": "领导",
        "purpose": "决策",
        "page_count": 6,
        "source_files": [{"path": str(source), "sha256": director_runtime.sha256(source)}],
        "template": {"path": str(template) if with_template else None, "sha256": director_runtime.sha256(template)},
    })
    return project


class CapabilityAndModeTest(unittest.TestCase):
    def test_preflight_checks_tools_and_model_workflows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-cap-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            snapshot = director_runtime.capability_preflight(project, runtime)
            self.assertEqual(snapshot["capabilities"]["pptx_intake"]["status"], "available_tool")
            self.assertEqual(snapshot["capabilities"]["template_analysis"]["status"], "available_model_workflow")
            self.assertFalse(snapshot["capabilities"]["template_analysis"]["verified"])
            self.assertEqual(snapshot["modes"]["premium"]["status"], "available_model_workflow")

    def test_mode_propose_refreshes_stale_snapshot_and_never_recommends_degraded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-refresh-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            first = director_runtime.propose_mode(project, ROOT, runtime, quality_preference="balanced")
            self.assertEqual(first["recommended_mode"], "template")
            (runtime / "scripts" / "pptx_intake.py").unlink()
            second = director_runtime.propose_mode(project, ROOT, runtime, quality_preference="balanced")
            self.assertTrue(second["capability_snapshot_refreshed"])
            self.assertNotIn("template", second["available_modes"])
            self.assertEqual(second["recommended_mode"], "standard")

    def test_mirror_requires_explicit_complete_workflow(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-mirror-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            normal = director_runtime.propose_mode(project, ROOT, runtime, quality_preference="quality")
            self.assertEqual(normal["recommended_mode"], "premium")
            self.assertTrue(normal["mirror_available"])
            selected = director_runtime.select_mode(project, ROOT, runtime, mode="premium", quality_preference="quality")
            mode = json.loads(Path(selected["generation_mode"]).read_text(encoding="utf-8"))
            self.assertEqual(mode["replication_mode"], "fidelity")

    def test_capability_events_have_true_lifecycle_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-events-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            events: list[tuple] = []
            director_runtime.capability_preflight(project, runtime, force=True, operation_reporter=lambda *event: events.append(event))
            self.assertEqual([event[0] for event in events], ["tool_started", "tool_completed"])
            self.assertEqual([event[1] for event in events], ["capability_preflight", "capability_preflight"])

            failed: list[tuple] = []
            with patch.object(director_runtime, "_tool", side_effect=RuntimeError("broken tool")):
                with self.assertRaisesRegex(RuntimeError, "broken tool"):
                    director_runtime.capability_preflight(project, runtime, force=True, operation_reporter=lambda *event: failed.append(event))
            self.assertEqual([event[0] for event in failed], ["tool_started", "tool_failed"])
            self.assertEqual([event[1] for event in failed], ["capability_preflight", "capability_preflight"])

    def test_premium_model_workflow_only_issues_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-premium-events-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            events: list[tuple] = []
            result = director_runtime.select_mode(
                project,
                ROOT,
                runtime,
                mode="premium",
                quality_preference="quality",
                operation_reporter=lambda *event: events.append(event),
            )
            self.assertEqual(result["template_processing"]["status"], "deterministic_tools_complete")
            names = [event[0] for event in events]
            self.assertIn("model_workflow_context_issued", names)
            self.assertNotIn("model_workflow_started", names)
            self.assertNotIn("model_workflow_completed", names)

    def test_semantic_hash_ignores_display_fields_and_tracks_real_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-semantic-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            snapshot = director_runtime.capability_preflight(project, runtime)
            original_capability_hash = snapshot["capability_semantic_hash"]
            snapshot_path = project / ".director" / "capability_snapshot.json"
            edited_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            edited_snapshot["captured_at"] = "2099-01-01T00:00:00+00:00"
            write_json(snapshot_path, edited_snapshot)
            self.assertEqual(json.loads(snapshot_path.read_text(encoding="utf-8"))["capability_semantic_hash"], original_capability_hash)

            director_runtime.select_mode(project, ROOT, runtime, mode="template", quality_preference="balanced")
            baseline = director_runtime.current_mode_semantic_hash(project)
            mode_path = project / ".director" / "generation_mode.json"
            mode = json.loads(mode_path.read_text(encoding="utf-8"))
            mode["selected_at"] = "2099-01-01T00:00:00+00:00"
            mode["recommendation_reason"] = "display-only change"
            write_json(mode_path, mode)
            self.assertEqual(director_runtime.current_mode_semantic_hash(project), baseline)

            source = project / "sources" / "材料.md"
            source.write_text("# 材料\n发生了业务变化。", encoding="utf-8")
            source_changed = director_runtime.current_mode_semantic_hash(project)
            self.assertNotEqual(source_changed, baseline)
            template = project / "references" / "模板.pptx"
            template.write_bytes(b"template changed")
            self.assertNotEqual(director_runtime.current_mode_semantic_hash(project), source_changed)

            (runtime / "references" / "strategist.md").write_text("# Strategist\nChanged dependency closure.\n" * 10, encoding="utf-8")
            refreshed = director_runtime.capability_preflight(project, runtime, force=True)
            self.assertNotEqual(refreshed["capability_semantic_hash"], original_capability_hash)

    def test_context_rehydrate_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-context-") as temp:
            root = Path(temp)
            runtime = make_runtime(root)
            project = make_project(root)
            director_runtime.select_mode(project, ROOT, runtime, mode="template", quality_preference="balanced")
            page = {
                "page_id": "P03", "page_role": "architecture", "page_intent": "解释关系",
                "required_messages": ["能力层", "业务层"], "source_refs": ["sources/材料.md#H:材料"],
                "factual_constraints": ["不得新增事实"], "unresolved_questions": [],
            }
            first = director_runtime.refresh_context(project, command="page-begin", page=page, router_root=ROOT, runtime_root=runtime)
            first_text = Path(first["path"]).read_text(encoding="utf-8")
            second = director_runtime.refresh_context(project, command="page-begin", page=page, router_root=ROOT, runtime_root=runtime)
            self.assertEqual(first["semantic_dependency_hash"], second["semantic_dependency_hash"])
            self.assertEqual(first_text, Path(second["path"]).read_text(encoding="utf-8"))
            self.assertNotIn("refreshed_at", first_text)
            self.assertIn("## required_context", first_text)


class GroupedSampleAndPremiumOrderTest(unittest.TestCase):
    def _grouped_project(self, root: Path) -> Path:
        runtime = make_runtime(root)
        project = make_project(root)
        director_runtime.select_mode(project, ROOT, runtime, mode="template", quality_preference="balanced")
        production.initialize_project(project)
        pages = [
            {
                "page_id": f"P{index:02d}",
                "page_role": "cover" if index == 1 else ("architecture" if index == 3 else "finding"),
                "page_intent": f"页面{index}",
                "required_messages": ["主题"] if index != 3 else ["能力层", "业务层"],
                "source_refs": [] if index == 1 else ["sources/材料.md#H:材料"],
                "factual_constraints": [],
                "unresolved_questions": [],
            }
            for index in range(1, 7)
        ]
        candidate = root / "candidate.json"
        write_json(candidate, {
            "schema_version": "3.1", "content_map": {"core_argument": "x"},
            "fact_boundary": {"rule": "source"}, "storyline": {"logic": "reorganized"},
            "pages": pages,
            "sample_pages": [
                {"page_id": "P01", "sample_role": "overview", "reason": "总览"},
                {"page_id": "P03", "sample_role": "complex", "reason": "复杂关系"},
            ],
        })
        director_plan.install_director_plan(project, candidate)
        return project

    def test_grouped_samples_survive_global_input_invalidation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-groups-") as temp:
            project = self._grouped_project(Path(temp))
            before = production._load(project)
            self.assertEqual(before["samples"]["strategy"], "three_groups")
            (project / "sources" / "材料.md").write_text("# 材料\n源材料已变化。", encoding="utf-8")
            production.reconcile(project)
            after = production._load(project)
            self.assertEqual(after["samples"]["strategy"], "three_groups")
            self.assertEqual(set(after["samples"]["directions"]), {"A", "B", "C"})
            self.assertEqual(after["samples"]["round"], 2)

    def test_premium_plan_does_not_require_preexisting_design_spec(self) -> None:
        with tempfile.TemporaryDirectory(prefix="director31-premium-plan-") as temp:
            project = make_project(Path(temp))
            write_json(project / ".director" / "generation_mode.json", {"mode": "premium"})
            candidate = project.parent / "candidate.json"
            candidate.write_text("{}", encoding="utf-8")

            class Plan:
                def __init__(self) -> None:
                    self.called = False

                def install_director_plan(self, received_project: Path, received_candidate: str) -> dict:
                    self.called = True
                    self.project = received_project
                    self.candidate = received_candidate
                    return {"stage": "design_pending"}

            plan = Plan()
            args = type("Args", (), {"command": "plan", "project": str(project), "apply": str(candidate)})()
            _, result, _ = route.dispatch(args, {"production": object(), "director_plan": plan, "project_manager": object()})
            self.assertTrue(plan.called)
            self.assertEqual(result["generation_mode"], "premium")


if __name__ == "__main__":
    unittest.main()
