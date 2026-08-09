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
DIRECTOR_PROTOCOL = "V15"
SEMANTIC_FIELDS = (
    "page_role", "audience_move", "relationship",
    "hierarchy", "rhythm_intent", "visual_semantics",
)
QUALITY_PRIORITY = "不考虑 Token、工具调用和思考次数，以最终汇报效果为优先，充分发挥 PPT Master 原生完整能力。"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PPT Prompt Router 3.1.3 semantic director interface")
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
    p.add_argument("--prompt-id")
    p.add_argument("--stage1-contract")
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


def read_stage1_contract(value: str | None) -> tuple[str, str | None]:
    if not value:
        return "", None
    p = Path(value).expanduser()
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        return text, str(p.resolve())
    return value, None


def director_base(profile: dict, lens: str | None) -> dict:
    refs = ROOT / "references"
    kernel = file_text(refs / "director_kernel.md")
    vocab = file_text(refs / "ppt_semantic_vocabulary.md")
    profile_path = ROOT / profile["file"]
    profile_text = file_text(profile_path)
    lens_text = ""
    lens_path = None
    if lens:
        p = ROOT / "lenses" / f"{lens}.md"
        if p.is_file():
            lens_path = str(p.resolve())
            lens_text = file_text(p)
    chunks = [
        "# Director Runtime Payload",
        f"Router: {ROUTER_VERSION}",
        f"Primary Profile: {profile['id']} / {profile.get('name_zh','')}",
        "\n## Director Kernel\n" + kernel,
        "\n## Semantic Vocabulary\n" + vocab,
        "\n## Primary Profile\n" + profile_text,
    ]
    if lens_text:
        chunks.append("\n## Secondary Lens\n" + lens_text)
    base = "\n".join(chunks).strip()
    return {
        "profile_path": str(profile_path.resolve()),
        "profile_sha256": sha_text(profile_text),
        "secondary_lens_path": lens_path,
        "base_prompt": base,
        "base_prompt_sha256": sha_text(base),
    }


def presentation_plan_path(project_dir: str | None) -> str:
    if project_dir:
        return str((Path(project_dir).expanduser() / "analysis" / "presentation_plan.md").resolve())
    return "analysis/presentation_plan.md"


def compile_director_handoff(profile: dict | None, lens: str | None, mode: str, phase: str,
                             stage1_contract: str, stage1_source: str | None, project_dir: str | None) -> dict:
    refs = ROOT / "references"
    out = {
        "protocol": DIRECTOR_PROTOCOL,
        "intervention": mode,
        "activation_point": "after_stage1_confirmation",
        "semantic_fields": list(SEMANTIC_FIELDS),
        "output_path": presentation_plan_path(project_dir),
        "mapping_protocol_path": str((refs / "ppt_master_4_4_mapping_protocol.md").resolve()),
        "capability_map_path": str((refs / "ppt_master_design_capability_map.md").resolve()),
        "brief_template_path": str((refs / "director_brief_template.md").resolve()),
        "status": "bypass" if profile is None else ("ready" if phase == "director" else "prepared"),
        "profile_path": None,
        "profile_sha256": None,
        "secondary_lens_path": None,
        "base_prompt": None,
        "inline_prompt": None,
        "inline_prompt_sha256": None,
        "stage1_contract_source": stage1_source,
        "stage1_sha256": sha_text(stage1_contract) if stage1_contract else None,
    }
    if profile is None:
        return out
    base = director_base(profile, lens)
    out.update(base)
    if phase == "director":
        if not stage1_contract:
            raise ValueError("director phase needs --stage1-contract with the confirmed Stage 1 communication contract")
        trace = (
            "<!-- router_trace\n"
            f"router_version: {ROUTER_VERSION}\n"
            f"primary_profile: {profile['id']}\n"
            f"profile_sha256: {base['profile_sha256']}\n"
            f"stage1_sha256: {sha_text(stage1_contract)}\n"
            "-->"
        )
        prompt = f"""{QUALITY_PRIORITY}

{base['base_prompt']}

## Confirmed Stage 1 Communication Contract
{stage1_contract.strip()}

## Current Director Task
Router 仅编译本次专业导演 handoff，不直接生成页面计划。当前主智能体现在切换为专业 Director：完整读取原始材料、用户明确要求和以上已确认 Communication Contract，执行当前 Primary Profile 的专业导演方法，实际生成 `{out['output_path']}`。

`presentation_plan.md` 开头写入以下追踪头，随后形成 Deck North Star 和完整逐页策划：

{trace}

每页落实 `page_role / audience_move / relationship / hierarchy / rhythm_intent / visual_semantics` 六字段，同时给出 Core message、适合上屏的 Content、Evidence / image material 与 Speaker Notes。事实、数据、案例、机制、问题和建议以原始材料为依据；表达可按领导汇报需要完成归纳、合并、拆分、重组和凝练。

完成 `presentation_plan.md` 后，将它作为 PPT Master Stage 2 的首要页面语义来源。正常形成的计划、Design Spec、Spec Lock 与最终页面共同构成本次研发审计证据；不要为追踪另建页面状态或质量门禁。""".strip()
        out["inline_prompt"] = prompt
        out["inline_prompt_sha256"] = sha_text(prompt)
    return out


