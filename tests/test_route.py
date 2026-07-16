from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from install import FOCUSED_PROFILE_IDS, PROFILE_FIELDS, compile_director_profile, lint_profiles, prompt_entries
from scripts import router_profile


ROOT = Path(__file__).resolve().parents[1]
ROUTE_SCRIPT = ROOT / "scripts" / "route.py"
SPEC = importlib.util.spec_from_file_location("router_v2", ROUTE_SCRIPT)
assert SPEC and SPEC.loader
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


class RouterV2Test(unittest.TestCase):
    def test_start_only_imports_inputs_and_runs_capability_preflight(self) -> None:
        class FakeManager:
            def __init__(self, base: str | Path):
                self.base = Path(base)

            def init_project(self, name: str, _format: str, _base: str) -> str:
                project = self.base / name
                for relative in ("analysis", "sources"):
                    (project / relative).mkdir(parents=True, exist_ok=True)
                return str(project)

            def import_sources(self, project: str, sources: list[str], **_kwargs: object) -> dict:
                destination = Path(project) / "sources"
                for raw in sources:
                    source = Path(raw)
                    (destination / source.name).write_bytes(source.read_bytes())
                return {"imported": sources}

        class FakeProduction:
            @staticmethod
            def initialize_project(project: str | Path) -> None:
                write = Path(project) / "analysis" / "production_state.json"
                write.write_text(json.dumps({"stage": "director_pending"}), encoding="utf-8")

        with tempfile.TemporaryDirectory(prefix="router31-start-") as temp:
            root = Path(temp)
            source = root / "材料.md"; source.write_text("# 材料\n事实", encoding="utf-8")
            template = root / "参考.pptx"; template.write_bytes(b"pptx")
            args = router.build_parser().parse_args([
                "start", "--request", "政务专项规划，4页，给政府领导汇报，参考模板元素",
                "--source", str(source), "--template", str(template), "--page-count", "4",
                "--prompt-id", "government_strategy", "--project-base", str(root / "projects"),
                "--project-name", "start-boundary",
            ])
            with mock.patch.object(router, "capability_preflight", return_value={"modes": {"standard": {"status": "available_model_workflow"}}}) as preflight:
                project, result = router.command_start(
                    args,
                    {"project_manager": types.SimpleNamespace(ProjectManager=FakeManager), "production": FakeProduction},
                )
            preflight.assert_called_once()
            self.assertEqual(result["next_allowed_actions"], ["mode-propose"])
            self.assertTrue((project / "sources" / "材料.md").is_file())
            self.assertTrue((project / "references" / "参考.pptx").is_file())
            for forbidden in ("analysis/director_plan.json", "design_spec.md", "spec_lock.md", "analysis/template_intake"):
                self.assertFalse((project / forbidden).exists(), forbidden)

    def test_router_runtime_is_internal_and_receipt_independent(self) -> None:
        route_source = (ROOT / "scripts" / "route.py").read_text(encoding="utf-8")
        self.assertNotIn("install_receipt.json", route_source)
        self.assertNotIn("PPT_MASTER_ROOT", route_source)
        self.assertNotIn("ppt-master-root", route_source)
        self.assertIn("scripts.router_profile", route_source)
        self.assertNotIn("from install import", route_source)
        self.assertIn('RUNTIME = ROOT / "runtime" / "ppt-master"', route_source)
        self.assertEqual(
            router.PUBLIC_COMMANDS,
            ("start", "mode-propose", "mode-select", "plan", "lock-spec", "page-begin", "page-check", "page-review", "page-pass", "sample-confirm", "sample-reject", "review", "status", "export"),
        )

    def test_runtime_profile_compiler_has_no_installer_dependency(self) -> None:
        profile_source = (ROOT / "scripts" / "router_profile.py").read_text(encoding="utf-8")
        self.assertNotIn("prepare_master_source", profile_source)
        self.assertNotIn("apply_master_overlay", profile_source)
        index = router_profile.load_index(ROOT)
        government = next(entry for entry in router_profile.prompt_entries(index) if entry["id"] == "government_strategy")
        self.assertIn("省市专项汇报", router_profile.compile_director_profile(ROOT, government))

    def test_compiles_one_director_profile_with_defaults_and_hashable_content(self) -> None:
        index = router.load_index(ROOT)
        entries = prompt_entries(index)
        self.assertEqual(len(entries), 25)
        lint_profiles(ROOT, entries)
        government = next(entry for entry in entries if entry["id"] == "government_strategy")
        compiled = compile_director_profile(ROOT, government)
        self.assertIn("## Universal Director Protocol", compiled)
        self.assertIn("## Scene Profile", compiled)
        for field in PROFILE_FIELDS:
            self.assertIn(f"- {field}:", compiled)
        self.assertIn("省市专项汇报", compiled)
        self.assertIn("现状 | 问题 | 原因 | 差距 | 路径 | 行动", compiled)
        self.assertEqual(len(hashlib.sha256(compiled.encode("utf-8")).hexdigest()), 64)

        experimental = next(entry for entry in entries if entry["id"] == "work_report")
        fallback = compile_director_profile(ROOT, experimental)
        self.assertIn("## Experimental Source Guidance", fallback)
        self.assertIn("- required_content_fields: ", fallback)

    def test_shared_protocol_stays_in_director_boundary(self) -> None:
        protocol = (ROOT / "prompts/_shared/director_protocol.md").read_text(encoding="utf-8")
        for required in (
            "content_map",
            "整体 Storyline",
            "每页只表达一个核心观点",
            "主要内容关系",
            "事实、推断、目标和建议",
        ):
            self.assertIn(required, protocol)
        for forbidden in (
            "production.py",
            "svg_quality_checker.py",
            "visual_review.py",
            "charts_index.json",
            "字体选择",
            "配色选择",
            "导出命令",
        ):
            self.assertNotIn(forbidden, protocol)

    def test_six_focused_profiles_route_adjacent_scenarios(self) -> None:
        index = router.load_index(ROOT)
        cases = {
            "government_strategy": "省级数字政府政务专项规划，面向政府领导汇报人工智能+政务服务路径",
            "business_bid": "招标文件技术标投标评标响应方案",
            "data_report": "管理层数据报告：经营数据指标报告和风险报告",
            "classroom_lesson": "高中生物课堂教学设计与学生练习课件",
            "brand_presentation": "品牌定位、品牌文化和品牌故事宣讲",
            "fundraising_bp": "面向投资人的融资BP，说明估值、融资用途和财务预测",
        }
        self.assertEqual(set(cases), FOCUSED_PROFILE_IDS)
        for expected, request in cases.items():
            result = router.route_profile(index, request)
            self.assertEqual(result["status"], "selected")
            self.assertEqual(result["entry"]["id"], expected)

    def test_government_strategy_scoring_and_ambiguity(self) -> None:
        index = router.load_index(ROOT)
        selected = router.route_profile(
            index,
            "某县政务专项规划，给政府领导汇报政策实施路径",
        )
        self.assertEqual(selected["status"], "selected")
        self.assertEqual(selected["entry"]["id"], "government_strategy")
        self.assertGreaterEqual(selected["score"], 3)

        ambiguous = router.route_profile(index, "做一个PPT")
        self.assertEqual(ambiguous["status"], "needs_input")
        self.assertEqual(len(ambiguous["candidates"]), 2)

    def test_four_template_intents(self) -> None:
        template = ["reference.pptx"]
        self.assertEqual(
            router.detect_template_intent("参考模板设计元素，不要套用", template)["intent"],
            "reference_elements",
        )
        self.assertEqual(
            router.detect_template_intent("保持模板版式并替换内容", template)["intent"],
            "native_fill",
        )
        self.assertEqual(
            router.detect_template_intent("提炼成可复用模板工作区", template)["intent"],
            "reusable_template",
        )
        self.assertEqual(router.detect_template_intent("自由设计", [])["intent"], "none")
        deferred = router.detect_template_intent("用这个PPT做", template)
        self.assertEqual(deferred["status"], "selected")
        self.assertEqual(deferred["intent"], "reference_elements")

    @unittest.skipUnless(
        os.environ.get("RUN_INSTALLED_ROUTER_INTEGRATION") == "1",
        "仅对已安装离线套件运行真实 Router 集成测试",
    )
    def test_real_router_accept_without_template(self) -> None:
        with tempfile.TemporaryDirectory(prefix="router-v2-") as tmp:
            tmpdir = Path(tmp)
            source = tmpdir / "government-plan.md"
            source.write_text("# 政务专项规划\n面向政府领导汇报政策实施路径。", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROUTE_SCRIPT),
                    "start",
                    "--project-base",
                    str(tmpdir / "projects"),
                    "--project-name",
                    "router_contract_test",
                    "--prompt-id",
                    "government_strategy",
                    "--request",
                    "政务专项规划，4页，给政府领导汇报",
                    "--source",
                    str(source),
                    "--page-count",
                    "4",
                    "--audience",
                    "政府领导",
                    "--template-intent",
                    "none",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn('"status": "director_pending"', result.stdout)
            self.assertIn('"next_allowed_actions": [', result.stdout)
            matches = re.findall(r'"project": "([^"]+)"', result.stdout)
            self.assertTrue(matches, msg=result.stdout)
            project = Path(matches[-1])
            contract_path = project / "analysis/director_contract.json"
            profile_path = project / "analysis/director_profile.md"
            state_path = project / "analysis/production_state.json"
            self.assertTrue(contract_path.is_file())
            self.assertTrue(profile_path.is_file())
            self.assertTrue(state_path.is_file())
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            self.assertEqual(contract["profile"]["id"], "government_strategy")
            self.assertEqual(contract["profile"]["validation_status"], "validated")
            self.assertEqual(contract["template"]["intent"], "none")
            profile = profile_path.read_text(encoding="utf-8")
            self.assertIn("## Universal Director Protocol", profile)
            self.assertEqual(
                contract["profile"]["sha256"],
                hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            )
            self.assertFalse(any(path.name == "director_profile.md" for path in (project / "sources").iterdir()))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "director_pending")


if __name__ == "__main__":
    unittest.main()
