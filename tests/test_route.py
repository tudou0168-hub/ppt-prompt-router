from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from install import FOCUSED_PROFILE_IDS, PROFILE_FIELDS, compile_director_profile, lint_profiles, prompt_entries


ROOT = Path(__file__).resolve().parents[1]
PPT_MASTER_ROOT = ROOT.parent / "ppt-master"
ROUTE_SCRIPT = ROOT / "scripts" / "route.py"
SPEC = importlib.util.spec_from_file_location("router_v2", ROUTE_SCRIPT)
assert SPEC and SPEC.loader
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


class RouterV2Test(unittest.TestCase):
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
            "主要视觉锚点",
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
        self.assertEqual(router.detect_template_intent("用这个PPT做", template)["status"], "needs_input")

    @unittest.skipUnless(
        (PPT_MASTER_ROOT / "skills" / "ppt-master" / "scripts" / "project_manager.py").is_file(),
        "未提供本地 PPT Master，跳过真实 Router 集成测试",
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
                    "--ppt-master-root",
                    str(PPT_MASTER_ROOT),
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
            self.assertIn('"status": "ppt-master-accepted"', result.stdout)
            self.assertIn('"accepted": true', result.stdout)
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
            self.assertEqual(contract["template_intent"], "none")
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
