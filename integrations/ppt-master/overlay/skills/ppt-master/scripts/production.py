#!/usr/bin/env python3
"""Deterministic workflow gates for PPT Director managed projects."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_FILE = Path("analysis/production_state.json")
CURRENT_FILE = Path(".page_work/current.svg")
STAGES = {
    "director_pending", "design_pending", "sample_production", "sample_confirmation",
    "production", "midpoint_required", "deck_review_required", "export_ready",
    "exported", "repair_required",
}
TOP_LEVEL_FIELDS = {
    "stage", "active_page", "global_hashes", "samples", "pages",
    "midpoint_review", "deck_review", "export",
}


class ProductionError(RuntimeError):
    def __init__(self, message: str, *, next_actions: list[str] | None = None):
        super().__init__(message)
        self.code = "WORKFLOW_BLOCKED"
        self.next_actions = next_actions or []


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _project(value: str | Path) -> Path:
    project = Path(value).expanduser().resolve()
    if not (project / "analysis" / "director_contract.json").is_file():
        raise ProductionError(f"not a managed PPT Director project: {project}")
    return project


def _state_path(project: Path) -> Path:
    return project / STATE_FILE


def _load(project: Path) -> dict[str, Any]:
    path = _state_path(project)
    if not path.is_file():
        raise ProductionError("production_state.json is missing", next_actions=["start"])
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionError(f"invalid production state: {exc}") from exc
    if set(state) != TOP_LEVEL_FIELDS:
        raise ProductionError("production state has unsupported top-level fields")
    if state.get("stage") not in STAGES:
        raise ProductionError(f"unsupported production stage: {state.get('stage')}")
    return state


def _save(project: Path, state: dict[str, Any]) -> None:
    if set(state) != TOP_LEVEL_FIELDS or state["stage"] not in STAGES:
        raise ProductionError("refusing to write invalid production state")
    _atomic_json(_state_path(project), state)


def _plan(project: Path) -> dict[str, Any]:
    from director_plan import load_plan
    return load_plan(project)


def _pages(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan["pages"])


def _sample_ids(plan: dict[str, Any]) -> list[str]:
    return [item["page_id"] for item in plan["sample_pages"]]


def _page(state: dict[str, Any], page_id: str) -> dict[str, Any]:
    try:
        return state["pages"][page_id]
    except KeyError as exc:
        raise ProductionError(f"unknown page: {page_id}") from exc


def _page_record() -> dict[str, Any]:
    return {
        "state": "pending", "svg_hash": None, "png_hash": None,
        "machine_check_hash": None, "review_report_hash": None,
        "reviewed_png_hash": None, "review_passed": False,
        "blocking_issues": [], "notes_hash": None,
        "input_hash": None,
    }


def _global_files(project: Path) -> dict[str, Path]:
    return {
        "director_contract_hash": project / "analysis" / "director_contract.json",
        "director_profile_hash": project / "analysis" / "director_profile.md",
        "director_plan_hash": project / "analysis" / "director_plan.json",
        "design_spec_hash": project / "design_spec.md",
        "spec_lock_hash": project / "spec_lock.md",
        "capability_snapshot_hash": project / ".director" / "capability_snapshot.json",
        "generation_mode_hash": project / ".director" / "generation_mode.json",
        "master_handoff_hash": project / ".director" / "master_handoff.md",
        "selected_sample_hash": project / ".director" / "selected_sample.json",
    }


def _current_source_hashes(project: Path) -> list[dict[str, str | None]]:
    contract = _load_json(project / "analysis" / "director_contract.json") or {}
    rows = []
    for row in contract.get("source_files") or []:
        if not isinstance(row, dict) or not row.get("path"):
            continue
        path = Path(str(row["path"])).expanduser()
        try:
            logical_path = path.resolve().relative_to(project.resolve()).as_posix()
        except ValueError:
            logical_path = path.name
        rows.append({"logical_path": logical_path, "sha256": _sha256(path)})
    return sorted(rows, key=lambda item: (item["logical_path"], item["sha256"] or ""))


def _current_template_hash(project: Path) -> str | None:
    contract = _load_json(project / "analysis" / "director_contract.json") or {}
    raw = (contract.get("template") or {}).get("path")
    return _sha256(Path(str(raw)).expanduser()) if raw else None


def _mode_semantic_hash(project: Path) -> str | None:
    mode = _load_json(project / ".director" / "generation_mode.json")
    if not mode:
        return None
    inputs = mode.get("semantic_inputs")
    if not isinstance(inputs, dict):
        return mode.get("mode_semantic_hash") or _sha256(project / ".director" / "generation_mode.json")
    current = dict(inputs)
    current["source_hashes"] = _current_source_hashes(project)
    current["template_hash"] = _current_template_hash(project)
    return _canonical_hash(current)


def _global_hash(project: Path, key: str, path: Path) -> str | None:
    if key == "capability_snapshot_hash":
        snapshot = _load_json(path) or {}
        return snapshot.get("capability_semantic_hash") or _sha256(path)
    if key == "generation_mode_hash":
        return _mode_semantic_hash(project)
    return _sha256(path)


def _current_globals(project: Path) -> dict[str, str | None]:
    return {key: _global_hash(project, key, path) for key, path in _global_files(project).items()}


def _clear_reviews(state: dict[str, Any]) -> None:
    state["midpoint_review"] = {"status": "pending", "reviewed_pages": []}
    state["deck_review"] = {"status": "pending", "reviewed_pages": [], "blocking_issues": []}
    state["export"] = {"path": None, "pptx_hash": None, "input_hashes": {}}


def _invalidate_page(record: dict[str, Any], *, state: str = "repair_required", svg: bool = False, notes: bool = False) -> None:
    record["state"] = state
    if svg:
        record["svg_hash"] = None
        record["png_hash"] = None
        record["machine_check_hash"] = None
    if notes:
        record["notes_hash"] = None
    record["review_report_hash"] = None
    record["reviewed_png_hash"] = None
    record["review_passed"] = False
    record["blocking_issues"] = []


def _notes_path(project: Path, page_id: str) -> Path:
    for suffix in (".md", ".txt"):
        candidate = project / "notes" / f"{page_id}{suffix}"
        if candidate.is_file():
            return candidate
    total = project / "notes" / "total.md"
    return total if total.is_file() else project / "notes" / f"{page_id}.md"


def _output_path(project: Path, page_id: str) -> Path:
    return project / "svg_output" / f"{page_id}.svg"


def _review_path(project: Path, page_id: str) -> Path:
    return project / ".review" / f"{page_id}.json"


def _preview_path(project: Path, page_id: str) -> Path:
    return project / ".preview" / f"{page_id}.png"


def initialize_project(project_path: str | Path) -> dict[str, Any]:
    project = _project(project_path)
    if _state_path(project).exists():
        raise ProductionError("production state already exists")
    state = {
        "stage": "director_pending", "active_page": None, "global_hashes": _current_globals(project),
        "samples": {"page_ids": [], "status": "pending", "approved_hashes": {}},
        "pages": {}, "midpoint_review": {"status": "pending", "reviewed_pages": []},
        "deck_review": {"status": "pending", "reviewed_pages": [], "blocking_issues": []},
        "export": {"path": None, "pptx_hash": None, "input_hashes": {}},
    }
    _save(project, state)
    return state


def _generation_mode(project: Path) -> dict[str, Any]:
    path = project / ".director" / "generation_mode.json"
    if not path.is_file():
        return {"mode": "standard", "sample_strategy": "single"}
    return json.loads(path.read_text(encoding="utf-8"))


def _sample_state(project: Path, page_ids: list[str]) -> dict[str, Any]:
    mode = _generation_mode(project)
    if mode.get("sample_strategy") != "three_groups":
        return {"page_ids": page_ids, "status": "pending", "approved_hashes": {}}
    return {
        "page_ids": page_ids, "status": "pending", "approved_hashes": {},
        "strategy": "three_groups", "round": 1, "active_direction": None,
        "directions": {
            direction: {"pages": {page_id: _page_record() for page_id in page_ids}}
            for direction in ("A", "B", "C")
        },
    }


def attach_director_plan(project_path: str | Path) -> dict[str, Any]:
    project = _project(project_path)
    state, plan = _load(project), _plan(project)
    if state["stage"] != "director_pending" or state["pages"]:
        raise ProductionError("director plan can only be attached once in director_pending")
    state["pages"] = {page["page_id"]: _page_record() for page in _pages(plan)}
    state["samples"] = _sample_state(project, _sample_ids(plan))
    state["global_hashes"] = _current_globals(project)
    state["stage"] = "design_pending"
    _save(project, state)
    return state


def _required_typography(profile_id: str) -> tuple[int, int, int]:
    return (20, 16, 12) if profile_id in {"government_strategy", "decision_meeting"} else (18, 16, 12)


def lock_spec(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state)
    if state["stage"] not in {"design_pending", "repair_required"}:
        raise ProductionError("spec can only be locked in design_pending or repair_required", next_actions=["status"])
    design, lock = project / "design_spec.md", project / "spec_lock.md"
    if not design.is_file() or not lock.is_file() or not design.read_text(encoding="utf-8").strip() or not lock.read_text(encoding="utf-8").strip():
        raise ProductionError("design_spec.md and spec_lock.md must be complete before samples")
    contract = json.loads((project / "analysis" / "director_contract.json").read_text(encoding="utf-8"))
    minimums = _required_typography(str(contract["profile"]["id"]))
    marker = f"minimum_font_sizes: body={minimums[0]}px supporting={minimums[1]}px footnote={minimums[2]}px"
    if marker not in lock.read_text(encoding="utf-8"):
        raise ProductionError(f"spec_lock.md must freeze: {marker}")
    state["global_hashes"] = _current_globals(project)
    state["stage"] = "sample_production"
    _save(project, state)
    return {"stage": state["stage"], "sample_pages": state["samples"]["page_ids"], "next_allowed_actions": ["page-begin <sample_page_id>"]}


def _sample_snapshot(project: Path, page_id: str) -> dict[str, str | None]:
    return {"svg_hash": _sha256(_output_path(project, page_id)), "png_hash": _sha256(_preview_path(project, page_id)), "review_hash": _sha256(_review_path(project, page_id))}


def _sample_root(project: Path, state: dict[str, Any], direction: str) -> Path:
    return project / ".director" / "samples" / f"round-{int(state['samples'].get('round', 1)):03d}" / direction


def _sample_paths(project: Path, state: dict[str, Any], direction: str, page_id: str) -> tuple[Path, Path, Path]:
    root = _sample_root(project, state, direction)
    return root / "svg" / f"{page_id}.svg", root / "preview" / f"{page_id}.png", root / "review" / f"{page_id}.json"


def _sample_record(state: dict[str, Any], direction: str, page_id: str) -> dict[str, Any]:
    try:
        return state["samples"]["directions"][direction]["pages"][page_id]
    except KeyError as exc:
        raise ProductionError(f"unknown sample direction/page: {direction}/{page_id}") from exc


def _active_record(state: dict[str, Any], page_id: str) -> dict[str, Any]:
    direction = state["samples"].get("active_direction")
    return _sample_record(state, direction, page_id) if direction else _page(state, page_id)


def _active_paths(project: Path, state: dict[str, Any], page_id: str) -> tuple[Path, Path, Path]:
    direction = state["samples"].get("active_direction")
    if direction:
        return _sample_paths(project, state, direction, page_id)
    return _output_path(project, page_id), _preview_path(project, page_id), _review_path(project, page_id)


def reconcile(project_path: str | Path, state: dict[str, Any] | None = None) -> list[str]:
    project = _project(project_path)
    state = state or _load(project)
    was_exported = state["stage"] == "exported"
    changes: list[str] = []
    current_globals = _current_globals(project)
    recorded = state["global_hashes"]
    changed_globals = [key for key, value in current_globals.items() if recorded.get(key) not in {None, value}]
    if changed_globals:
        for record in state["pages"].values():
            _invalidate_page(record, state="repair_required", svg=True, notes=True)
        previous_samples = state.get("samples") or {}
        state["samples"] = _sample_state(project, _sample_ids(_plan(project)) if current_globals["director_plan_hash"] else [])
        if state["samples"].get("strategy") == "three_groups":
            state["samples"]["round"] = int(previous_samples.get("round", 0)) + 1
        _clear_reviews(state)
        state["stage"] = (
            "design_pending"
            if set(changed_globals).issubset({"design_spec_hash", "spec_lock_hash"}) and not was_exported
            else "repair_required"
        )
        changes.extend(changed_globals)
        state["global_hashes"] = current_globals

    active = state.get("active_page")
    for page_id, record in state["pages"].items():
        svg_path = project / CURRENT_FILE if active == page_id else _output_path(project, page_id)
        current_svg = _sha256(svg_path)
        current_notes = _sha256(_notes_path(project, page_id))
        if record.get("svg_hash") and record["svg_hash"] != current_svg:
            _invalidate_page(record, state="active" if active == page_id else "repair_required", svg=True)
            changes.append(f"svg:{page_id}")
        if record.get("notes_hash") != current_notes and (record.get("notes_hash") is not None or current_notes is not None) and record.get("state") == "passed":
            _invalidate_page(record, notes=True)
            changes.append(f"notes:{page_id}")
        review = _review_path(project, page_id)
        preview = _preview_path(project, page_id)
        if record.get("review_report_hash") and record["review_report_hash"] != _sha256(review):
            _invalidate_page(record)
            changes.append(f"review:{page_id}")
        if record.get("png_hash") and record["png_hash"] != _sha256(preview):
            _invalidate_page(record)
            record["png_hash"] = None
            changes.append(f"png:{page_id}")

    approved = state["samples"].get("approved_hashes") or {}
    if approved and any(approved.get(page_id) != _sample_snapshot(project, page_id) for page_id in state["samples"]["page_ids"]):
        state["samples"]["approved_hashes"] = {}
        state["samples"]["status"] = "pending"
        state["stage"] = "sample_production"
        changes.append("sample_approval")
    if state["stage"] == "production" and state["midpoint_review"]["status"] == "passed":
        ordered = [page["page_id"] for page in _pages(_plan(project))]
        if ordered and _all_passed(state, ordered):
            state["stage"] = "deck_review_required"
            changes.append("deck_review_required")
    if changes:
        _clear_reviews(state)
        if was_exported:
            state["stage"] = "repair_required"
        _save(project, state)
    return changes


def _next_actions(state: dict[str, Any]) -> list[str]:
    stage = state["stage"]
    return {
        "director_pending": ["plan"], "design_pending": ["lock-spec"],
        "sample_production": ["page-begin"], "sample_confirmation": ["sample-confirm A|B|C"],
        "production": ["page-begin"], "midpoint_required": ["review midpoint"],
        "deck_review_required": ["review deck"], "export_ready": ["export"],
        "exported": ["status"], "repair_required": ["page-begin <repair_page>", "status"],
    }[stage]


def status(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    changes = reconcile(project, state)
    state = _load(project)
    return {"stage": state["stage"], "active_page": state["active_page"], "changes": changes, "samples": state["samples"], "pages": state["pages"], "next_allowed_actions": _next_actions(state)}


def _director_page(project: Path, page_id: str) -> dict[str, Any]:
    page = next((item for item in _pages(_plan(project)) if item["page_id"] == page_id), None)
    if page is None:
        raise ProductionError(f"page is not in director plan: {page_id}")
    return page


def begin_page(project_path: str | Path, page_id: str, router_root: str | Path, runtime_root: str | Path, *, direction: str | None = None) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    if state["active_page"]:
        raise ProductionError(f"active page must finish first: {state['active_page']}")
    allowed = state["stage"] in {"sample_production", "production", "repair_required"}
    if not allowed:
        raise ProductionError(f"page production is blocked in {state['stage']}", next_actions=_next_actions(state))
    if state["stage"] == "sample_production" and page_id not in state["samples"]["page_ids"]:
        raise ProductionError("only selected samples may be produced before confirmation")
    grouped = state["stage"] == "sample_production" and state["samples"].get("strategy") == "three_groups"
    if grouped and direction not in {"A", "B", "C"}:
        raise ProductionError("template/premium samples require --direction A, B, or C")
    if not grouped and direction:
        raise ProductionError("--direction is only valid for template/premium sample groups")
    state["samples"]["active_direction"] = direction if grouped else None
    record = _sample_record(state, direction, page_id) if grouped else _page(state, page_id)
    if grouped:
        page_payload = _director_page(project, page_id)
        input_payload = {
            "schema_version": "1.0",
            "page": page_payload,
            "mode_semantic_hash": _mode_semantic_hash(project),
            "template_hash": _current_template_hash(project),
        }
        record["input_hash"] = _canonical_hash(input_payload)
    if state["stage"] == "repair_required" and record["state"] != "repair_required":
        raise ProductionError(f"page {page_id} is not marked for repair")
    if state["stage"] == "production":
        pending = [page["page_id"] for page in _pages(_plan(project)) if _page(state, page["page_id"])["state"] != "passed"]
        if pending and page_id != pending[0]:
            raise ProductionError(f"next planned page is {pending[0]}")
    current = project / CURRENT_FILE
    current.parent.mkdir(parents=True, exist_ok=True)
    source = _sample_paths(project, state, direction, page_id)[0] if grouped else _output_path(project, page_id)
    if record["state"] == "repair_required" and source.is_file():
        shutil.copy2(source, current)
    else:
        current.unlink(missing_ok=True)
    _invalidate_page(record, state="active", svg=True)
    state["active_page"] = page_id
    _save(project, state)
    runtime = Path(runtime_root).resolve(); router = Path(router_root).resolve()
    return {"stage": state["stage"], "page_id": page_id, "direction": direction, "work_file": str(current), "director_requirements": _director_page(project, page_id), "required_context": [str(path) for path in (
        router / "SKILL.md", runtime / "MASTER.md", project / "analysis" / "director_profile.md",
        project / "analysis" / "director_plan.json", project / "design_spec.md", project / "spec_lock.md",
        runtime / "references" / "ppt-director-runtime.md",
        runtime / "references" / "executor-base.md", runtime / "references" / "shared-standards.md",
    )], "next_allowed_actions": ["write .page_work/current.svg", "page-check"]}


def _iteration(project: Path, page_id: str) -> int:
    values = []
    for path in (project / ".preview").glob(f"{page_id}.iter*.png"):
        suffix = path.stem.rsplit("iter", 1)[-1]
        if suffix.isdigit(): values.append(int(suffix))
    return max(values, default=0) + 1


def check_page(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = state["active_page"]
    if not page_id:
        raise ProductionError("no active page", next_actions=["page-begin"])
    current = project / CURRENT_FILE
    if not current.is_file():
        raise ProductionError(".page_work/current.svg is missing")
    from svg_quality_checker import SVGQualityChecker
    result = SVGQualityChecker().check_file(str(current))
    if not result.get("passed"):
        _active_record(state, page_id)["blocking_issues"] = list(result.get("errors") or [])
        _save(project, state)
        raise ProductionError("SVG machine check failed", next_actions=["fix current.svg", "page-check"])
    from visual_review import render_svg_file
    iteration = _iteration(project, page_id)
    rendered = project / ".preview" / f"{page_id}.iter{iteration}.png"
    render = render_svg_file(current, rendered)
    if not render.get("ok") or render.get("all_background"):
        raise ProductionError("visual review renderer produced an invalid preview")
    _, canonical, _ = _active_paths(project, state, page_id)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rendered, canonical)
    record = _active_record(state, page_id)
    record.update({"state": "checked", "svg_hash": _sha256(current), "png_hash": _sha256(canonical), "machine_check_hash": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(), "review_report_hash": None, "reviewed_png_hash": None, "review_passed": False, "blocking_issues": []})
    _save(project, state)
    return {"page_id": page_id, "machine_check": result, "png": str(canonical), "png_hash": record["png_hash"], "next_allowed_actions": ["open PNG", "page-review"]}


def review_context(project_path: str | Path, runtime_root: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = state["active_page"]
    if not page_id or _active_record(state, page_id)["state"] != "checked":
        raise ProductionError("active page must be checked and rendered before review")
    _, preview, review = _active_paths(project, state, page_id)
    return {"page_id": page_id, "direction": state["samples"].get("active_direction"), "png": str(preview), "required_context": [str(Path(runtime_root) / "references" / "visual-review.md"), str(Path(runtime_root) / "workflows" / "visual-review.md")], "required_output": str(review), "next_allowed_actions": ["open PNG", "page-review --apply <report.json>"]}


def install_page_review(project_path: str | Path, candidate: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = state["active_page"]
    if not page_id:
        raise ProductionError("no active page")
    record, source = _active_record(state, page_id), Path(candidate).expanduser().resolve()
    if record["state"] != "checked" or not source.is_file():
        raise ProductionError("review requires the latest checked PNG and a report candidate")
    report = json.loads(source.read_text(encoding="utf-8"))
    passed = report.get("passed") is True or report.get("status") in {"ok", "fixed"}
    blocking = report.get("blocking_issues") or report.get("critical_issues") or []
    if report.get("page_id") not in {None, page_id} or not isinstance(blocking, list):
        raise ProductionError("invalid visual review report")
    current = project / CURRENT_FILE
    _, preview, destination = _active_paths(project, state, page_id)
    if report.get("final_svg_hash") not in {None, _sha256(current)} or report.get("final_png_hash") not in {None, _sha256(preview)}:
        raise ProductionError("visual review report is stale")
    installed = {
        "page_id": page_id, "mode": "controlled", "status": "ok" if passed and not blocking else "needs_human",
        "final_svg_hash": _sha256(current), "final_png_hash": _sha256(preview),
        "blocking_issues": blocking, "summary": str(report.get("summary") or ""),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(destination, installed)
    record.update({"state": "reviewed" if installed["status"] == "ok" else "checked", "review_report_hash": _sha256(destination), "reviewed_png_hash": installed["final_png_hash"], "review_passed": installed["status"] == "ok", "blocking_issues": blocking})
    _save(project, state)
    if not record["review_passed"]:
        raise ProductionError("visual review has blocking issues", next_actions=["fix current.svg", "page-check"])
    return {"page_id": page_id, "review": str(destination), "status": "passed", "next_allowed_actions": ["page-pass"]}


def _all_passed(state: dict[str, Any], ids: list[str]) -> bool:
    return all(_page(state, page_id)["state"] == "passed" for page_id in ids)


def _validate_grouped_samples(project: Path, state: dict[str, Any]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for direction in ("A", "B", "C"):
        rows = []
        for sample_id in state["samples"]["page_ids"]:
            record = _sample_record(state, direction, sample_id)
            svg, png, review = _sample_paths(project, state, direction, sample_id)
            hashes = {"svg_hash": _sha256(svg), "png_hash": _sha256(png), "review_hash": _sha256(review)}
            if record["state"] != "passed" or not record["review_passed"] or record["blocking_issues"]:
                raise ProductionError(f"sample direction is incomplete: {direction}/{sample_id}")
            if None in hashes.values() or hashes != {
                "svg_hash": record["svg_hash"],
                "png_hash": record["png_hash"],
                "review_hash": record["review_report_hash"],
            }:
                raise ProductionError(f"sample direction hashes are stale: {direction}/{sample_id}")
            rows.append(f"{sample_id}:{hashes['svg_hash']}:{hashes['png_hash']}")
        fingerprints[direction] = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    if len(set(fingerprints.values())) != 3:
        raise ProductionError("A/B/C sample directions contain duplicate artifacts")
    for sample_id in state["samples"]["page_ids"]:
        input_hashes = {_sample_record(state, direction, sample_id).get("input_hash") for direction in ("A", "B", "C")}
        if None in input_hashes or len(input_hashes) != 1:
            raise ProductionError(f"A/B/C sample content inputs differ: {sample_id}")
    return fingerprints


def _midpoint(plan: dict[str, Any]) -> int:
    return max(1, (len(_pages(plan)) + 1) // 2)


def pass_page(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = state["active_page"]
    if not page_id:
        raise ProductionError("no active page")
    record, current = _active_record(state, page_id), project / CURRENT_FILE
    output, preview, report = _active_paths(project, state, page_id)
    if record["state"] != "reviewed" or not record["review_passed"] or record["blocking_issues"]:
        raise ProductionError("current page has not passed visual review")
    if record["svg_hash"] != _sha256(current) or record["png_hash"] != _sha256(preview) or record["review_report_hash"] != _sha256(report) or record["reviewed_png_hash"] != record["png_hash"]:
        raise ProductionError("current SVG, PNG, or review changed after checking")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, output)
    record.update({"state": "passed", "svg_hash": _sha256(output), "notes_hash": _sha256(_notes_path(project, page_id))})
    state["active_page"] = None
    direction = state["samples"].get("active_direction")
    state["samples"]["active_direction"] = None
    plan = _plan(project)
    if state["stage"] == "sample_production":
        if state["samples"].get("strategy") == "three_groups":
            complete = all(
                _sample_record(state, sample_direction, sample_id)["state"] == "passed"
                for sample_direction in ("A", "B", "C") for sample_id in state["samples"]["page_ids"]
            )
        else:
            complete = _all_passed(state, state["samples"]["page_ids"])
        if complete:
            if state["samples"].get("strategy") == "three_groups":
                _validate_grouped_samples(project, state)
            state["stage"] = "sample_confirmation"
            state["samples"]["status"] = "awaiting_user"
    elif state["stage"] in {"production", "repair_required"}:
        ordered = [page["page_id"] for page in _pages(plan)]
        passed_count = sum(_page(state, pid)["state"] == "passed" for pid in ordered)
        if state["midpoint_review"]["status"] != "passed" and passed_count >= _midpoint(plan):
            state["stage"] = "midpoint_required"
        elif _all_passed(state, ordered):
            state["stage"] = "deck_review_required"
        else:
            state["stage"] = "production"
    _save(project, state)
    return {"page_id": page_id, "direction": direction, "state": "passed", "stage": state["stage"], "next_allowed_actions": _next_actions(state)}


def sample_confirm(project_path: str | Path, decision: str, *, page_id: str | None = None, replacements: list[str] | None = None) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    if state["stage"] != "sample_confirmation":
        raise ProductionError("sample confirmation is only allowed after all three samples pass")
    decision = decision.upper()
    if state["samples"].get("strategy") == "three_groups":
        if decision not in {"A", "B", "C"}:
            raise ProductionError("direction must be A, B, or C")
        if page_id or replacements:
            raise ProductionError("template/premium sample selection does not accept --page-id or --pages")
        fingerprints = _validate_grouped_samples(project, state)
        selected_files: list[str] = []
        selected_pngs: list[str] = []
        selected_hashes: dict[str, Any] = {}
        for sample_id in state["samples"]["page_ids"]:
            source_svg, source_png, source_review = _sample_paths(project, state, decision, sample_id)
            target_svg, target_png, target_review = _output_path(project, sample_id), _preview_path(project, sample_id), _review_path(project, sample_id)
            for source, target in ((source_svg, target_svg), (source_png, target_png), (source_review, target_review)):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            record = _page(state, sample_id)
            sample_record = _sample_record(state, decision, sample_id)
            record.update(json.loads(json.dumps(sample_record)))
            record.update({"state": "passed", "svg_hash": _sha256(target_svg), "png_hash": _sha256(target_png), "review_report_hash": _sha256(target_review), "reviewed_png_hash": _sha256(target_png), "notes_hash": _sha256(_notes_path(project, sample_id))})
            selected_files.append(str(target_svg))
            selected_pngs.append(str(target_png))
            selected_hashes[sample_id] = _sample_snapshot(project, sample_id)
        selected = {
            "selected_direction": decision, "selected_files": selected_files,
            "selected_pngs": selected_pngs, "selected_hashes": selected_hashes,
            "selection_time": datetime.now(timezone.utc).isoformat(),
            "selected_by": "user_confirmation", "template_profile_hash": state["global_hashes"].get("design_spec_hash"),
            "master_handoff_hash": state["global_hashes"].get("master_handoff_hash"),
        }
        _atomic_json(project / ".director" / "selected_sample.json", selected)
        state["samples"].update({"status": "approved", "selected_direction": decision, "approved_hashes": selected_hashes})
        state["global_hashes"] = _current_globals(project)
        state["stage"] = "production"
        _save(project, state)
        return {"decision": decision, "stage": state["stage"], "selected_sample": str(project / ".director" / "selected_sample.json"), "samples": state["samples"], "next_allowed_actions": _next_actions(state)}
    if decision == "A":
        snapshots = {pid: _sample_snapshot(project, pid) for pid in state["samples"]["page_ids"]}
        if any(None in snapshot.values() for snapshot in snapshots.values()):
            raise ProductionError("sample files are incomplete")
        for sample_id, snapshot in snapshots.items():
            record = _page(state, sample_id)
            if record["state"] != "passed" or snapshot != {
                "svg_hash": record["svg_hash"], "png_hash": record["png_hash"],
                "review_hash": record["review_report_hash"],
            }:
                raise ProductionError(f"sample state or hash is stale: {sample_id}")
        state["samples"].update({"status": "approved", "approved_hashes": snapshots})
        state["stage"] = "production"
    elif decision == "B":
        if not page_id or page_id not in state["samples"]["page_ids"]:
            raise ProductionError("decision B requires exactly one current sample page_id")
        _invalidate_page(_page(state, page_id), svg=False)
        state["samples"].update({"status": "pending", "approved_hashes": {}})
        state["stage"] = "sample_production"
    elif decision == "C":
        from director_plan import replace_sample_pages
        updated = replace_sample_pages(project, replacements or [])
        for record in state["pages"].values():
            _invalidate_page(record, state="pending", svg=True, notes=True)
        state["samples"] = {"page_ids": _sample_ids(updated), "status": "pending", "approved_hashes": {}}
        state["global_hashes"] = _current_globals(project)
        state["global_hashes"]["spec_lock_hash"] = None
        _clear_reviews(state)
        state["stage"] = "design_pending"
    else:
        raise ProductionError("decision must be A, B, or C")
    _save(project, state)
    return {"decision": decision, "stage": state["stage"], "samples": state["samples"], "next_allowed_actions": _next_actions(state)}


def sample_reject(project_path: str | Path, reason: str) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    if state["stage"] != "sample_confirmation":
        raise ProductionError("samples can only be rejected in sample_confirmation")
    if not reason.strip():
        raise ProductionError("sample rejection requires user feedback")
    feedback = project / ".director" / "sample_feedback.md"
    feedback.parent.mkdir(parents=True, exist_ok=True)
    round_number = int(state["samples"].get("round", 1))
    with feedback.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\n## Rejected round {round_number}\n\n- reason: {reason.strip()}\n")
        for direction in ("A", "B", "C") if state["samples"].get("strategy") == "three_groups" else ("single",):
            stream.write(f"- direction: {direction}\n")
    if state["samples"].get("strategy") == "three_groups":
        page_ids = list(state["samples"]["page_ids"])
        state["samples"] = _sample_state(project, page_ids)
        state["samples"]["round"] = round_number + 1
    else:
        for sample_id in state["samples"]["page_ids"]:
            _invalidate_page(_page(state, sample_id), state="pending", svg=False)
        state["samples"].update({"status": "pending", "approved_hashes": {}})
    (project / ".director" / "selected_sample.json").unlink(missing_ok=True)
    _clear_reviews(state)
    state["global_hashes"] = _current_globals(project)
    state["stage"] = "sample_production"
    _save(project, state)
    return {"stage": state["stage"], "round": state["samples"].get("round", 1), "feedback": str(feedback), "next_allowed_actions": ["page-begin"]}


def _review_expected(project: Path, state: dict[str, Any], kind: str) -> list[str]:
    ordered = [page["page_id"] for page in _pages(_plan(project))]
    if kind == "deck":
        return ordered
    passed = [page_id for page_id in ordered if _page(state, page_id)["state"] == "passed"]
    return list(dict.fromkeys([*state["samples"]["page_ids"], *passed[-2:]]))


def record_review(project_path: str | Path, kind: str, review_status: str, *, reviewed_pages: list[str]) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    required_stage = "midpoint_required" if kind == "midpoint" else "deck_review_required"
    if state["stage"] != required_stage:
        raise ProductionError(f"{kind} review is blocked in {state['stage']}")
    expected = _review_expected(project, state, kind)
    if not set(expected).issubset(set(reviewed_pages)):
        raise ProductionError(f"review must include: {', '.join(expected)}")
    gate = state["midpoint_review"] if kind == "midpoint" else state["deck_review"]
    gate.update({"status": review_status, "reviewed_pages": reviewed_pages})
    if review_status == "failed":
        state["stage"] = "repair_required"
    elif kind == "midpoint":
        state["stage"] = "production"
    else:
        from fact_guard import scan_deck_facts
        issues = scan_deck_facts(project)
        gate["blocking_issues"] = issues
        state["stage"] = "repair_required" if issues else "export_ready"
    _save(project, state)
    if state["stage"] == "repair_required":
        raise ProductionError(f"{kind} review failed", next_actions=["status", "page-begin <repair_page>"])
    return {"kind": kind, "status": "passed", "stage": state["stage"], "next_allowed_actions": _next_actions(state)}


def can_export(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    changes = reconcile(project, state); state = _load(project)
    if changes or state["stage"] != "export_ready":
        raise ProductionError("export is not ready", next_actions=_next_actions(state))
    ordered = [page["page_id"] for page in _pages(_plan(project))]
    if not _all_passed(state, ordered) or state["deck_review"]["status"] != "passed":
        raise ProductionError("all pages and deck review must pass before export")
    for page_id in ordered:
        record = _page(state, page_id)
        expected = _sample_snapshot(project, page_id)
        if (
            expected["svg_hash"] is None or expected["png_hash"] is None or expected["review_hash"] is None
            or record["svg_hash"] != expected["svg_hash"]
            or record["png_hash"] != expected["png_hash"]
            or record["review_report_hash"] != expected["review_hash"]
            or record["reviewed_png_hash"] != expected["png_hash"]
            or not record["review_passed"] or record["blocking_issues"]
            or record["notes_hash"] != _sha256(_notes_path(project, page_id))
        ):
            raise ProductionError(f"page integrity check failed: {page_id}", next_actions=["status"])
    from fact_guard import scan_deck_facts
    issues = scan_deck_facts(project)
    if issues:
        state["deck_review"]["blocking_issues"] = issues
        state["stage"] = "repair_required"
        _save(project, state)
        raise ProductionError("fact gate failed before export", next_actions=["status"])
    return {"allowed": True, "input_hashes": {pid: _sample_snapshot(project, pid) for pid in ordered}}


def export_deck(project_path: str | Path, output: str | None = None) -> dict[str, Any]:
    project = _project(project_path)
    preflight = can_export(project)
    from svg_to_pptx.pptx_package.cli import main as export_main
    target = Path(output).expanduser().resolve() if output else project / "exports" / f"{project.name}.pptx"
    with redirect_stdout(io.StringIO()):
        code = export_main([str(project), "--output", str(target)])
    if code:
        raise ProductionError(f"PPT Master export failed with exit code {code}")
    state = _load(project)
    state["export"] = {"path": str(target), "pptx_hash": _sha256(target), "input_hashes": preflight["input_hashes"]}
    state["stage"] = "exported"
    _save(project, state)
    return {"stage": "exported", "pptx": str(target), "pptx_hash": state["export"]["pptx_hash"], "next_allowed_actions": ["status"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(status(args.project), ensure_ascii=False, indent=2))
        return 0
    except ProductionError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
