#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INDEX = ROOT / "prompt-index.json"

if __package__:
    from . import scoring, semantics
    from . import template_intent as intent_mod
else:
    sys.path.insert(0, str(ROOT))
    from scripts import scoring, semantics
    from scripts import template_intent as intent_mod

ROUTER_VERSION = "3.1.3"
TARGET = "4.4+"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PPT Prompt Router 3.1.3 direct-plan interface")
    p.add_argument("--phase", choices=("preflight", "director"), default="preflight")
    p.add_argument("--project-name", default="")
    p.add_argument("--format", default="ppt169")
    p.add_argument("--project-dir")
    p.add_argument("--material", action="append", default=[])
    p.add_argument("--reference-path", action="append", default=[])
    p.add_argument("--template-path", action="append", default=[])
    p.add_argument("--workspace-root", action="append", default=[])
    p.add_argument("--workspace-intent", choices=("explicit_use_requested", "candidate"))
    p.add_argument("--context", action="append", default=[])
    p.add_argument("--audience", default="")
    p.add_argument("--page-count", type=int)
    p.add_argument("--delivery-purpose", default="")
    p.add_argument("--user-request", default="")
    p.add_argument("--chapter-constraint", action="append", default=[])
    p.add_argument("--title-constraint", action="append", default=[])
    p.add_argument("--image-constraint", action="append", default=[])
    p.add_argument("--fact-constraint", action="append", default=[])
    p.add_argument("--template-constraint", action="append", default=[])
    p.add_argument("--user-constraint", action="append", default=[])
    p.add_argument("--prompt-id")
    p.add_argument("--pptx-intent", choices=intent_mod.VALID_INTENTS)
    p.add_argument("--template-intent", choices=tuple(intent_mod.LEGACY_INTENT_MAP))
    p.add_argument("--json", action="store_true")
    return p


def task_text(a: argparse.Namespace, refs: list[str]) -> str:
    parts = [
        a.user_request, *a.context, a.delivery_purpose, a.audience,
        *[Path(x).name for x in a.material],
        *[Path(x).name for x in refs],
    ]
    return " ".join(x for x in parts if x).strip() or "default"


def generation_profile_hint(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ("快速生成", "快速做", "quick generate", "quick", "直接生成", "跳过策略")):
        return "quick_generate"
    if any(x in t for x in ("1:1", "一比一", "保留原文字", "保留文字", "保留页数", "保留顺序", "只美化", "美化这份ppt")):
        return "beautify"
    return "default"


def intervention_mode(text: str, source_intent: str) -> tuple[str, str, str]:
    t = text.lower()
    profile = generation_profile_hint(text)
    if source_intent == "enhance_native":
        return "bypass", profile, "native enhancement由PPT Master原生能力直接完成"
    if source_intent == "create_reusable_template":
        scenario = any(x in t for x in ("政府", "政务", "年度总结", "半年总结", "工作汇报", "经营复盘", "培训", "技术方案", "销售提案"))
        return ("light" if scenario else "bypass"), profile, ("专业场景模板补充场景语义" if scenario else "模板提取直接交由PPT Master")
    if source_intent == "fill_native":
        restructuring = any(x in t for x in ("提炼", "压缩", "浓缩", "重构", "重组", "从材料", "生成", "整理成", "总结"))
        return ("light" if restructuring else "bypass"), profile, ("原生填充前补充内容重构" if restructuring else "原生页面直接填充")
    if profile in ("quick_generate", "beautify"):
        return "light", profile, "以轻量导演语义辅助原生生成"
    return "full", profile, "新生成或重构型PPT适合完整专业导演"


def choose(index: dict, text: str, sem: dict, forced: str | None = None):
    if forced:
        entry = next((x for x in index["prompts"] if x["id"] == forced), None)
        if not entry:
            raise ValueError(f"unknown prompt id: {forced}")
        return entry, [], "high", False
    ranked = scoring.rank(index, text.lower(), sem)
    if not ranked:
        raise ValueError("prompt registry is empty")
    top = ranked[0]
    entry = next(x for x in index["prompts"] if x["id"] == top.profile_id)
    shortlist = [{"id": x.profile_id, "score": x.score} for x in ranked[:3]]
    conf = scoring.confidence(ranked)
    arbitrate = scoring.is_ambiguous(ranked) or conf == "low"
    return entry, shortlist, conf, arbitrate


def candidate_profiles(index: dict, ranking: list[dict]) -> list[dict]:
    by_id = {x["id"]: x for x in index.get("prompts", [])}
    out = []
    for item in ranking:
        entry = by_id.get(item["id"])
        if entry:
            out.append({
                "id": entry["id"], "name_zh": entry.get("name_zh"),
                "score": item["score"],
                "profile_path": str((ROOT / entry["file"]).resolve()),
                "default_lens": entry.get("default_lens"),
            })
    return out


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_constraints(a: argparse.Namespace) -> dict[str, list[str]]:
    return {
        "chapters": a.chapter_constraint,
        "titles": a.title_constraint,
        "images": a.image_constraint,
        "facts": a.fact_constraint,
        "templates": a.template_constraint,
        "other": a.user_constraint,
    }


