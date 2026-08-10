#!/usr/bin/env python3
"""Fast program-level regression for Router 3.1.3.

Deliberately small: it validates the production contract, not PPT aesthetics.
Real PPT validation follows TESTING.md and stops after 3–4 representative pages.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import route

DIRECT_PLAN_PROFILES = (
    "government_annual_summary",
    "government_strategy",
    "work_report",
    "decision_meeting",
    "product_technical",
)

REPRESENTATIVE_ROUTES = (
    ("government_annual_summary", "为管委会领导制作2026年上半年工作总结及下半年工作谋划"),
    ("government_strategy", "为领导汇报数字政府建设方案，分析现状差距、建设目标和实施路径"),
    ("work_report", "企业项目季度工作复盘，汇报目标结果、进度偏差、风险和下一步行动"),
    ("decision_meeting", "管理层决策会，比较两个真实方案的预算、周期、收益和风险后拍板"),
    ("product_technical", "技术解决方案，说明业务场景、系统架构、数据流、接口、安全和实施"),
)


def preflight(args: list[str]) -> dict:
    return route.resolve(route.parser().parse_args(["--phase", "preflight", *args]))


def assert_representative_routes() -> None:
    for expected, request in REPRESENTATIVE_ROUTES:
        out = preflight(["--user-request", request])
        actual = (out["profile_selection"]["primary_profile"] or {}).get("id")
        if actual != expected:
            raise AssertionError(f"route mismatch: expected={expected} actual={actual} request={request}")
        if not out["execution_path"]["requires_presentation_plan"]:
            raise AssertionError(f"{expected} did not enter direct_plan_v1")

    # Important conflict: annual review must not swallow an explicit construction plan.
    out = preflight(["--user-request", "政府数字化建设方案：总结现状并制定专项规划、建设路线图和实施方案"])
    actual = (out["profile_selection"]["primary_profile"] or {}).get("id")
    if actual != "government_strategy":
        raise AssertionError(f"annual/strategy boundary regressed: {actual}")


def assert_prompt_contract() -> None:
    index = json.loads(route.INDEX.read_text(encoding="utf-8"))
    by_id = {x["id"]: x for x in index["prompts"]}
    required_sections = ("## Goals", "## Skills", "## Workflows", "## 语义导演", "## 每页输出格式", "## 输出")
    anchoring_markers = ("完整页面导演示例", "示例一", "示例二", "示例三", "示例四", "## P01｜", "## P02｜", "## P03｜")
    downstream_terms = (
        "ppt master", "design_spec", "stage 2", "spec lock", "executor", "§ix", "§viii",
        "audience move", "core message", "layout", "native shape", "svg", "visualization",
        "visual job router", "boolean", "animation", "page rhythm",
    )

    for pid in DIRECT_PLAN_PROFILES:
        entry = by_id[pid]
        if entry.get("director_protocol") != "direct_plan_v1":
            raise AssertionError(f"{pid} missing direct_plan_v1")
        if entry.get("profile_version") != "3.1.3":
            raise AssertionError(f"{pid} profile_version not separated from protocol")
        text = (ROOT / entry["file"]).read_text(encoding="utf-8")
        for section in required_sections:
            if section not in text:
                raise AssertionError(f"{pid} missing V15 section {section}")
        if any(marker in text for marker in anchoring_markers):
            raise AssertionError(f"{pid} contains page-specific example anchoring")
        if "presentation_plan.md" not in text:
            raise AssertionError(f"{pid} missing final output contract")
        lower = text.lower()
        if any(term in lower for term in downstream_terms):
            raise AssertionError(f"{pid} contains downstream implementation knowledge")


def assert_path_only_director() -> None:
    with tempfile.TemporaryDirectory(prefix="router-smoke-") as tmp:
        out = route.resolve(route.parser().parse_args([
            "--phase", "director",
            "--prompt-id", "product_technical",
            "--project-dir", tmp,
            "--material", "/tmp/source.docx",
            "--template-path", "/tmp/template/",
            "--reference-path", "/tmp/reference.pptx",
            "--workspace-root", "/tmp/workspace/",
            "--user-request", "给技术委员会汇报系统建设方案",
            "--audience", "技术委员会",
            "--page-count", "10",
            "--chapter-constraint", "保留现有四章",
            "--title-constraint", "沿用用户标题",
            "--fact-constraint", "数据严格按原文",
        ]))
        plan = Path(tmp) / "analysis" / "presentation_plan.md"
        if not plan.parent.is_dir():
            raise AssertionError("analysis directory was not prepared")

    task = out["director_task"]["task"]
    if out["director_task"]["status"] != "ready" or not task:
        raise AssertionError("director task not ready")
    if not task.get("path_only_context"):
        raise AssertionError("director task is not path-only")
    if task.get("secondary_lens_path") is not None:
        raise AssertionError("Direct Plan should use one self-contained professional Profile without a secondary lens")
    prompt = task["prompt"]
    if str((ROOT / "prompts/05_professional_scenarios/product_technical.md").resolve()) not in prompt:
        raise AssertionError("professional prompt path missing")
    # Full profile content must not be inlined into the task.
    profile_text = (ROOT / "prompts/05_professional_scenarios/product_technical.md").read_text(encoding="utf-8").strip()
    if profile_text[:120] in prompt:
        raise AssertionError("professional profile content was inlined")

    handoff = out["master_handoff"]
    expected = {
        "material_paths": ["/tmp/source.docx"],
        "template_paths": ["/tmp/template/"],
        "reference_paths": ["/tmp/reference.pptx"],
        "workspace_roots": ["/tmp/workspace/"],
    }
    for key, value in expected.items():
        if handoff[key] != value:
            raise AssertionError(f"typed path lost: {key}")
    if handoff["presentation_plan_path"] != str(plan.resolve()):
        raise AssertionError("plan path missing from Master handoff")
    if handoff["explicit_user_constraints"]["titles"] != ["沿用用户标题"]:
        raise AssertionError("user title constraint lost")

    serialized = json.dumps(handoff, ensure_ascii=False)
    for forbidden in ("Professional Director Prompt", "Director Kernel", "Semantic Vocabulary", "Primary Profile", "scoring", "capability map"):
        if forbidden in serialized:
            raise AssertionError(f"Router internals leaked to Master: {forbidden}")


def assert_non_plan_paths() -> None:
    cases = (
        ("light", ["--pptx-intent", "fill_native", "--user-request", "保留页面壳，从材料重构生成半年总结"]),
        ("bypass", ["--pptx-intent", "enhance_native", "--user-request", "给现有PPT添加备注和转场"]),
        ("legacy_full", ["--prompt-id", "business_proposal", "--user-request", "客户经营提升咨询方案"]),
    )
    for label, args in cases:
        out = preflight(args)
        if out["execution_path"]["requires_presentation_plan"]:
            raise AssertionError(f"{label} incorrectly requires a plan")
        if "presentation_plan_path" in out["master_handoff"]:
            raise AssertionError(f"{label} leaked nonexistent plan path")

    legacy = preflight(["--prompt-id", "business_proposal", "--user-request", "客户经营提升咨询方案"])
    if legacy["director_task"]["status"] != "not_migrated":
        raise AssertionError("unmigrated FULL profile status is wrong")

    light = preflight(["--pptx-intent", "fill_native", "--prompt-id", "government_annual_summary", "--user-request", "保留页面壳并重构半年总结"])
    if light["director_task"]["status"] != "not_required":
        raise AssertionError("LIGHT migrated profile should be not_required, not not_migrated")


def main() -> int:
    assert_representative_routes()
    assert_prompt_contract()
    assert_path_only_director()
    assert_non_plan_paths()
    print(json.dumps({
        "router_version": route.ROUTER_VERSION,
        "representative_routes": len(REPRESENTATIVE_ROUTES) + 1,
        "direct_plan_profiles": len(DIRECT_PLAN_PROFILES),
        "path_only_director": "passed",
        "typed_master_handoff": "passed",
        "prompt_anti_anchoring": "passed",
        "non_plan_paths": "passed",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
