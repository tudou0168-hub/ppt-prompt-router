#!/usr/bin/env python3
"""Small, dependency-free Router routing and handoff regression runner."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import route


VARIANTS = (
    "第1轮", "受众已确认", "素材已就绪", "版式16比9",
    "来源可核", "继续处理", "保持结果",
)

SPECIAL_CASES = (
    ("government_annual_summary", "为管委会领导制作2026年上半年工作总结及下半年工作谋划，使用政府汇报工作区"),
    ("government_strategy", "为领导汇报数字政府建设方案，分析现状差距并明确建设路径"),
    ("work_report", "企业经营复盘：汇报成果、问题与下一步计划"),
    ("planning_proposal", "活动运营策划方案，说明预算与执行安排"),
    ("decision_meeting", "管理层决策会：比较两个方案并审批预算后拍板"),
    ("business_proposal", "客户提案：智能招生经营提升试点合作与咨询建议"),
)


def preflight(argv: list[str]) -> dict:
    return route.resolve(route.parser().parse_args(["--phase", "preflight", *argv]))


def canonical_signal(index: dict, entry: dict) -> str:
    candidates = [
        *entry.get("strong_signals", ()), *entry.get("required_signals", ()),
        *entry.get("supporting_signals", ()), entry.get("use_when", ""),
    ]
    for signal in candidates:
        if not signal:
            continue
        sem = route.semantics.classify(signal)
        top = route.scoring.rank(index, signal.lower(), sem)[0]
        if top.profile_id == entry["id"] and top.score >= 5:
            return signal
    raise AssertionError(f"registry has no discriminating signal for {entry['id']}")


def profile_matrix(index: dict) -> list[tuple[str, str]]:
    cases = []
    for entry in index["prompts"]:
        # The registry's required signal is intentionally the stable minimal
        # scenario.  Seven neutral delivery contexts make selection drift visible
        # without injecting a competing domain or job into the request.
        signal = canonical_signal(index, entry)
        for variant in VARIANTS:
            cases.append((entry["id"], f"{signal} PPT {variant}"))
    return cases


def assert_profile(expected: str, request: str) -> None:
    out = preflight(["--user-request", request])
    actual = (out["profile_selection"]["primary_profile"] or {}).get("id")
    if actual != expected:
        raise AssertionError(f"{expected=} {actual=} request={request!r}")


def assert_non_default_paths() -> int:
    checks = (
        ("enhance_native", "bypass", "给现有PPT添加演讲者备注和转场"),
        ("fill_native", "bypass", "保留原版式，只替换文字并填充模板"),
        ("fill_native", "light", "保留页面壳，从材料重构生成政务半年总结"),
        ("create_reusable_template", "light", "将政府年度总结沉淀为可复用模板"),
    )
    for intent, expected_mode, request in checks:
        out = preflight(["--pptx-intent", intent, "--user-request", request])
        mode = out["intervention"]["mode"]
        if mode != expected_mode:
            raise AssertionError(f"{intent=} {expected_mode=} {mode=}")
    return len(checks)


def assert_direct_plan_handoff() -> None:
    with tempfile.TemporaryDirectory(prefix="ppt-router-regression-") as tmp:
        out = route.resolve(route.parser().parse_args([
            "--phase", "director", "--prompt-id", "government_annual_summary",
            "--project-dir", tmp, "--user-request", "政府半年工作总结",
            "--material", "/tmp/source.docx", "--template-path", "/tmp/government-report",
        ]))
        plan_path = Path(tmp) / "analysis" / "presentation_plan.md"
        if not plan_path.parent.is_dir():
            raise AssertionError("director phase did not prepare the ordinary analysis directory")
    task = out["director_task"]
    prompt = task["task"]["prompt"] if task["task"] else ""
    handoff = out["master_handoff"]
    required = (
        "Router Director Task", "Professional Director Prompt", "government_annual_summary",
        "Final output path", "presentation_plan.md",
    )
    if task["status"] != "ready" or not task["task"]["prompt_sha256"]:
        raise AssertionError("director task did not become ready")
    if any(token not in prompt for token in required):
        raise AssertionError("director task omitted a required context section")
    if "用户明确要求（含标题、章节、页数、图片、事实、模板和参考约束）" not in prompt:
        raise AssertionError("director task omitted input-priority instructions")
    if handoff["presentation_plan_path"] != str(plan_path.resolve()):
        raise AssertionError("Master did not receive the final plan path")
    if out["execution_path"] != {
        "id": "router_director_then_fresh_master",
        "requires_presentation_plan": True,
        "director_protocol": "direct_plan_v1",
    }:
        raise AssertionError("migrated profile did not select the direct-plan execution path")
    expected_paths = {
        "material_paths": ["/tmp/source.docx"],
        "template_paths": ["/tmp/government-report"],
        "reference_paths": [],
        "workspace_roots": [],
    }
    if {k: handoff[k] for k in expected_paths} != expected_paths:
        raise AssertionError("Master handoff merged typed input paths")
    rendered_handoff = json.dumps(handoff, ensure_ascii=False)
    forbidden = ("Director Kernel", "Semantic Vocabulary", "Primary Profile", "Secondary Lens", "scoring", "capability map")
    if any(token in rendered_handoff for token in forbidden):
        raise AssertionError("Router internals crossed the Master handoff boundary")


def assert_non_plan_paths() -> None:
    legacy_full = preflight([
        "--prompt-id", "government_strategy", "--user-request", "政府专项规划与建设方案",
        "--material", "/tmp/strategy.docx", "--reference-path", "/tmp/reference.pptx",
    ])
    light = preflight([
        "--pptx-intent", "fill_native", "--user-request", "保留页面壳，从材料重构生成政务半年总结",
        "--material", "/tmp/content.docx", "--template-path", "/tmp/native-template.pptx",
    ])
    bypass = preflight([
        "--pptx-intent", "enhance_native", "--user-request", "给现有PPT添加演讲者备注和转场",
        "--reference-path", "/tmp/existing.pptx",
    ])
    for label, out in (("legacy full", legacy_full), ("light", light), ("bypass", bypass)):
        if out["execution_path"]["requires_presentation_plan"]:
            raise AssertionError(f"{label} incorrectly requires a plan")
        if "presentation_plan_path" in out["master_handoff"]:
            raise AssertionError(f"{label} passed a nonexistent plan path to Master")
        if out["director_task"]["task"] is not None:
            raise AssertionError(f"{label} incorrectly compiled a Director task")
    if legacy_full["director_task"]["status"] != "not_migrated":
        raise AssertionError("legacy profile migration status was not exposed")
    try:
        route.resolve(route.parser().parse_args([
            "--phase", "director", "--prompt-id", "government_strategy",
            "--project-dir", "/tmp/legacy-director", "--user-request", "政府专项规划",
        ]))
    except ValueError:
        pass
    else:
        raise AssertionError("legacy profile incorrectly entered the direct-plan phase")


def assert_user_constraint_preservation() -> None:
    out = preflight([
        "--prompt-id", "government_annual_summary", "--user-request", "严格按用户给定章节制作",
        "--audience", "市政府专题会", "--page-count", "12", "--format", "ppt169",
        "--delivery-purpose", "专题汇报", "--chapter-constraint", "按一、二、三章顺序",
        "--title-constraint", "标题沿用用户目录", "--image-constraint", "P04必须使用现场照片",
        "--fact-constraint", "所有数据保留原口径", "--template-constraint", "使用指定模板",
        "--user-constraint", "不新增页面",
    ])
    c = out["master_handoff"]["explicit_user_constraints"]
    if c["chapters"] != ["按一、二、三章顺序"] or c["titles"] != ["标题沿用用户目录"]:
        raise AssertionError("explicit chapter/title constraints were lost")
    if c["images"] != ["P04必须使用现场照片"] or c["facts"] != ["所有数据保留原口径"]:
        raise AssertionError("explicit image/fact constraints were lost")
    if out["master_handoff"]["page_count"] != 12 or out["master_handoff"]["format"] != "ppt169":
        raise AssertionError("core user constraints were lost")


def main() -> int:
    index = json.loads(route.INDEX.read_text(encoding="utf-8"))
    matrix = profile_matrix(index)
    for expected, request in matrix:
        assert_profile(expected, request)
    for expected, request in SPECIAL_CASES:
        assert_profile(expected, request)
    non_default = assert_non_default_paths()
    assert_direct_plan_handoff()
    assert_non_plan_paths()
    assert_user_constraint_preservation()
    print(json.dumps({
        "router_version": route.ROUTER_VERSION,
        "profiles": len(index["prompts"]),
        "routing_cases": len(matrix) + len(SPECIAL_CASES),
        "non_default_cases": non_default,
        "direct_plan_handoff": "passed",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
