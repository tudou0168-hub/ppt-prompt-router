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


def _confirmations() -> dict[str, Any]:
    return {
        "materials": "pending",
        "mode": "pending",
        "director": "pending",
        "style": "pending",
        "pilot": "pending",
        "premium_page": "pending",
    }


def _awaiting_confirmation(
    kind: str,
    next_command: str,
    *,
    next_action: str,
    **values: Any,
) -> dict[str, Any]:
    return {
        "status": "AWAITING_USER_CONFIRMATION",
        "confirmation_kind": kind,
        "next_action": next_action,
        "next_command": next_command,
        **values,
    }


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
    values = {key: _global_hash(project, key, path) for key, path in _global_files(project).items()}
    values["source_content_hash"] = _canonical_hash(_current_source_hashes(project))
    values["template_content_hash"] = _current_template_hash(project)
    return values


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
        "samples": {
            "page_ids": [], "status": "pending", "approved_hashes": {},
            "phase": "materials", "confirmations": _confirmations(),
        },
        "pages": {}, "midpoint_review": {"status": "pending", "reviewed_pages": []},
        "deck_review": {"status": "pending", "reviewed_pages": [], "blocking_issues": []},
        "export": {"path": None, "pptx_hash": None, "input_hashes": {}},
    }
    _save(project, state)
    return state


def _generation_mode(project: Path) -> dict[str, Any]:
    path = project / ".director" / "generation_mode.json"
    if not path.is_file():
        return {"mode": "standard", "sample_strategy": "pilot"}
    return json.loads(path.read_text(encoding="utf-8"))


def confirm_materials(project_path: str | Path, decision: str) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    value = decision.strip().lower()
    if value not in {"approve", "adjust"}:
        raise ProductionError("materials decision must be approve or adjust")
    if state["pages"] or state["stage"] != "director_pending":
        raise ProductionError("materials can only be confirmed before planning")
    state["samples"].setdefault("confirmations", _confirmations())["materials"] = (
        "approved" if value == "approve" else "adjust_requested"
    )
    state["samples"]["phase"] = "mode" if value == "approve" else "materials"
    _save(project, state)
    return {
        "decision": value,
        "stage": state["stage"],
        "confirmations": state["samples"]["confirmations"],
        "next_action": "select generation mode" if value == "approve" else "restart with corrected input roles",
        "next_command": "mode-propose <project>" if value == "approve" else "start --source ... --reference ... --template ...",
    }