def supports_direct_plan(profile: dict | None) -> bool:
    return bool(profile and profile.get("director_protocol") == "direct_plan_v1")


def execution_path(mode: str, profile: dict | None) -> tuple[str, bool, str | None]:
    if mode == "full" and supports_direct_plan(profile):
        return "router_director_then_fresh_master", True, "direct_plan_v1"
    if mode == "full" and profile is not None:
        return "fresh_master_without_plan", False, None
    return "fresh_master_without_plan", False, None


def presentation_plan_path(project_dir: str | None) -> str:
    if project_dir:
        return str((Path(project_dir).expanduser() / "analysis" / "presentation_plan.md").resolve())
    return "analysis/presentation_plan.md"


def director_task(profile: dict, lens: str | None, plan_path: str, a: argparse.Namespace) -> dict:
    """Compile a small Router-only task. Professional content stays behind file paths."""
    profile_path = (ROOT / profile["file"]).resolve()
    profile_text = file_text(profile_path)
    lens_path = None
    if lens:
        p = (ROOT / "lenses" / f"{lens}.md").resolve()
        if p.is_file():
            lens_path = str(p)

    lines = [
        "# Router Director Task",
        f"Router: {ROUTER_VERSION}",
        f"Primary Profile: {profile['id']}",
        "",
        "## Read these paths",
        f"- Professional prompt: `{profile_path}`",
    ]
    if lens_path:
        lines.append(f"- Optional secondary lens: `{lens_path}`")
    lines.extend([
        *[f"- Material: `{x}`" for x in a.material],
        *[f"- Template: `{x}`" for x in a.template_path],
        *[f"- Reference: `{x}`" for x in a.reference_path],
        *[f"- Workspace: `{x}`" for x in a.workspace_root],
        "",
        "## User task",
        a.user_request or "按原始材料和明确约束完成专业导演。",
        f"- Audience: {a.audience or '由材料和用户要求判断'}",
        f"- Page count: {a.page_count if a.page_count else '由用户要求和材料判断'}",
        f"- Format: {a.format}",
        f"- Delivery purpose: {a.delivery_purpose or '由用户要求判断'}",
        "- Explicit constraints: " + json.dumps(user_constraints(a), ensure_ascii=False),
        "",
        "## Priority",
        "用户明确要求 → 原始事实材料 → 用户明确模板/参考要求 → Professional Profile 的专业默认经验。",
        "",
        "## Output",
        f"完整读取上述路径后，按 Professional Profile 直接写入 `{plan_path}`。",
        "完成 presentation_plan.md 后结束当前 Router Director Context。",
        "PPT Master、Design Spec、Spec Lock、SVG、图片和PPTX由后续 fresh PPT Master Context负责。",
    ])
    prompt = "\n".join(lines).strip()
    return {
        "profile_path": str(profile_path),
        "profile_sha256": sha_text(profile_text),
        "secondary_lens_path": lens_path,
        "prompt": prompt,
        "prompt_sha256": sha_text(prompt),
        "path_only_context": True,
    }


def master_handoff(a: argparse.Namespace, plan_path: str | None, source_intent: str) -> dict:
    """Router→Master boundary: typed paths + user task + short native activation."""
    activation = "调用 PPT Master 完成当前任务。完整读取当前 PPT Master SKILL.md 及实际命中的原生工作流，由 PPT Master 自主确定最终 Route。"
    if plan_path:
        activation += "读取 presentation_plan.md 作为已完成的专业内容与页面语义导演稿，并结合原始材料、模板/参考和用户要求继续生产。"
    if source_intent not in {"fill_native", "enhance_native", "create_reusable_template"}:
        activation += "Generate PPTX 时按当前版本 Default Generate PPTX 原生完整流程执行。"
    activation += "以最终汇报效果为优先，充分发挥本任务实际适用的原生完整、高级和条件能力，完成 Strategist、设计生产、Review、Export 与 Postflight。不要重新运行 PPT Prompt Router。"

    out = {
        "material_paths": list(a.material),
        "template_paths": list(a.template_path),
        "reference_paths": list(a.reference_path),
        "workspace_roots": list(a.workspace_root),
        "original_user_task": a.user_request,
        "audience": a.audience,
        "page_count": a.page_count,
        "format": a.format,
        "delivery_purpose": a.delivery_purpose,
        "explicit_user_constraints": user_constraints(a),
        "activation_prompt": activation,
    }
    if plan_path:
        out["presentation_plan_path"] = plan_path
        out["content_contract_change_rule"] = (
            "若用户实质改变核心任务、材料范围或页面规模，停止当前 Master Context，"
            "从 Router 入口重新生成 presentation_plan.md，再启动新的 Master Context。"
        )
    return out


