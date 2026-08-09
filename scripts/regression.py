#!/usr/bin/env python3
"""Small, dependency-free Router regression runner.

The Router is a handoff compiler, not a presentation generator.  This runner
therefore checks deterministic routing and the two handoff payloads without
creating production artifacts or pretending to validate PPT Master output.
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


def assert_director_handoff() -> None:
    contract = json.dumps({
        "audience": "管委会领导", "communication_intent": "汇报半年工作成效与下一步",
    }, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="ppt-router-regression-") as tmp:
        out = route.resolve(route.parser().parse_args([
            "--phase", "director", "--prompt-id", "government_annual_summary",
            "--stage1-contract", contract, "--project-dir", tmp,
            "--user-request", "政府半年工作总结",
        ]))
    handoff = out["director_handoff"]
    prompt = handoff["inline_prompt"] or ""
    required = (
        "Director Runtime Payload", "Confirmed Stage 1 Communication Contract",
        "government_annual_summary", "Director Kernel", "Semantic Vocabulary",
        "Router 仅编译本次专业导演 handoff", "presentation_plan.md",
    )
    if handoff["status"] != "ready" or not handoff["inline_prompt_sha256"]:
        raise AssertionError("director handoff did not become ready")
    if any(token not in prompt for token in required):
        raise AssertionError("director handoff omitted a required context section")


def main() -> int:
    index = json.loads(route.INDEX.read_text(encoding="utf-8"))
    matrix = profile_matrix(index)
    for expected, request in matrix:
        assert_profile(expected, request)
    for expected, request in SPECIAL_CASES:
        assert_profile(expected, request)
    non_default = assert_non_default_paths()
    assert_director_handoff()
    print(json.dumps({
        "router_version": route.ROUTER_VERSION,
        "profiles": len(index["prompts"]),
        "routing_cases": len(matrix) + len(SPECIAL_CASES),
        "non_default_cases": non_default,
        "director_handoff": "passed",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