def confirm_mode(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    confirmations = state["samples"].setdefault("confirmations", _confirmations())
    if confirmations.get("materials") != "approved":
        raise ProductionError("materials confirmation is required before mode selection")
    confirmations["mode"] = "approved"
    if state["samples"].get("phase") == "template_analysis" and confirmations.get("director") == "approved" and state["pages"]:
        state["samples"]["phase"] = "style"
        state["stage"] = "sample_production"
    else:
        state["samples"]["phase"] = "director"
    state["global_hashes"] = _current_globals(project)
    _save(project, state)
    return {"stage": state["stage"], "confirmations": confirmations, "next_allowed_actions": ["plan"]}


def _sample_state(project: Path, plan: dict[str, Any], confirmations: dict[str, Any] | None = None) -> dict[str, Any]:
    mode = _generation_mode(project)
    page_ids = _sample_ids(plan)
    values = json.loads(json.dumps(confirmations or _confirmations()))
    values["materials"] = "approved"
    values["mode"] = "approved"
    values["director"] = "approved"
    strategy = "style_then_pilot" if mode.get("mode") in {"template", "premium"} else "pilot"
    style = plan.get("style_sample") if isinstance(plan.get("style_sample"), dict) else None
    style_id = str(style.get("page_id")) if style else None
    return {
        "page_ids": page_ids,
        "status": "pending",
        "approved_hashes": {},
        "strategy": strategy,
        "phase": "style" if strategy == "style_then_pilot" else "pilot",
        "round": 1,
        "active_candidate": None,
        "style_page_id": style_id,
        "candidates": {
            "style": {style_id: _page_record()} if style_id else {},
            "pilot": {page_id: _page_record() for page_id in page_ids},
        },
        "confirmations": values,
    }


def attach_director_plan(project_path: str | Path) -> dict[str, Any]:
    project = _project(project_path)
    state, plan = _load(project), _plan(project)
    if state["stage"] != "director_pending" or state["pages"]:
        raise ProductionError("director plan can only be attached once in director_pending")
    confirmations = state["samples"].setdefault("confirmations", _confirmations())
    contract = _load_json(project / "analysis" / "director_contract.json") or {}
    legacy = str(contract.get("schema_version") or "3.0") != "3.1"
    if legacy:
        confirmations.update({"materials": "approved", "mode": "approved", "director": "approved"})
    if confirmations.get("mode") != "approved" or confirmations.get("director") != "approved":
        raise ProductionError("director confirmation is required before attaching the plan")
    state["pages"] = {page["page_id"]: _page_record() for page in _pages(plan)}
    state["samples"] = _sample_state(project, plan, confirmations)
    state["global_hashes"] = _current_globals(project)
    state["stage"] = "sample_production" if state["samples"]["phase"] == "style" else "design_pending"
    _save(project, state)
    return state


def confirm_director(project_path: str | Path, decision: str) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    value = decision.strip().lower()
    if value not in {"approve", "adjust", "restart"}:
        raise ProductionError("director decision must be approve, adjust, or restart")
    if state["stage"] != "director_pending" or state["pages"]:
        raise ProductionError("director confirmation is only allowed before page design")
    confirmations = state["samples"].setdefault("confirmations", _confirmations())
    if confirmations.get("mode") != "approved":
        raise ProductionError("mode confirmation is required before director confirmation")
    if not (project / "analysis" / "director_plan.json").is_file():
        raise ProductionError("director plan must exist before director confirmation")
    confirmations["director"] = "approved" if value == "approve" else f"{value}_requested"
    _save(project, state)
    if value != "approve":
        return {
            "decision": value, "stage": state["stage"], "confirmations": confirmations,
            "next_allowed_actions": ["plan --apply <revised-candidate.json>"],
        }
    attached = attach_director_plan(project)
    return {
        "decision": value, "stage": attached["stage"], "samples": attached["samples"],
        "next_allowed_actions": _next_actions(attached),
    }


def register_director_plan(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    if state["stage"] != "director_pending" or state["pages"]:
        raise ProductionError("director plan can only be registered before page design")
    confirmations = state["samples"].setdefault("confirmations", _confirmations())
    if confirmations.get("mode") != "approved":
        raise ProductionError("mode confirmation is required before planning")
    confirmations["director"] = "pending"
    state["samples"]["phase"] = "director"
    state["global_hashes"] = _current_globals(project)
    _save(project, state)
    return _awaiting_confirmation(
        "director",
        f"confirm {project} director approve",
        next_action="review and confirm the content director plan",
        stage=state["stage"],
        samples=state["samples"],
    )


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
    confirmations = state["samples"].setdefault("confirmations", _confirmations())
    if _generation_mode(project).get("mode") in {"template", "premium"} and confirmations.get("style") != "approved":
        raise ProductionError("style sample confirmation is required before lock-spec")
    state["global_hashes"] = _current_globals(project)
    state["samples"]["phase"] = "pilot"
    state["samples"]["status"] = "pending"
    state["stage"] = "sample_production"
    _save(project, state)
    return {"stage": state["stage"], "sample_pages": state["samples"]["page_ids"], "samples": state["samples"], "next_allowed_actions": ["page-begin <pilot_page_id>"]}


def _sample_snapshot(project: Path, page_id: str) -> dict[str, str | None]:
    return {"svg_hash": _sha256(_output_path(project, page_id)), "png_hash": _sha256(_preview_path(project, page_id)), "review_hash": _sha256(_review_path(project, page_id))}


def _candidate_snapshot(project: Path, state: dict[str, Any], kind: str, page_id: str) -> dict[str, str | None]:
    svg, png, review = _candidate_paths(project, state, kind, page_id)
    return {"svg_hash": _sha256(svg), "png_hash": _sha256(png), "review_hash": _sha256(review)}


def _sample_root(project: Path, state: dict[str, Any], kind: str) -> Path:
    return project / ".director" / "samples" / f"round-{int(state['samples'].get('round', 1)):03d}" / kind


def _candidate_paths(project: Path, state: dict[str, Any], kind: str, page_id: str) -> tuple[Path, Path, Path]:
    if kind not in {"style", "pilot"}:
        raise ProductionError(f"unknown sample kind: {kind}")
    root = _sample_root(project, state, kind)
    return root / "svg" / f"{page_id}.svg", root / "preview" / f"{page_id}.png", root / "review" / f"{page_id}.json"


def _candidate_record(state: dict[str, Any], kind: str, page_id: str) -> dict[str, Any]:
    try:
        return state["samples"]["candidates"][kind][page_id]
    except KeyError as exc:
        raise ProductionError(f"unknown sample candidate: {kind}/{page_id}") from exc


def _sample_paths(project: Path, state: dict[str, Any], direction: str, page_id: str) -> tuple[Path, Path, Path]:
    """Read-only path compatibility for old A/B/C project state."""
    if direction in {"style", "pilot"}:
        return _candidate_paths(project, state, direction, page_id)
    if direction not in {"A", "B", "C"} or "directions" not in state.get("samples", {}):
        raise ProductionError(f"unknown legacy sample direction: {direction}")
    root = project / ".director" / "samples" / f"round-{int(state['samples'].get('round', 1)):03d}" / direction
    return root / "svg" / f"{page_id}.svg", root / "preview" / f"{page_id}.png", root / "review" / f"{page_id}.json"


def _active_candidate(state: dict[str, Any]) -> dict[str, str] | None:
    value = state.get("samples", {}).get("active_candidate")
    if not isinstance(value, dict) or value.get("sample_type") not in {"style", "pilot"} or not value.get("page_id"):
        return None
    return {"sample_type": str(value["sample_type"]), "page_id": str(value["page_id"])}


def _active_page_id(state: dict[str, Any]) -> str | None:
    candidate = _active_candidate(state)
    return candidate["page_id"] if candidate else state.get("active_page")


def _active_record(state: dict[str, Any], page_id: str) -> dict[str, Any]:
    candidate = _active_candidate(state)
    return _candidate_record(state, candidate["sample_type"], page_id) if candidate else _page(state, page_id)


def _active_paths(project: Path, state: dict[str, Any], page_id: str) -> tuple[Path, Path, Path]:
    candidate = _active_candidate(state)
    if candidate:
        return _candidate_paths(project, state, candidate["sample_type"], page_id)
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
        previous_samples = state.get("samples") or {}
        confirmations = previous_samples.get("confirmations") or _confirmations()
        source_changed = bool(set(changed_globals).intersection({
            "source_content_hash", "director_contract_hash", "director_profile_hash",
        }))
        template_changed = "template_content_hash" in changed_globals and not source_changed
        director_changed = "director_plan_hash" in changed_globals and not source_changed
        spec_changed = bool(set(changed_globals).intersection({
            "design_spec_hash", "spec_lock_hash", "selected_sample_hash",
        })) and not (source_changed or template_changed or director_changed)
        if source_changed or director_changed:
            confirmations["director"] = "restart_requested"
            confirmations["style"] = "pending"
            confirmations["pilot"] = "pending"
            confirmations["premium_page"] = "pending"
            state["pages"] = {}
            state["samples"] = {
                "page_ids": [], "status": "pending", "approved_hashes": {},
                "phase": "director", "active_candidate": None, "confirmations": confirmations,
            }
            state["active_page"] = None
            state["stage"] = "director_pending"
        elif template_changed and current_globals.get("director_plan_hash"):
            confirmations["style"] = "pending"
            confirmations["pilot"] = "pending"
            confirmations["premium_page"] = "pending"
            state["pages"] = {page["page_id"]: _page_record() for page in _pages(_plan(project))}
            state["samples"] = _sample_state(project, _plan(project), confirmations)
            state["samples"]["round"] = int(previous_samples.get("round", 0)) + 1
            state["samples"]["phase"] = "template_analysis"
            state["active_page"] = None
            state["stage"] = "sample_production"
        elif spec_changed and current_globals.get("director_plan_hash"):
            for record in state["pages"].values():
                _invalidate_page(record, state="repair_required", svg=True, notes=True)
            state["samples"] = _sample_state(project, _plan(project), confirmations)
            state["samples"]["round"] = int(previous_samples.get("round", 0)) + 1
            state["samples"]["phase"] = "pilot"
            confirmations = state["samples"]["confirmations"]
            confirmations["pilot"] = "pending"
            confirmations["premium_page"] = "pending"
            state["active_page"] = None
            state["stage"] = "design_pending"
        else:
            for record in state["pages"].values():
                _invalidate_page(record, state="repair_required", svg=True, notes=True)
            state["active_page"] = None
            state["samples"]["active_candidate"] = None
            state["stage"] = "repair_required"
        _clear_reviews(state)
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
    pilot_approved = (state["samples"].get("confirmations") or {}).get("pilot") == "approved"
    if pilot_approved and approved and state["samples"].get("candidates") and any(
        approved.get(page_id) != _candidate_snapshot(project, state, "pilot", page_id)
        for page_id in state["samples"]["page_ids"]
    ):
        state["samples"]["approved_hashes"] = {}
        state["samples"]["status"] = "pending"
        state["samples"].setdefault("confirmations", _confirmations())["pilot"] = "pending"
        state["samples"]["phase"] = "pilot"
        state["stage"] = "sample_production"
        changes.append("sample_approval")
    if state["stage"] == "production" and state["midpoint_review"]["status"] == "passed":
        ordered = [page["page_id"] for page in _pages(_plan(project))]
        if ordered and _all_passed(state, ordered):
            state["stage"] = "deck_review_required"
            changes.append("deck_review_required")
    if changes:
        _clear_reviews(state)
        if was_exported and not changed_globals:
            state["stage"] = "repair_required"
        _save(project, state)
    return changes


def _next_actions(state: dict[str, Any]) -> list[str]:
    stage = state["stage"]
    confirmations = state.get("samples", {}).get("confirmations") or {}
    if stage == "director_pending":
        if confirmations.get("materials") != "approved":
            return ["confirm materials approve"]
        if confirmations.get("mode") != "approved":
            return ["mode-propose", "mode-select"]
        return ["plan", "confirm director approve"]
    if stage == "sample_confirmation":
        return [
            "sample-confirm approve|adjust|redo"
            if state["samples"].get("phase") == "style"
            else "sample-confirm approve|adjust|restart"
        ]
    if stage == "sample_production" and state["samples"].get("phase") == "template_analysis":
        return ["mode-select --mode template|premium"]
    return {
        "design_pending": ["lock-spec"],
        "sample_production": ["page-begin"],
        "production": ["page-begin"], "midpoint_required": ["review midpoint"],
        "deck_review_required": ["review deck"], "export_ready": ["export"],
        "exported": ["status"], "repair_required": ["page-begin <repair_page>", "status"],
    }[stage]


def status(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    changes = reconcile(project, state)
    state = _load(project)
    result = {"stage": state["stage"], "active_page": state["active_page"], "active_candidate": state["samples"].get("active_candidate"), "changes": changes, "samples": state["samples"], "pages": state["pages"], "next_allowed_actions": _next_actions(state)}
    confirmations = state["samples"].get("confirmations") or {}
    if state["stage"] == "director_pending" and confirmations.get("materials") != "approved":
        result.update(_awaiting_confirmation(
            "materials",
            f"confirm {project} materials approve",
            next_action="review and confirm material roles",
        ))
    elif state["stage"] == "director_pending" and state["samples"].get("phase") == "director" and confirmations.get("director") == "pending":
        result.update(_awaiting_confirmation(
            "director",
            f"confirm {project} director approve",
            next_action="review and confirm the content director plan",
        ))
    elif state["stage"] == "sample_confirmation":
        kind = "style" if state["samples"].get("phase") == "style" else "pilot"
        result.update(_awaiting_confirmation(
            kind,
            f"sample-confirm {project} approve",
            next_action=f"review and confirm the {kind} candidates",
        ))
    elif state.get("active_page") and _page(state, state["active_page"]).get("state") == "awaiting_user":
        result.update(_awaiting_confirmation(
            "premium_page",
            f"confirm {project} premium-page approve",
            next_action="review and confirm the current premium page before sealing",
        ))
    return result


def _director_page(project: Path, page_id: str) -> dict[str, Any]:
    page = next((item for item in _pages(_plan(project)) if item["page_id"] == page_id), None)
    if page is None:
        raise ProductionError(f"page is not in director plan: {page_id}")
    return page


def begin_page(project_path: str | Path, page_id: str, router_root: str | Path, runtime_root: str | Path, *, direction: str | None = None) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    active = _active_page_id(state)
    if active:
        raise ProductionError(f"active page or candidate must finish first: {active}")
    if state["stage"] == "director_pending":
        raise ProductionError("director confirmation is required before page design", next_actions=_next_actions(state))
    allowed = state["stage"] in {"sample_production", "production", "repair_required"}
    if not allowed:
        raise ProductionError(f"page production is blocked in {state['stage']}", next_actions=_next_actions(state))
    if direction:
        raise ProductionError("A/B/C sample directions are disabled; produce the selected page once")
    candidate_kind = None
    if state["stage"] == "sample_production":
        phase = state["samples"].get("phase")
        if phase == "template_analysis":
            raise ProductionError("template analysis must be refreshed with mode-select before candidate production")
        candidate_kind = "style" if phase == "style" else "pilot"
        allowed_ids = [state["samples"].get("style_page_id")] if candidate_kind == "style" else state["samples"]["page_ids"]
        if page_id not in allowed_ids:
            raise ProductionError("only the selected style or pilot pages may be produced before confirmation")
    record = _candidate_record(state, candidate_kind, page_id) if candidate_kind else _page(state, page_id)
    if candidate_kind:
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
    source = _candidate_paths(project, state, candidate_kind, page_id)[0] if candidate_kind else _output_path(project, page_id)
    if record["state"] == "repair_required" and source.is_file():
        shutil.copy2(source, current)
    else:
        current.unlink(missing_ok=True)
    _invalidate_page(record, state="active", svg=True)
    if candidate_kind:
        state["samples"]["active_candidate"] = {"sample_type": candidate_kind, "page_id": page_id}
        state["active_page"] = None
    else:
        state["active_page"] = page_id
        state["samples"]["active_candidate"] = None
    _save(project, state)
    runtime = Path(runtime_root).resolve()
    return {"stage": state["stage"], "page_id": page_id, "candidate_kind": candidate_kind, "work_file": str(current), "director_requirements": _director_page(project, page_id), "required_context": [str(path) for path in (
        project / ".director" / "master_handoff.md",
        project / ".director" / "context_rehydrate.md",
        runtime / "references" / "executor-base.md",
    )], "next_allowed_actions": ["write .page_work/current.svg", "page-check"]}


def _iteration(preview: Path) -> int:
    values = []
    for path in preview.parent.glob(f"{preview.stem}.iter*{preview.suffix}"):
        suffix = path.stem.rsplit("iter", 1)[-1]
        if suffix.isdigit(): values.append(int(suffix))
    return max(values, default=0) + 1


def check_page(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = _active_page_id(state)
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
    _, canonical, _ = _active_paths(project, state, page_id)
    iteration = _iteration(canonical)
    rendered = canonical.parent / f"{canonical.stem}.iter{iteration}{canonical.suffix}"
    rendered.parent.mkdir(parents=True, exist_ok=True)
    render = render_svg_file(current, rendered)
    if not render.get("ok") or render.get("all_background"):
        raise ProductionError("visual review renderer produced an invalid preview")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rendered, canonical)
    record = _active_record(state, page_id)
    record.update({"state": "checked", "svg_hash": _sha256(current), "png_hash": _sha256(canonical), "machine_check_hash": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(), "review_report_hash": None, "reviewed_png_hash": None, "review_passed": False, "blocking_issues": []})
    _save(project, state)
    return {"page_id": page_id, "machine_check": result, "png": str(canonical), "png_hash": record["png_hash"], "next_allowed_actions": ["open PNG", "page-review"]}


def review_context(project_path: str | Path, runtime_root: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = _active_page_id(state)
    if not page_id or _active_record(state, page_id)["state"] != "checked":
        raise ProductionError("active page must be checked and rendered before review")
    _, preview, review = _active_paths(project, state, page_id)
    candidate = _active_candidate(state)
    return {"page_id": page_id, "candidate_kind": candidate["sample_type"] if candidate else None, "png": str(preview), "required_context": [str(path) for path in (
        project / ".director" / "master_handoff.md",
        project / ".director" / "context_rehydrate.md",
        Path(runtime_root) / "workflows" / "visual-review.md",
    )], "required_output": str(review), "next_allowed_actions": ["open PNG", "page-review --apply <report.json>"]}


def install_page_review(project_path: str | Path, candidate: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    page_id = _active_page_id(state)
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
    if not record["review_passed"]:
        _save(project, state)
        raise ProductionError("visual review has blocking issues", next_actions=["fix current.svg", "page-check"])
    active_candidate = _active_candidate(state)
    if active_candidate:
        kind = active_candidate["sample_type"]
        output, _, _ = _candidate_paths(project, state, kind, page_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current, output)
        record.update({"state": "candidate_ready", "svg_hash": _sha256(output)})
        state["samples"]["active_candidate"] = None
        ids = [state["samples"]["style_page_id"]] if kind == "style" else state["samples"]["page_ids"]
        complete = all(_candidate_record(state, kind, candidate_id)["state"] == "candidate_ready" for candidate_id in ids)
        if complete:
            _validate_candidate_set(project, state, kind, ids)
            state["stage"] = "sample_confirmation"
            state["samples"]["status"] = "pending"
            confirmation_kind = "style" if kind == "style" else "pilot"
            state["samples"].setdefault("confirmations", _confirmations())[confirmation_kind] = "pending"
        _save(project, state)
        if complete:
            confirmation_kind = "style" if kind == "style" else "pilot"
            return _awaiting_confirmation(
                confirmation_kind,
                f"sample-confirm {project} approve",
                next_action=f"review and confirm the {confirmation_kind} candidates",
                page_id=page_id,
                stage=state["stage"],
                candidate_kind=kind,
                candidate_paths=[str(_candidate_paths(project, state, kind, candidate_id)[1]) for candidate_id in ids],
            )
        return {"page_id": page_id, "candidate_kind": kind, "state": "candidate_ready", "stage": state["stage"], "next_allowed_actions": ["page-begin <next_candidate_page_id>"]}
    _save(project, state)
    return {"page_id": page_id, "review": str(destination), "status": "passed", "next_allowed_actions": ["page-pass"]}


def _all_passed(state: dict[str, Any], ids: list[str]) -> bool:
    return all(_page(state, page_id)["state"] == "passed" for page_id in ids)


def _validate_candidate_set(project: Path, state: dict[str, Any], kind: str, page_ids: list[str]) -> dict[str, dict[str, str | None]]:
    snapshots: dict[str, dict[str, str | None]] = {}
    for page_id in page_ids:
        record = _candidate_record(state, kind, page_id)
        snapshot = _candidate_snapshot(project, state, kind, page_id)
        if record["state"] != "candidate_ready" or not record["review_passed"] or record["blocking_issues"]:
            raise ProductionError(f"candidate is incomplete: {kind}/{page_id}")
        if None in snapshot.values() or snapshot != {
            "svg_hash": record["svg_hash"],
            "png_hash": record["png_hash"],
            "review_hash": record["review_report_hash"],
        }:
            raise ProductionError(f"candidate hashes are stale: {kind}/{page_id}")
        snapshots[page_id] = snapshot
    return snapshots


def _midpoint(plan: dict[str, Any]) -> int:
    return max(1, (len(_pages(plan)) + 1) // 2)


def _advance_after_formal_page(project: Path, state: dict[str, Any], plan: dict[str, Any]) -> None:
    ordered = [page["page_id"] for page in _pages(plan)]
    passed_count = sum(_page(state, pid)["state"] == "passed" for pid in ordered)
    if state["midpoint_review"]["status"] != "passed" and passed_count >= _midpoint(plan):
        state["stage"] = "midpoint_required"
    elif _all_passed(state, ordered):
        state["stage"] = "deck_review_required"
    else:
        state["stage"] = "production"


def _seal_formal_page(project: Path, state: dict[str, Any], page_id: str) -> dict[str, Any]:
    record, current = _page(state, page_id), project / CURRENT_FILE
    output = _output_path(project, page_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, output)
    record.update({"state": "passed", "svg_hash": _sha256(output), "notes_hash": _sha256(_notes_path(project, page_id))})
    state["active_page"] = None
    state["samples"]["active_candidate"] = None
    _advance_after_formal_page(project, state, _plan(project))
    _save(project, state)
    return {"page_id": page_id, "state": "passed", "stage": state["stage"], "next_allowed_actions": _next_actions(state)}


def pass_page(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    if _active_candidate(state) or state["stage"] in {"sample_production", "sample_confirmation"}:
        raise ProductionError("candidate pages become ready after page-review and must never use formal page-pass")
    page_id = state["active_page"]
    if not page_id:
        raise ProductionError("no active page")
    record, current = _active_record(state, page_id), project / CURRENT_FILE
    output, preview, report = _active_paths(project, state, page_id)
    if record["state"] != "reviewed" or not record["review_passed"] or record["blocking_issues"]:
        raise ProductionError("current page has not passed visual review")
    if record["svg_hash"] != _sha256(current) or record["png_hash"] != _sha256(preview) or record["review_report_hash"] != _sha256(report) or record["reviewed_png_hash"] != record["png_hash"]:
        raise ProductionError("current SVG, PNG, or review changed after checking")
    if _generation_mode(project).get("mode") == "premium" and state["stage"] == "production":
        record["state"] = "awaiting_user"
        state["samples"].setdefault("confirmations", _confirmations())["premium_page"] = "pending"
        _save(project, state)
        return _awaiting_confirmation(
            "premium_page",
            f"confirm {project} premium-page approve",
            next_action="review and confirm the current premium page before sealing",
            page_id=page_id,
            state="awaiting_user",
            stage=state["stage"],
        )
    return _seal_formal_page(project, state, page_id)


def _append_sample_feedback(project: Path, phase: str, decision: str, reason: str | None) -> Path:
    feedback = project / ".director" / "sample_feedback.md"
    feedback.parent.mkdir(parents=True, exist_ok=True)
    with feedback.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\n## {phase} {decision}\n\n- feedback: {(reason or '用户要求重新处理').strip()}\n")
    return feedback


def sample_confirm(project_path: str | Path, decision: str, *, page_id: str | None = None, replacements: list[str] | None = None, reason: str | None = None) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    reconcile(project, state); state = _load(project)
    if state["stage"] != "sample_confirmation":
        raise ProductionError("sample confirmation is only allowed after the current candidate set passes")
    value = decision.strip().lower()
    phase = state["samples"].get("phase")
    allowed = {"approve", "adjust", "redo"} if phase == "style" else {"approve", "adjust", "restart"}
    if value not in allowed:
        raise ProductionError(f"{phase} decision must be one of: {', '.join(sorted(allowed))}")
    confirmations = state["samples"].setdefault("confirmations", _confirmations())
    kind = "style" if phase == "style" else "pilot"
    ids = [state["samples"].get("style_page_id")] if kind == "style" else list(state["samples"]["page_ids"])
    if value == "approve":
        snapshots = _validate_candidate_set(project, state, kind, ids)
        confirmations[kind] = "approved"
        state["samples"].update({"status": "approved", "approved_hashes": snapshots})
        selected_files = []
        for candidate_id in ids:
            selected_files.extend(str(path) for path in _candidate_paths(project, state, kind, candidate_id))
        _atomic_json(project / ".director" / "selected_sample.json", {
            "sample_type": kind,
            "page_ids": ids,
            "selected_files": selected_files,
            "selected_hashes": snapshots,
            "selected_by": "user_confirmation",
            "selection_time": datetime.now(timezone.utc).isoformat(),
        })
        if phase == "style":
            state["stage"] = "design_pending"
        else:
            state["stage"] = "production"
        state["global_hashes"] = _current_globals(project)
    elif value == "adjust":
        _append_sample_feedback(project, phase, value, reason)
        for candidate_id in ids:
            _invalidate_page(_candidate_record(state, kind, candidate_id), state="repair_required", svg=False)
        confirmations[kind] = "adjust_requested"
        state["samples"].update({"status": "pending", "approved_hashes": {}})
        state["stage"] = "sample_production"
    elif value == "redo":
        _append_sample_feedback(project, phase, value, reason)
        state["samples"]["round"] = int(state["samples"].get("round", 1)) + 1
        state["samples"]["candidates"]["style"] = {ids[0]: _page_record()}
        state["samples"]["candidates"]["pilot"] = {pid: _page_record() for pid in state["samples"]["page_ids"]}
        state["samples"]["active_candidate"] = None
        confirmations["style"] = "restart_requested"
        confirmations["pilot"] = "pending"
        state["samples"].update({"status": "pending", "approved_hashes": {}})
        state["global_hashes"]["design_spec_hash"] = None
        state["global_hashes"]["spec_lock_hash"] = None
        state["stage"] = "sample_production"
    else:  # pilot restart
        _append_sample_feedback(project, phase, value, reason)
        confirmations["director"] = "restart_requested"
        confirmations["style"] = "pending"
        confirmations["pilot"] = "restart_requested"
        state["pages"] = {}
        state["samples"] = {
            "page_ids": [], "status": "pending", "approved_hashes": {}, "phase": "director", "active_candidate": None,
            "confirmations": confirmations,
        }
        state["active_page"] = None
        state["global_hashes"]["director_plan_hash"] = None
        state["global_hashes"]["design_spec_hash"] = None
        state["global_hashes"]["spec_lock_hash"] = None
        _clear_reviews(state)
        state["stage"] = "director_pending"
    _save(project, state)
    next_actions = _next_actions(state)
    return {
        "decision": value,
        "stage": state["stage"],
        "samples": state["samples"],
        "next_action": next_actions[0] if next_actions else "status",
        "next_command": next_actions[0] if next_actions else f"status {project}",
        "next_allowed_actions": next_actions,
    }


def sample_reject(project_path: str | Path, reason: str) -> dict[str, Any]:
    if not reason.strip():
        raise ProductionError("sample rejection requires user feedback")
    return sample_confirm(project_path, "adjust", reason=reason)


def confirm_premium_page(project_path: str | Path, decision: str) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    if _generation_mode(project).get("mode") != "premium":
        raise ProductionError("premium page confirmation is only valid in premium mode")
    page_id = state.get("active_page")
    value = decision.strip().lower()
    if not page_id or _page(state, page_id).get("state") != "awaiting_user":
        raise ProductionError("no premium page is awaiting user confirmation")
    if value == "approve":
        state["samples"]["confirmations"]["premium_page"] = "approved"
        return _seal_formal_page(project, state, page_id)
    if value == "adjust":
        record = _page(state, page_id)
        _invalidate_page(record, state="active", svg=False)
        state["samples"]["confirmations"]["premium_page"] = "adjust_requested"
        _save(project, state)
        return {"page_id": page_id, "state": "active", "stage": state["stage"], "next_allowed_actions": ["fix current.svg", "page-check"]}
    raise ProductionError("premium page decision must be approve or adjust")


def _review_expected(project: Path, state: dict[str, Any], kind: str) -> list[str]:
    ordered = [page["page_id"] for page in _pages(_plan(project))]
    if kind == "deck":
        return ordered
    passed = [page_id for page_id in ordered if _page(state, page_id)["state"] == "passed"]
    return passed[-2:]


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


### PPT Director 4.0 phase-1 path.  The stable 3.1 helpers above remain available
### for audit only; new projects use this small formal-probe flow.

def _phase1_confirmations() -> dict[str, str]:
    return {"brief": "pending", "design": "pending", "page": "pending"}


def _phase1(project: Path, state: dict[str, Any]) -> bool:
    return bool((state.get("samples") or {}).get("phase1"))


def _phase1_record() -> dict[str, Any]:
    return _page_record()


def initialize_project(project_path: str | Path) -> dict[str, Any]:
    project = _project(project_path)
    if _state_path(project).exists():
        raise ProductionError("production state already exists")
    state = {
        "stage": "director_pending", "active_page": None,
        "global_hashes": {"deck_plan_hash": None, "page_semantic_hashes": {}, "template_profile_hash": None, "design_genome_hash": None, "spec_lock_hash": None},
        "samples": {"phase1": True, "page_ids": [], "status": "pending", "approved_hashes": {}, "confirmations": _phase1_confirmations(), "feedback": []},
        "pages": {}, "midpoint_review": {"status": "pending", "reviewed_pages": []},
        "deck_review": {"status": "pending", "reviewed_pages": [], "blocking_issues": []},
        "export": {"path": None, "pptx_hash": None, "input_hashes": {}},
    }
    _save(project, state)
    return state


def _phase1_hashes(project: Path) -> dict[str, Any]:
    from scripts.director_runtime import semantic_plan_hashes, sha256
    return {
        **semantic_plan_hashes(project),
        "template_profile_hash": sha256(project / "analysis" / "template_profile.json"),
        "design_genome_hash": sha256(project / "design_genome.json"),
        "spec_lock_hash": sha256(project / "spec_lock.md"),
    }


def _phase1_invalidate(record: dict[str, Any]) -> None:
    record.update(_phase1_record())


def _phase1_invalidate_all(state: dict[str, Any]) -> None:
    for record in state["pages"].values():
        _phase1_invalidate(record)
    state["active_page"] = None
    state["midpoint_review"] = {"status": "pending", "reviewed_pages": []}
    state["deck_review"] = {"status": "pending", "reviewed_pages": [], "blocking_issues": []}
    state["export"] = {"path": None, "pptx_hash": None, "input_hashes": {}}


def record_phase1_artifact(project_path: str | Path, artifact_kind: str) -> dict[str, Any]:
    """Refresh Phase-1 dependencies after a role-owned artifact is accepted."""
    project, state = _project(project_path), _load(_project(project_path))
    if not _phase1(project, state):
        raise ProductionError("phase-1 artifact registration requires a 4.0 project")
    changes = reconcile(project, state)
    state = _load(project)
    state["global_hashes"] = _phase1_hashes(project)
    _save(project, state)
    return {"artifact_kind": artifact_kind, "changes": changes, "global_hashes": state["global_hashes"]}


def reconcile(project_path: str | Path, state: dict[str, Any] | None = None) -> list[str]:
    project = _project(project_path)
    state = state or _load(project)
    if not _phase1(project, state):
        return []
    current, recorded = _phase1_hashes(project), state["global_hashes"]
    changes: list[str] = []
    if recorded.get("deck_plan_hash") and current["deck_plan_hash"] != recorded.get("deck_plan_hash"):
        _phase1_invalidate_all(state); state["samples"]["confirmations"]["brief"] = "pending"; state["samples"]["confirmations"]["design"] = "pending"; state["stage"] = "director_pending"; changes.append("deck_plan")
    else:
        previous_pages = recorded.get("page_semantic_hashes") or {}
        for page_id, digest in current["page_semantic_hashes"].items():
            if previous_pages.get(page_id) and previous_pages.get(page_id) != digest and page_id in state["pages"]:
                _phase1_invalidate(state["pages"][page_id]); state["deck_review"] = {"status": "pending", "reviewed_pages": [], "blocking_issues": []}; state["export"] = {"path": None, "pptx_hash": None, "input_hashes": {}}; changes.append(f"page:{page_id}")
        if recorded.get("template_profile_hash") and current["template_profile_hash"] != recorded.get("template_profile_hash"):
            _phase1_invalidate_all(state); state["samples"]["confirmations"]["design"] = "pending"; state["stage"] = "design_pending"; changes.append("template_profile")
        elif recorded.get("design_genome_hash") and current["design_genome_hash"] != recorded.get("design_genome_hash"):
            _phase1_invalidate_all(state); state["samples"]["confirmations"]["design"] = "pending"; state["stage"] = "design_pending"; changes.append("design_genome")
    state["global_hashes"] = current
    if changes:
        _save(project, state)
    return changes


def register_director_plan(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    if not _phase1(project, state):
        raise ProductionError("phase-1 Director Plan registration requires a phase-1 project")
    from director_plan import load_plan
    plan = load_plan(project)
    state["samples"]["page_ids"] = [item["page_id"] for item in plan["sample_pages"]]
    state["samples"]["confirmations"]["brief"] = "pending"
    state["global_hashes"] = _phase1_hashes(project)
    _save(project, state)
    return _awaiting_confirmation("brief", f"approve {project} --type brief --decision A", next_action="review and approve the Director Plan", stage=state["stage"])


def approve_phase1(project_path: str | Path, approval_type: str, decision: str, *, feedback: str | None = None, reset_scope: str | None = None, page_id: str | None = None, source: str = "cli_unverified", source_id: str | None = None) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    if not _phase1(project, state):
        raise ProductionError("phase-1 approval requires a 4.0 project")
    if source == "host_user_message":
        raise ProductionError("host_user_message approval must be injected by a trusted host adapter")
    if source != "cli_unverified":
        raise ProductionError("unsupported approval source")
    value = decision.upper()
    if approval_type == "brief":
        if value != "A" or state["stage"] != "director_pending":
            raise ProductionError("brief approval only accepts A while Director Plan is pending")
        from director_plan import load_plan
        plan = load_plan(project)
        state["pages"] = {page["page_id"]: _phase1_record() for page in plan["pages"]}
        state["samples"]["page_ids"] = [item["page_id"] for item in plan["sample_pages"]]
        state["samples"]["confirmations"]["brief"] = "approved"
        state["stage"] = "design_pending"
    elif approval_type == "design":
        if state["stage"] != "sample_confirmation":
            raise ProductionError("design approval requires three sealed probes")
        ids = state["samples"]["page_ids"]
        if value == "A":
            if not _all_passed(state, ids):
                raise ProductionError("all design probes must pass before approval")
            state["samples"]["confirmations"]["design"] = "approved"; state["samples"]["status"] = "approved"; state["stage"] = "production"
        elif value == "B":
            if not feedback:
                raise ProductionError("design B requires feedback")
            for item in ids: _phase1_invalidate(state["pages"][item])
            state["samples"]["feedback"].append({"decision": "B", "feedback": feedback}); state["samples"]["confirmations"]["design"] = "adjust_requested"; state["stage"] = "sample_production"
        elif value == "C":
            if reset_scope not in {"content", "template", "visual"}:
                raise ProductionError("design C requires reset_scope=content|template|visual")
            _phase1_invalidate_all(state); state["samples"]["feedback"].append({"decision": "C", "scope": reset_scope, "feedback": feedback or ""}); state["samples"]["confirmations"]["design"] = "restart_requested"
            if reset_scope == "content": state["samples"]["confirmations"]["brief"] = "pending"; state["stage"] = "director_pending"
            else: state["stage"] = "design_pending"
        else:
            raise ProductionError("design approval must be A, B, or C")
    elif approval_type == "page":
        active = state.get("active_page")
        if value != "A" or not active or (page_id and page_id != active):
            raise ProductionError("page approval only accepts A for the active page")
        record = state["pages"][active]
        if record["state"] != "reviewed" or not record["review_passed"]:
            raise ProductionError("page approval requires a passed current review")
        record["page_approval"] = {"svg_hash": record["svg_hash"], "png_hash": record["png_hash"], "review_hash": record["review_report_hash"], "source": source, "source_id": source_id}
        state["samples"]["confirmations"]["page"] = "approved"
    else:
        raise ProductionError("approval type must be brief, design, or page")
    state["global_hashes"] = _phase1_hashes(project)
    _save(project, state)
    return {"approval_type": approval_type, "decision": value, "stage": state["stage"], "artifact_hashes": state["global_hashes"], "source": source, "source_id": source_id, "feedback": feedback}


def lock_spec(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path))
    if not _phase1(project, state):
        raise ProductionError("phase-1 lock-spec requires phase-1 state")
    if state["stage"] != "design_pending" or state["samples"]["confirmations"].get("brief") != "approved":
        raise ProductionError("brief approval is required before compiling the design genome")
    from scripts.director_runtime import compile_design_spec
    compiled = compile_design_spec(project)
    state["global_hashes"] = _phase1_hashes(project)
    state["stage"] = "sample_production"
    _save(project, state)
    return {"stage": state["stage"], "sample_pages": state["samples"]["page_ids"], **compiled, "next_allowed_actions": ["page-begin <probe_page_id>"]}


def begin_page(project_path: str | Path, page_id: str, router_root: str | Path, runtime_root: str | Path, *, direction: str | None = None) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path)); reconcile(project, state); state = _load(project)
    if state.get("active_page"):
        raise ProductionError(f"active page must finish first: {state['active_page']}")
    if state["stage"] not in {"sample_production", "production", "repair_required"}:
        raise ProductionError(f"page production is blocked in {state['stage']}")
    if state["stage"] == "sample_production" and page_id not in state["samples"]["page_ids"]:
        raise ProductionError("only the three design probes may be produced before design approval")
    from director_plan import page_by_id, load_plan
    plan = load_plan(project)
    if page_id not in state["pages"]:
        raise ProductionError(f"page is not in Director Plan: {page_id}")
    if state["stage"] == "production":
        pending = [page["page_id"] for page in plan["pages"] if state["pages"][page["page_id"]]["state"] != "passed"]
        if pending and pending[0] != page_id:
            raise ProductionError(f"next planned page is {pending[0]}")
    current = project / CURRENT_FILE; current.parent.mkdir(parents=True, exist_ok=True)
    output = _output_path(project, page_id)
    if state["pages"][page_id]["state"] == "repair_required" and output.is_file(): shutil.copy2(output, current)
    else: current.unlink(missing_ok=True)
    _phase1_invalidate(state["pages"][page_id]); state["pages"][page_id]["state"] = "active"; state["active_page"] = page_id; _save(project, state)
    return {"stage": state["stage"], "page_id": page_id, "work_file": str(current), "director_requirements": page_by_id(plan, page_id), "next_allowed_actions": ["write .page_work/current.svg", "page-check"]}


def review_context(project_path: str | Path, runtime_root: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path)); page_id = state.get("active_page")
    if not page_id or state["pages"][page_id]["state"] != "checked": raise ProductionError("active page must be checked and rendered before review")
    return {"page_id": page_id, "png": str(_preview_path(project, page_id)), "required_output": str(_review_path(project, page_id)), "next_allowed_actions": ["page-review --apply <report.json>"]}


def install_page_review(project_path: str | Path, candidate: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path)); page_id = state.get("active_page")
    if not page_id or state["pages"][page_id]["state"] != "checked": raise ProductionError("review requires a checked active page")
    report = _load_json(Path(candidate).resolve())
    required = {"page_id", "review_run_id", "review_mode", "svg_hash", "png_hash", "verdict", "issues", "revision_direction"}
    if not report or set(report) != required or report["page_id"] != page_id or report["review_mode"] not in {"independent_agent", "controlled_same_session", "human"} or report["verdict"] not in {"PASS", "REVISE"} or not isinstance(report["issues"], list) or not isinstance(report["revision_direction"], list):
        raise ProductionError("invalid phase-1 visual review schema")
    current, preview = project / CURRENT_FILE, _preview_path(project, page_id)
    if report["svg_hash"] != _sha256(current) or report["png_hash"] != _sha256(preview): raise ProductionError("visual review report is stale")
    destination = _review_path(project, page_id); _atomic_json(destination, report)
    record = state["pages"][page_id]; passed = report["verdict"] == "PASS" and not report["issues"]
    record.update({"state": "reviewed" if passed else "checked", "review_report_hash": _sha256(destination), "reviewed_png_hash": report["png_hash"], "review_passed": passed, "blocking_issues": report["issues"]})
    _save(project, state)
    if not passed: raise ProductionError("visual review requires revision", next_actions=["fix current.svg", "page-check"])
    return {"page_id": page_id, "review": str(destination), "status": "passed", "next_allowed_actions": ["page-pass"]}


def pass_page(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path)); page_id = state.get("active_page")
    if not page_id: raise ProductionError("no active page")
    record, current, preview, report = state["pages"][page_id], project / CURRENT_FILE, _preview_path(project, page_id), _review_path(project, page_id)
    if record["state"] != "reviewed" or not record["review_passed"] or record["svg_hash"] != _sha256(current) or record["png_hash"] != _sha256(preview) or record["review_report_hash"] != _sha256(report): raise ProductionError("current page has not passed the bound review")
    if _generation_mode(project).get("mode") == "premium" and state["stage"] == "production":
        approved = record.get("page_approval") or {}
        if {approved.get("svg_hash"), approved.get("png_hash"), approved.get("review_hash")} != {record["svg_hash"], record["png_hash"], record["review_report_hash"]}:
            raise ProductionError("deep_fusion page approval is required before sealing")
    output = _output_path(project, page_id); output.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(current, output)
    record.update({"state": "passed", "svg_hash": _sha256(output), "notes_hash": _sha256(_notes_path(project, page_id))}); state["active_page"] = None
    if state["stage"] == "sample_production" and _all_passed(state, state["samples"]["page_ids"]):
        state["stage"] = "sample_confirmation"; state["samples"]["status"] = "pending"; state["samples"]["confirmations"]["design"] = "pending"
    elif state["stage"] in {"production", "repair_required"}:
        _advance_after_formal_page(project, state, _plan(project))
    _save(project, state)
    return {"page_id": page_id, "state": "passed", "stage": state["stage"], "next_allowed_actions": _next_actions(state)}


def sample_confirm(project_path: str | Path, decision: str, *, page_id: str | None = None, replacements: list[str] | None = None, reason: str | None = None, reset_scope: str | None = None) -> dict[str, Any]:
    return approve_phase1(project_path, "design", decision, feedback=reason, reset_scope=reset_scope)


def _next_actions(state: dict[str, Any]) -> list[str]:
    if state["stage"] == "director_pending":
        return ["submit <project> --role content_strategist --artifact <director_plan.json>", "approve <project> --type brief --decision A"]
    if state["stage"] == "design_pending":
        return ["submit <project> --role visual_director --artifact <design_genome.json>", "lock-spec"]
    if state["stage"] == "sample_production":
        return ["page-begin <probe_page_id>"]
    if state["stage"] == "sample_confirmation":
        return ["approve <project> --type design --decision A|B|C"]
    if state["stage"] == "production":
        return ["page-begin <next_page_id>"]
    return ["status"]


def status(project_path: str | Path) -> dict[str, Any]:
    project, state = _project(project_path), _load(_project(project_path)); changes = reconcile(project, state); state = _load(project)
    result = {"stage": state["stage"], "active_page": state.get("active_page"), "changes": changes, "samples": state["samples"], "pages": state["pages"], "next_allowed_actions": _next_actions(state)}
    if state["stage"] == "director_pending": result.update(_awaiting_confirmation("brief", f"approve {project} --type brief --decision A", next_action="approve the Director Plan"))
    elif state["stage"] == "sample_confirmation": result.update(_awaiting_confirmation("design", f"approve {project} --type design --decision A", next_action="approve the three design probes"))
    return result


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