def resolve(a: argparse.Namespace) -> dict:
    refs = list(dict.fromkeys([*a.reference_path, *a.template_path]))
    text = task_text(a, refs)
    if a.pptx_intent and a.template_intent:
        raise ValueError("use one intent option only")

    source_intent = a.pptx_intent or (
        intent_mod.normalize_legacy_intent(a.template_intent)
        if a.template_intent
        else intent_mod.classify(a.user_request, refs, workspace_roots=a.workspace_root)
    )
    mode, generation_profile, reason = intervention_mode(a.user_request, source_intent)
    sem = semantics.classify(text)
    index = json.loads(INDEX.read_text(encoding="utf-8"))

    selected = None
    ranking = []
    confidence = "n/a"
    arbitrate = False
    lens = None

    if mode != "bypass":
        selected, ranking, confidence, arbitrate = choose(index, text, sem, a.prompt_id)
        if not a.prompt_id and ranking and ranking[0]["score"] < 5:
            mode = "bypass"
            reason = "专业场景信号较弱，PPT Master原生判断更合适"
            selected, ranking, confidence, arbitrate = None, [], "n/a", False
        else:
            lens = selected.get("default_lens")
            if "government" in sem["domains"] and selected["id"] not in ("government_strategy", "government_annual_summary"):
                lens = "government_formality"
            if "decide" in sem["jobs"] and selected["id"] not in ("decision_meeting", "government_strategy", "government_annual_summary"):
                lens = "decision_ask"
            if arbitrate:
                lens = None

    resolved_profile = selected if (selected and not arbitrate) else None
    candidates = candidate_profiles(index, ranking) if arbitrate else []
    path, needs_plan, protocol = execution_path(mode, resolved_profile)
    # A migrated Direct Plan Profile is self-contained.  Keep its Director context
    # single-profile to reduce prompt dilution and cross-skill context pollution.
    if needs_plan:
        lens = None

    if a.phase == "director" and not needs_plan:
        raise ValueError("director phase needs a resolved profile migrated to director_protocol=direct_plan_v1")

    plan_path = presentation_plan_path(a.project_dir) if needs_plan else None
    if a.phase == "director" and plan_path and a.project_dir:
        Path(plan_path).parent.mkdir(parents=True, exist_ok=True)

    workspace_intent = a.workspace_intent or ("explicit_use_requested" if a.workspace_root else "candidate")
    task = director_task(resolved_profile, lens, plan_path, a) if needs_plan and resolved_profile else None

    return {
        "schema_version": "ppt_prompt_router.result.v3_1_3.direct_plan",
        "router_version": ROUTER_VERSION,
        "target_ppt_master": TARGET,
        "phase": a.phase,
        "action": (
            "generate_plan_then_start_fresh_ppt_master_context" if a.phase == "director"
            else ("invoke_router_director" if needs_plan else "invoke_ppt_master")
        ),
        "execution_path": {
            "id": path,
            "requires_presentation_plan": needs_plan,
            "director_protocol": protocol,
        },
        "intervention": {
            "mode": mode,
            "reason": reason,
            "generation_profile_hint": generation_profile,
        },
        "profile_selection": {
            "status": "arbitrate" if arbitrate else ("resolved" if resolved_profile else "bypass"),
            "primary_profile": None if not selected else {
                "id": selected["id"], "name_zh": selected["name_zh"], "confidence": confidence
            },
            "candidates": candidates,
            "arbitration_basis": "受众 + Communication Job + 预期Audience Move" if arbitrate else None,
        },
        "secondary_lens": lens,
        "source_intent": {
            "value": source_intent,
            "master_route_hint": intent_mod.route_hint(source_intent),
            "authoritative": False,
        },
        "director_task": {
            "status": (
                "ready" if task and a.phase == "director"
                else "prepared" if task
                else "not_migrated" if (mode == "full" and resolved_profile and not supports_direct_plan(resolved_profile))
                else "not_required" if resolved_profile
                else "bypass"
            ),
            "output_path": plan_path,
            "router_context_only": True,
            "task": task if a.phase == "director" else None,
        },
        "master_handoff": master_handoff(a, plan_path, source_intent),
        "request_context": {
            "original_user_request": a.user_request,
            "audience": a.audience,
            "delivery_purpose": a.delivery_purpose,
            "page_count": a.page_count,
            "format_hint": a.format,
            "materials": a.material,
            "reference_paths": a.reference_path,
            "template_paths": a.template_path,
            "workspace_roots": a.workspace_root,
            "workspace_intent": workspace_intent,
            "explicit_user_constraints": user_constraints(a),
        },
        "semantic_classification": sem,
    }


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    try:
        out = resolve(a)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        profile = out["profile_selection"]["primary_profile"]
        selected = profile["id"] if profile else "BYPASS"
        print(f"{out['phase']} / {out['intervention']['mode']}: {selected} -> {out['action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