def stage2_design_activation(plan_path: str) -> dict:
    text = f"""Stage 2 从 `{plan_path}` 开始，结合 Stage 1 确认、原始材料、已确认模板与当前项目完成二次编译。

Visual Style 统一颜色、字体、线条、材质、图像处理、图标和整体气质；每页空间结构由 `relationship / hierarchy / rhythm_intent / visual_semantics` 决定。

关系明确的页面先做一次语义 Visualization Recall / 能力族召回，再结合页面角色、内容密度、模板和全篇节奏选择候选、组合候选或自由设计。等权并列、KPI、短清单适合卡片或面板；递进、流程、汇聚、对比、层级、系统、主张-证据等页面优先体现对应真实结构。

Page Rhythm 综合页面角色、Audience Move、真实关系、信息密度和章节位置形成全篇节奏；关键成果与章节转折形成视觉停顿。图片角色与位置随页面语义变化，可采用侧证据、横幅、局部大图、背景图或小型佐证。

Executor 围绕 page-scale composition 先完成语义骨架，再充分发挥 Visualization、Native Shape、Charts / Diagrams、SVG、图片融合、数据表达、Visual Job Router、Live Preview 与当前页面适用的其他 PPT Master 原生能力。

卡片依赖、连续 dense 与构图重复只作为审阅时的诊断信号，不设数量配额。没有特殊关系时，清晰、稳健的排版就是合适的设计。""".strip()
    return {
        "semantic_source": plan_path,
        "activation_prompt": text,
        "activation_sha256": sha_text(text),
        "visual_style_scope": "project_identity_and_aesthetic",
        "page_composition_driver": "relationship + hierarchy + rhythm_intent + visual_semantics",
        "relationship_recall": "semantic_recall_before_final_composition_when_relationship_is_explicit",
        "image_role": "page_semantics_driven",
    }


def execution_policy(generation_profile: str, workspace_roots: list[str], workspace_intent: str, plan_path: str,
                     selected_profile_id: str | None) -> dict:
    resume = None
    if selected_profile_id:
        resume = (
            "Stage 1确认后再次运行同一个 scripts/route.py，使用 `--phase director --prompt-id "
            f"{selected_profile_id} --stage1-contract <confirmed-stage1-json-or-path>`，并保留本次原始任务、材料、project-dir与workspace参数。"
        )
    default_generate = {
        "stage_1": "完整理解原始材料、汇报对象、使用场景和明确约束，按 PPT Master 原生流程完成项目初始化、Communication Contract、Template Candidate Preparation 与 Stage 1确认。",
        "director_resume": resume,
        "director": f"执行 Director Runtime Payload，生成 `{plan_path}`；该文件承载故事主线、页面任务、核心观点、六字段页面语义、事实内容、素材和 Speaker Notes。",
        "stage_2": f"Stage 2 从 `{plan_path}` 开始，应用 `stage2_handoff.activation_prompt` 完成二次编译，再形成完整 `design_spec.md`。",
        "spec_lock": "Stage 2确认后，按 PPT Master 原生机制完成 design_spec.md、spec_lock.md 及实际命中的资源获取流程。",
        "executor": f"{QUALITY_PRIORITY} 围绕每页目标、核心观点、真实关系、信息层级和全篇视觉节奏，由 PPT Master Executor 逐页自主完成 page-scale composition，并充分发挥当前页面适用的原生视觉能力。",
        "review_export": "页面生产完成后，按 PPT Master 当前原生流程完成 Final Quality Check、当前任务适用的 Visual Review、Speaker Notes、后处理、Export 与 Postflight。",
    }
    return {
        "quality_priority": QUALITY_PRIORITY,
        "master_boot": "完整读取 PPT Master SKILL.md 及本任务实际命中的工作流；由 PPT Master 当前 routing 权威确定最终 Route。",
        "default_generate": default_generate,
        "generation_profile_hint": generation_profile,
        "workspace_roots": workspace_roots,
        "workspace_intent": workspace_intent,
        "application": "Default Generate 采用 Stage 1 → Director V15 → presentation_plan.md → Stage 2 → Design Spec/Lock → Executor 的交接；Quick、Beautify、Fill Native、Enhance Native、Create Template 沿用各自 Master 原生流程，并按 Router intervention 深度吸收专业语义。",
    }


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
    stage1_contract, stage1_source = read_stage1_contract(a.stage1_contract)
    if a.phase == "director" and (mode == "bypass" or resolved_profile is None):
        raise ValueError("director phase needs a resolved Director profile")

    plan_path = presentation_plan_path(a.project_dir)
    workspace_intent = a.workspace_intent or ("explicit_use_requested" if a.workspace_root else "candidate")
    handoff = compile_director_handoff(
        resolved_profile, lens, mode, a.phase, stage1_contract, stage1_source, a.project_dir
    )
    selected_id = resolved_profile["id"] if resolved_profile else None

    return {
        "schema_version": "ppt_prompt_router.result.v3_1_3",
        "router_version": ROUTER_VERSION,
        "target_ppt_master": TARGET,
        "phase": a.phase,
        "action": "invoke_ppt_master" if a.phase == "preflight" else "execute_director_then_resume_ppt_master",
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
        "director_handoff": handoff,
        "stage2_handoff": stage2_design_activation(plan_path) if resolved_profile else None,
        "execution_policy": execution_policy(
            generation_profile, a.workspace_root, workspace_intent, plan_path, selected_id
        ),
        "master_handoff": {
            "authority": "PPT Master",
            "route_authority": "PPT Master SKILL.md + workflows/routing.md",
            "instruction": f"{QUALITY_PRIORITY} 从 PPT Master 自己的 SKILL.md 开始，完整读取实际命中的工作流。Default Generate 完成 Stage 1 确认后执行 Router director phase 与 presentation_plan.md，再进入 Stage 2；PPT Master 继续负责 Route、确认、Strategist、Design Spec/Lock、Executor、原生质量流程与导出。",
        },
        "request_context": {
            "original_user_request": a.user_request,
            "audience": a.audience,
            "delivery_purpose": a.delivery_purpose,
            "page_count": a.page_count,
            "format_hint": a.format,
            "materials": a.material,
            "reference_paths": refs,
            "workspace_roots": a.workspace_root,
            "workspace_intent": workspace_intent,
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
