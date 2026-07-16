#!/usr/bin/env python3
"""PPT Director 3.0 single-Skill workflow dispatcher."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import os
import re
import shutil
import sys
import time
import uuid
import zipfile
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "ppt-master"
RUNTIME_SCRIPTS = RUNTIME / "scripts"
PUBLIC_COMMANDS = (
    "start", "mode-propose", "mode-select", "plan", "lock-spec", "page-begin",
    "page-check", "page-review", "page-pass", "sample-confirm", "sample-reject",
    "review", "status", "export",
)
TEMPLATE_INTENTS = {"reference_elements", "native_fill", "reusable_template", "none"}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.router_profile import (  # noqa: E402
    PackageError,
    compile_director_profile,
    load_index,
    validate_prompt_index,
)
from scripts.run_log import append_event, sha256  # noqa: E402
from scripts.director_runtime import (  # noqa: E402
    DirectorRuntimeError,
    capability_preflight,
    propose_mode,
    refresh_context,
    require_mode,
    select_mode,
)


class WorkflowError(PackageError):
    def __init__(self, message: str, *, code: str = "WORKFLOW_BLOCKED", next_actions: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.next_actions = next_actions or []


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"expected JSON object: {path}")
    return value


def _stage(project: Path | None) -> str | None:
    if project is None:
        return None
    path = project / "analysis" / "production_state.json"
    return str(_json(path).get("stage")) if path.is_file() else None


def _required(*paths: Path) -> list[dict[str, str | None]]:
    return [{"path": str(path.resolve()), "sha256": sha256(path)} for path in paths]


def _runtime_check() -> None:
    required = (RUNTIME / "MASTER.md", RUNTIME_SCRIPTS, RUNTIME / "references")
    if not all(path.exists() for path in required):
        raise WorkflowError("internal PPT Master runtime is incomplete", code="RUNTIME_INVALID")
    if any(RUNTIME.rglob("SKILL.md")):
        raise WorkflowError("internal runtime exposes a second Skill", code="RUNTIME_INVALID")


@contextmanager
def master_modules() -> Iterator[dict[str, Any]]:
    _runtime_check()
    sys.path.insert(0, str(RUNTIME_SCRIPTS))
    guard = importlib.import_module("runtime_guard")
    marker = guard.ROUTER_MARKER
    old = os.environ.get(marker)
    os.environ[marker] = uuid.uuid4().hex
    try:
        modules = {
            name: importlib.import_module(name)
            for name in ("project_manager", "director_plan", "production")
        }
        modules["runtime_guard"] = guard
        for name, module in modules.items():
            try:
                Path(module.__file__).resolve().relative_to(RUNTIME.resolve())
            except (AttributeError, ValueError) as exc:
                raise WorkflowError(
                    f"internal module loaded outside bundled runtime: {name}",
                    code="RUNTIME_INVALID",
                ) from exc
        yield modules
    finally:
        if old is None:
            os.environ.pop(marker, None)
        else:
            os.environ[marker] = old
        try:
            sys.path.remove(str(RUNTIME_SCRIPTS))
        except ValueError:
            pass


def _terms(entry: dict[str, Any], key: str) -> list[str]:
    value = entry.get(key) or []
    return [value] if isinstance(value, str) else [str(item) for item in value if str(item).strip()]


def score_profile(entry: dict[str, Any], text: str) -> tuple[int, dict[str, list[str]]]:
    lowered = text.lower()
    groups = {
        "primary": ("required_signals", 6), "strong": ("strong_signals", 3),
        "supporting": ("supporting_signals", 1), "negative": ("negative_signals", -5),
        "avoid_when": ("avoid_when", -8),
    }
    score, matched = 0, {}
    for label, (key, weight) in groups.items():
        hits = list(dict.fromkeys(term for term in _terms(entry, key) if term.lower() in lowered))
        if hits:
            matched[label] = hits
            score += weight * len(hits)
    return score, matched


def route_profile(index: dict[str, Any], text: str, *, prompt_id: str | None = None) -> dict[str, Any]:
    entries = validate_prompt_index(index)
    if prompt_id:
        entry = next((item for item in entries if item["id"] == prompt_id), None)
        if entry is None:
            raise WorkflowError(f"unknown prompt_id: {prompt_id}")
        return {"status": "selected", "entry": entry, "score": None, "matched": {"explicit": [prompt_id]}}
    ranked = []
    for entry in entries:
        score, matched = score_profile(entry, text)
        ranked.append({"entry": entry, "score": score, "matched": matched})
    ranked.sort(key=lambda item: (-item["score"], item["entry"]["id"]))
    first, second = ranked[0], ranked[1]
    if first["score"] < 3 or first["score"] - second["score"] < 2:
        return {"status": "needs_input", "question": "请确认本次 PPT 的主要场景。", "candidates": [
            {"id": item["entry"]["id"], "name": item["entry"]["name_zh"], "score": item["score"]}
            for item in ranked[:2]
        ]}
    return {"status": "selected", **first}


def detect_template_intent(request_text: str, template_paths: list[str], *, explicit: str | None = None) -> dict[str, Any]:
    if explicit:
        if explicit not in TEMPLATE_INTENTS:
            raise WorkflowError(f"unsupported template intent: {explicit}")
        if explicit != "none" and not template_paths:
            raise WorkflowError(f"template intent {explicit} requires a PPTX template")
        return {"status": "selected", "intent": explicit, "reason": "explicit"}
    if not template_paths:
        return {"status": "selected", "intent": "none", "reason": "no template supplied"}
    lowered = request_text.lower()
    signals = {
        "reusable_template": ("可复用模板", "模板工作区", "模板资产包"),
        "reference_elements": ("模板设计元素", "参考模板元素", "参考这个模板", "提炼设计语言", "不要套用", "不套版"),
        "native_fill": ("套用模板", "沿用原版式", "替换内容", "保持模板版式", "填充模板"),
    }
    active = [intent for intent, terms in signals.items() if any(term in lowered for term in terms)]
    if len(active) == 1:
        return {"status": "selected", "intent": active[0], "reason": "request signal"}
    return {"status": "selected", "intent": "reference_elements", "reason": "deferred to generation mode selection"}


def _docx_opening(path: Path, limit: int = 1200) -> str:
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read("word/document.xml"))
        return "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))[:limit]
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
        return ""


def material_context(paths: list[str]) -> str:
    chunks = []
    for raw in paths:
        path = Path(raw).expanduser()
        chunks.append(path.name)
        if path.suffix.lower() in {".md", ".txt"} and path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace")[:1200])
        elif path.suffix.lower() == ".docx" and path.is_file():
            chunks.append(_docx_opening(path))
    return "\n".join(chunks)


def _page_count(raw: int | None, request: str) -> int:
    if raw:
        return raw
    match = re.search(r"(\d{1,3})\s*页", request)
    if not match:
        raise WorkflowError("page count is required")
    return int(match.group(1))


def _write_contract(project: Path, entry: dict[str, Any], profile_text: str, args: argparse.Namespace, intent: str, template_path: str | None) -> Path:
    analysis = project / "analysis"
    profile = analysis / "director_profile.md"
    profile.write_text(profile_text, encoding="utf-8")
    source_files = [
        {"path": str(path.resolve()), "sha256": sha256(path)}
        for path in sorted((project / "sources").iterdir())
        if path.is_file() and path.suffix.lower() not in {".pptx", ".ppt", ".pptm"}
    ]
    template_hash = sha256(Path(template_path)) if template_path else None
    contract = {
        "schema_version": "3.1", "router_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "profile": {"id": entry["id"], "version": str(entry.get("version") or "3.0.0"), "sha256": sha256(profile), "validation_status": entry.get("validation_status", "experimental")},
        "request": args.request,
        "audience": args.audience or "未指定受众", "purpose": args.purpose or args.request,
        "page_count": _page_count(args.page_count, args.request),
        "source_files": source_files,
        "template": {"intent": intent, "path": template_path, "sha256": template_hash},
    }
    path = analysis / "director_contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


OperationEmitter = Callable[[Path, str, str, list[Path], list[Path], str | None], None]


def command_start(
    args: argparse.Namespace,
    modules: dict[str, Any],
    *,
    operation_emitter: OperationEmitter | None = None,
) -> tuple[Path, dict[str, Any]]:
    sources = [str(Path(path).expanduser().resolve()) for path in args.source]
    templates = [str(Path(path).expanduser().resolve()) for path in args.template]
    index = load_index(ROOT)
    audience = args.audience or ("政府领导" if "领导" in args.request else "未指定受众")
    routed = route_profile(index, "\n".join((args.request, audience, args.purpose or "", material_context(sources + templates))), prompt_id=args.prompt_id)
    if routed["status"] != "selected":
        raise WorkflowError(routed["question"], code="NEEDS_INPUT", next_actions=[item["id"] for item in routed["candidates"]])
    intent = detect_template_intent(args.request, templates, explicit=args.template_intent)
    if intent["status"] != "selected":
        raise WorkflowError(intent["question"], code="NEEDS_INPUT", next_actions=intent["candidates"])
    if len(templates) > 1:
        raise WorkflowError("only one primary template is supported")
    base = Path(args.project_base).expanduser().resolve() if args.project_base else (Path.home() / "PPT Director" / "projects")
    manager = modules["project_manager"].ProjectManager(base)
    with redirect_stdout(io.StringIO()):
        project = Path(manager.init_project(args.project_name or f"router_{routed['entry']['id']}", args.format, str(base))).resolve()
        imported = manager.import_sources(str(project), list(dict.fromkeys(sources)), copy=not args.move, move=args.move) if sources else {}
    template_path = None
    if templates:
        reference_dir = project / "references"
        reference_dir.mkdir(parents=True, exist_ok=True)
        source_template = Path(templates[0])
        destination = reference_dir / source_template.name
        if destination.exists():
            raise WorkflowError(f"reference PPTX already exists in project: {destination}")
        if args.move:
            shutil.move(str(source_template), destination)
        else:
            shutil.copy2(source_template, destination)
        template_path = str(destination.resolve())
    contract = _write_contract(project, routed["entry"], compile_director_profile(ROOT, routed["entry"]), args, intent["intent"], template_path)
    modules["production"].initialize_project(project)
    reporter = None
    if operation_emitter:
        reporter = lambda event_type, name, inputs, outputs, error: operation_emitter(project, event_type, name, inputs, outputs, error)
    snapshot = capability_preflight(project, RUNTIME, operation_reporter=reporter)
    contexts = _required(ROOT / "SKILL.md", RUNTIME / "MASTER.md", RUNTIME / "references" / "strategist.md", project / "analysis" / "director_profile.md", *sorted((project / "sources").glob("*.md")))
    return project, {"status": "director_pending", "project": str(project), "profile_id": routed["entry"]["id"], "template_intent": intent["intent"], "director_contract": str(contract), "capability_snapshot": str(project / ".director" / "capability_snapshot.json"), "available_modes": [key for key, value in snapshot["modes"].items() if value["status"] == "available_model_workflow"], "required_context": contexts, "next_allowed_actions": ["mode-propose"]}


def _project(args: argparse.Namespace) -> Path:
    project = Path(args.project).expanduser().resolve()
    if not (project / "analysis" / "director_contract.json").is_file():
        raise WorkflowError(f"not a managed project: {project}")
    return project


def dispatch(
    args: argparse.Namespace,
    modules: dict[str, Any],
    *,
    operation_emitter: OperationEmitter | None = None,
) -> tuple[Path, dict[str, Any], Any]:
    if args.command == "start":
        project, result = command_start(args, modules, operation_emitter=operation_emitter)
        return project, result, modules["project_manager"]
    project = _project(args)
    production, plan = modules["production"], modules["director_plan"]
    reporter = None
    if operation_emitter:
        reporter = lambda event_type, name, inputs, outputs, error: operation_emitter(project, event_type, name, inputs, outputs, error)
    if args.command == "mode-propose":
        return project, propose_mode(project, ROOT, RUNTIME, quality_preference=args.quality_preference, fidelity_requirement=args.fidelity_requirement, requested_mode=args.requested_mode, operation_reporter=reporter), sys.modules[__name__]
    if args.command == "mode-select":
        return project, select_mode(project, ROOT, RUNTIME, mode=args.mode, quality_preference=args.quality_preference, fidelity_requirement=args.fidelity_requirement, operation_reporter=reporter), sys.modules[__name__]
    if args.command == "plan":
        mode = require_mode(project)
        result = plan.install_director_plan(project, args.apply) if args.apply else plan.planning_context(project, ROOT, RUNTIME)
        result["generation_mode"] = mode["mode"]
        result.setdefault("required_context", []).append(str(project / ".director" / "master_handoff.md"))
        return project, result, plan
    if args.command == "lock-spec":
        require_mode(project)
        return project, production.lock_spec(project), production
    if args.command == "page-begin":
        mode = require_mode(project)
        plan_page = plan.page_by_id(plan.load_plan(project), args.page_id)
        ordered = [page["page_id"] for page in plan.plan_pages(plan.load_plan(project))]
        previous = ordered[ordered.index(args.page_id) - 1] if args.page_id in ordered and ordered.index(args.page_id) > 0 else None
        context = refresh_context(project, command="page-begin", page=plan_page, previous_page=previous, router_root=ROOT, runtime_root=RUNTIME)
        result = production.begin_page(project, args.page_id, ROOT, RUNTIME, direction=args.direction)
        result["context_rehydrate"] = context
        result["generation_mode"] = mode["mode"]
        result.setdefault("required_context", []).append(context["path"])
        return project, result, production
    if args.command == "page-check":
        return project, production.check_page(project), production
    if args.command == "page-review":
        state = production.status(project)
        page_id = state.get("active_page")
        context = refresh_context(project, command="page-review", page=plan.page_by_id(plan.load_plan(project), page_id) if page_id else None, router_root=ROOT, runtime_root=RUNTIME)
        result = production.install_page_review(project, args.apply) if args.apply else production.review_context(project, RUNTIME)
        result["context_rehydrate"] = context
        return project, result, production
    if args.command == "page-pass":
        return project, production.pass_page(project), production
    if args.command == "sample-confirm":
        return project, production.sample_confirm(project, args.decision, page_id=args.page_id, replacements=args.pages), production
    if args.command == "sample-reject":
        result = production.sample_reject(project, args.reason)
        context = refresh_context(project, command="sample-reject", router_root=ROOT, runtime_root=RUNTIME)
        result["context_rehydrate"] = context
        return project, result, production
    if args.command == "review":
        return project, production.record_review(project, args.kind, args.status, reviewed_pages=args.pages or []), production
    if args.command == "status":
        return project, production.status(project), production
    if args.command == "export":
        return project, production.export_deck(project, args.output), production
    raise WorkflowError(f"unsupported command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PPT Director 3.1")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--request", required=True); start.add_argument("--source", action="append", default=[]); start.add_argument("--template", action="append", default=[])
    start.add_argument("--template-intent", choices=sorted(TEMPLATE_INTENTS)); start.add_argument("--page-count", type=int); start.add_argument("--audience"); start.add_argument("--purpose"); start.add_argument("--prompt-id")
    start.add_argument("--format", default="ppt169"); start.add_argument("--project-name"); start.add_argument("--project-base"); start.add_argument("--move", action="store_true")
    propose = sub.add_parser("mode-propose"); propose.add_argument("project"); propose.add_argument("--quality-preference", choices=("speed", "balanced", "quality"), default="balanced"); propose.add_argument("--fidelity-requirement", choices=("light", "high", "mirror")); propose.add_argument("--requested-mode", choices=("standard", "template", "premium"))
    select = sub.add_parser("mode-select"); select.add_argument("project"); select.add_argument("--mode", required=True, choices=("standard", "template", "premium", "auto")); select.add_argument("--quality-preference", choices=("speed", "balanced", "quality"), default="balanced"); select.add_argument("--fidelity-requirement", choices=("light", "high", "mirror"))
    plan = sub.add_parser("plan"); plan.add_argument("project"); plan.add_argument("--apply")
    lock = sub.add_parser("lock-spec"); lock.add_argument("project")
    begin = sub.add_parser("page-begin"); begin.add_argument("project"); begin.add_argument("page_id"); begin.add_argument("--direction", choices=("A", "B", "C"))
    check = sub.add_parser("page-check"); check.add_argument("project")
    review_page = sub.add_parser("page-review"); review_page.add_argument("project"); review_page.add_argument("--apply")
    passed = sub.add_parser("page-pass"); passed.add_argument("project")
    confirm = sub.add_parser("sample-confirm"); confirm.add_argument("project"); confirm.add_argument("decision", choices=("A", "B", "C")); confirm.add_argument("--page-id"); confirm.add_argument("--pages", nargs="*")
    reject = sub.add_parser("sample-reject"); reject.add_argument("project"); reject.add_argument("--reason", required=True)
    review = sub.add_parser("review"); review.add_argument("project"); review.add_argument("kind", choices=("midpoint", "deck")); review.add_argument("--status", required=True, choices=("passed", "failed")); review.add_argument("--pages", nargs="*")
    status = sub.add_parser("status"); status.add_argument("project")
    export = sub.add_parser("export"); export.add_argument("project"); export.add_argument("--output")
    return parser


def _event_files(project: Path, command: str) -> tuple[list[Path], list[Path]]:
    analysis = project / "analysis"
    shared_inputs = [
        analysis / "director_contract.json", analysis / "director_profile.md",
        analysis / "director_plan.json", project / "design_spec.md", project / "spec_lock.md",
        project / ".director" / "capability_snapshot.json",
        project / ".director" / "generation_mode.json",
        project / ".director" / "master_handoff.md",
        project / ".director" / "context_rehydrate.md",
        project / ".director" / "selected_sample.json",
    ]
    current = project / ".page_work" / "current.svg"
    inputs = [*shared_inputs, current]
    outputs = [analysis / "production_state.json"]
    if command == "start":
        outputs.extend((analysis / "director_contract.json", analysis / "director_profile.md"))
        outputs.append(project / ".director" / "capability_snapshot.json")
    elif command == "mode-select":
        outputs.extend((project / ".director" / "generation_mode.json", project / ".director" / "master_handoff.md"))
    elif command == "sample-reject":
        outputs.append(project / ".director" / "sample_feedback.md")
    elif command == "plan":
        outputs.append(analysis / "director_plan.json")
    elif command in {"page-check", "page-review", "page-pass"}:
        state = _json(analysis / "production_state.json") if (analysis / "production_state.json").is_file() else {}
        page_id = state.get("active_page")
        if page_id:
            outputs.extend((project / ".preview" / f"{page_id}.png", project / ".review" / f"{page_id}.json", project / "svg_output" / f"{page_id}.svg"))
        elif command == "page-pass":
            outputs.extend(sorted((project / "svg_output").glob("*.svg")))
    elif command == "export":
        outputs.extend(project.glob("exports/*.pptx"))
    return inputs, outputs


def main(argv: list[str] | None = None) -> int:
    run_id, project, before, module_file = uuid.uuid4().hex, None, None, __file__
    started_at = datetime.now(timezone.utc).isoformat()
    started_clock = time.monotonic()
    args = None
    operation_ids: dict[str, str] = {}

    def emit_operation(
        event_project: Path,
        event_type: str,
        operation_name: str,
        inputs: list[Path],
        outputs: list[Path],
        error: str | None,
    ) -> None:
        operation_id = operation_ids.setdefault(operation_name, f"{run_id}:op:{len(operation_ids) + 1}")
        now = datetime.now(timezone.utc).isoformat()
        stage = _stage(event_project)
        mode_path = event_project / ".director" / "generation_mode.json"
        mode = _json(mode_path).get("mode") if mode_path.is_file() else None
        append_event(
            event_project,
            run_id=f"{run_id}:{operation_name}:{event_type}",
            operation_id=operation_id,
            command=args.command if args else "unknown",
            module="director_runtime",
            module_file=Path(__file__).with_name("director_runtime.py"),
            inputs=inputs,
            outputs=outputs,
            stage_before=stage,
            stage_after=stage,
            exit_code=None if event_type in {"tool_started", "model_workflow_context_issued"} else (0 if event_type in {"tool_completed", "model_workflow_artifacts_observed"} else 3),
            error_code="TOOL_FAILED" if event_type == "tool_failed" else ("WORKFLOW_BLOCKED" if event_type == "model_workflow_gate_failed" else None),
            event_type=event_type,
            started_at=now,
            finished_at=now,
            duration_seconds=0.0,
            mode=mode,
            details={"operation_name": operation_name, "expected_outputs": [str(path) for path in outputs], "error": error} if error else {"operation_name": operation_name, "expected_outputs": [str(path) for path in outputs]},
        )

    try:
        args = build_parser().parse_args(argv)
        if args.command != "start":
            project = Path(args.project).expanduser().resolve()
            before = _stage(project)
        with master_modules() as modules:
            project, result, module = dispatch(args, modules, operation_emitter=emit_operation)
            module_file = module.__file__
        after = _stage(project)
        inputs, outputs = _event_files(project, args.command)
        event_types = {
            "mode-propose": "mode_proposed", "mode-select": "mode_selected",
            "sample-confirm": "sample_selected", "sample-reject": "sample_rejected",
            "page-begin": "context_rehydrated", "page-check": "ppt_master_call_finished",
            "export": "export_finished",
        }
        mode_path = project / ".director" / "generation_mode.json"
        mode = _json(mode_path).get("mode") if mode_path.is_file() else None
        page_id = getattr(args, "page_id", None)
        if args.command == "plan" and not args.apply:
            emit_operation(project, "model_workflow_context_issued", "strategist_plan", [project / ".director" / "master_handoff.md"], [project / "analysis" / "director_plan.json"], None)
        elif args.command == "plan" and args.apply:
            emit_operation(project, "model_workflow_artifacts_observed", "strategist_plan", [Path(args.apply)], [project / "analysis" / "director_plan.json"], None)
            emit_operation(project, "model_workflow_context_issued", "design_system", [project / "analysis" / "director_plan.json", project / ".director" / "master_handoff.md"], [project / "design_spec.md", project / "spec_lock.md"], None)
        elif args.command == "lock-spec":
            emit_operation(project, "model_workflow_artifacts_observed", "design_system", [project / "analysis" / "director_plan.json"], [project / "design_spec.md", project / "spec_lock.md"], None)
        append_event(project, run_id=run_id, command=args.command, module=module.__name__, module_file=module_file, inputs=inputs, outputs=outputs, stage_before=before, stage_after=after, exit_code=0, event_type=event_types.get(args.command), started_at=started_at, duration_seconds=round(time.monotonic() - started_clock, 6), mode=mode, page_id=page_id, details={"capability_snapshot_refreshed": result.get("capability_snapshot_refreshed")} if isinstance(result, dict) else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PackageError, RuntimeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "ERROR")
        actions = getattr(exc, "next_actions", [])
        after = _stage(project) if project and project.exists() else before
        if project and (project / "analysis" / "director_contract.json").is_file():
            inputs, outputs = _event_files(project, getattr(args, "command", "unknown"))
            mode_path = project / ".director" / "generation_mode.json"
            mode = _json(mode_path).get("mode") if mode_path.is_file() else None
            if getattr(args, "command", None) == "lock-spec" and mode in {"template", "premium"}:
                emit_operation(project, "model_workflow_gate_failed", "design_system", [project / "analysis" / "director_plan.json"], [project / "design_spec.md", project / "spec_lock.md"], str(exc))
            append_event(project, run_id=run_id, command=getattr(args, "command", "unknown"), module="route", module_file=module_file, inputs=inputs, outputs=outputs, stage_before=before, stage_after=after, exit_code=3, error_code=code, event_type="command_failed", started_at=started_at, duration_seconds=round(time.monotonic() - started_clock, 6), mode=mode, page_id=getattr(args, "page_id", None))
        print(json.dumps({"status": "error", "error_code": code, "error": str(exc), "next_allowed_actions": actions}, ensure_ascii=False, indent=2))
        return 2 if code == "NEEDS_INPUT" else 3


if __name__ == "__main__":
    raise SystemExit(main())
