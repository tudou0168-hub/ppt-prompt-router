#!/usr/bin/env python3
"""Stateful, opt-in per-page production control for PPT Master projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
STATE_REL = Path("analysis/production_state.json")
CURRENT_REL = Path(".page_work/current.svg")
REVIEW_STATUSES = {"ok", "fixed", "needs_human", "render_failed", "prereq_failed"}
GLOBAL_HASH_FILES = {
    "director_contract_hash": Path("analysis/director_contract.json"),
    "director_profile_hash": Path("analysis/director_profile.md"),
    "director_plan_hash": Path("analysis/director_plan.json"),
    "design_spec_hash": Path("design_spec.md"),
    "spec_lock_hash": Path("spec_lock.md"),
}


class ProductionError(RuntimeError):
    """Raised when a production invariant would be violated."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _project(path: str | Path) -> Path:
    project = Path(path).expanduser().resolve()
    if not project.is_dir():
        raise ProductionError(f"project not found: {project}")
    return project


def _state_path(project: Path) -> Path:
    return project / STATE_REL


def _load(project: Path) -> dict[str, Any]:
    path = _state_path(project)
    if not path.is_file():
        raise ProductionError(f"controlled production is not initialized: {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionError(f"invalid production state: {exc}") from exc
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ProductionError(
            f"unsupported production state schema: {state.get('schema_version')!r}"
        )
    return state


def _save(project: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    _atomic_json(_state_path(project), state)


def _page(state: dict[str, Any], page_id: str) -> dict[str, Any]:
    try:
        return state["pages"][page_id]
    except KeyError as exc:
        raise ProductionError(f"unknown page: {page_id}") from exc


def _work_path(project: Path, record: dict[str, Any]) -> Path:
    rel = record.get("work_file") or str(Path(".page_work/repairs") / record["output_file"])
    return project / rel


def _director_plan(project: Path) -> dict[str, Any] | None:
    path = project / "analysis" / "director_plan.json"
    if not path.is_file():
        return None
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionError(f"invalid director plan: {exc}") from exc
    return plan


def _plan_pages(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan.get("pages") or plan.get("slides") or [])


def _plan_samples(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan.get("sample_pages") or plan.get("samples") or [])


def _requires_native_review(project: Path) -> bool:
    plan = _director_plan(project)
    return bool(plan and isinstance(plan.get("pages"), list))


def _review_path(project: Path, page_id: str) -> Path:
    return project / ".review" / f"{page_id}.json"


def _reset_visual_record(record: dict[str, Any], reason: str) -> None:
    record["visual_check"] = {"status": "pending", "reason": reason}
    record["review_report_hash"] = None
    record["reviewed_png_hash"] = None
    record["review_passed"] = False
    record["blocking_issues"] = []


def _current_global_hashes(project: Path) -> dict[str, str | None]:
    return {
        key: _sha256(project / rel) if (project / rel).is_file() else None
        for key, rel in GLOBAL_HASH_FILES.items()
    }


def _lock_or_check_global_hashes(project: Path, state: dict[str, Any]) -> None:
    recorded = state.setdefault("global_hashes", {})
    current = _current_global_hashes(project)
    changed: list[str] = []
    for key, value in current.items():
        if recorded.get(key) is None and value is not None:
            recorded[key] = value
        elif recorded.get(key) is not None and recorded.get(key) != value:
            changed.append(key)
    if changed:
        raise ProductionError(f"locked project inputs changed: {', '.join(changed)}")


def _director_requirements(project: Path, page_id: str) -> dict[str, Any]:
    plan = _director_plan(project)
    if not plan:
        return {}
    page = next((item for item in _plan_pages(plan) if item.get("page_id") == page_id), None)
    if not page:
        return {}
    if "pages" in plan:
        fields = (
            "headline",
            "page_goal",
            "page_role",
            "key_message",
            "relationship_type",
            "visual_anchor",
            "evidence_refs",
            "rhythm_role",
        )
        return {key: page.get(key) for key in fields}
    return {
        "headline": page.get("page_name"),
        "page_goal": page.get("page_goal"),
        "page_role": page.get("page_type"),
        "key_message": page.get("key_message"),
        "visual_anchor": page.get("visual_structure"),
    }


def _invalidate_record(
    project: Path,
    state: dict[str, Any],
    page_id: str,
    *,
    source: Path | None,
    reason: str,
) -> None:
    record = _page(state, page_id)
    repair_path = project / ".page_work" / "repairs" / record["output_file"]
    repair_path.parent.mkdir(parents=True, exist_ok=True)
    if source and source.is_file():
        os.replace(source, repair_path)
    preview = project / record.get("png_file", f".preview/{page_id}.png")
    preview.unlink(missing_ok=True)
    record.update(
        {
            "status": "repair_required",
            "work_file": str(repair_path.relative_to(project)),
            "svg_hash": None,
            "png_hash": None,
            "machine_check": {"status": "pending", "reason": reason},
        }
    )
    _reset_visual_record(record, reason)
    state["last_invalidation"] = {"page": page_id, "reason": reason, "at": _now()}
    _reset_dependent_gates(state, page_id)


def _passed_pages(state: dict[str, Any]) -> list[str]:
    return [page_id for page_id in state["page_order"] if _page(state, page_id).get("status") == "passed"]


def _midpoint_threshold(state: dict[str, Any]) -> int:
    return max(1, (len(state["page_order"]) + 1) // 2)


def _reset_dependent_gates(state: dict[str, Any], page_id: str) -> None:
    samples = state.get("samples") or {}
    if samples.get("required") and page_id in samples.get("pages", []):
        samples["status"] = "revision_required"
        samples.pop("approved_at", None)
    midpoint = state.get("midpoint_review") or {}
    if midpoint.get("required") and len(_passed_pages(state)) < _midpoint_threshold(state):
        midpoint["status"] = "pending"
        midpoint.pop("approved_at", None)
    deck = state.get("deck_review") or {}
    if deck.get("required"):
        deck["status"] = "pending"
        deck.pop("approved_at", None)


def reconcile(project: Path, state: dict[str, Any]) -> bool:
    """Reconcile recorded hashes with files; return whether state changed."""
    changed = False
    active_page = state.get("active_page")
    current = project / CURRENT_REL

    for page_id in state["page_order"]:
        record = _page(state, page_id)
        if record.get("status") == "passed":
            output = project / "svg_output" / record["output_file"]
            preview = project / record.get("png_file", f".preview/{page_id}.png")
            reason = None
            if not output.is_file() or _sha256(output) != record.get("svg_hash"):
                reason = "passed SVG is missing or changed"
            elif not preview.is_file() or _sha256(preview) != record.get("png_hash"):
                reason = "reviewed PNG is missing or changed"
            elif _requires_native_review(project):
                report = _review_path(project, page_id)
                if not report.is_file() or _sha256(report) != record.get("review_report_hash"):
                    reason = "visual review report is missing or changed"
                elif record.get("reviewed_png_hash") != record.get("png_hash"):
                    reason = "reviewed PNG hash no longer matches the passed page"
            if reason:
                _invalidate_record(
                    project,
                    state,
                    page_id,
                    source=output if output.is_file() else None,
                    reason=reason,
                )
                changed = True

    if active_page:
        record = _page(state, active_page)
        checked_hash = record.get("svg_hash")
        if checked_hash and (not current.is_file() or _sha256(current) != checked_hash):
            record.update(
                {
                    "status": "active",
                    "svg_hash": None,
                    "png_hash": None,
                    "machine_check": {
                        "status": "pending",
                        "reason": "current SVG changed after check",
                    },
                }
            )
            _reset_visual_record(record, "current SVG changed after check")
            changed = True
    return changed


def init_production(project_path: str | Path, pages: list[str], *, stage: str = "production") -> dict[str, Any]:
    project = _project(project_path)
    if not pages or any(not page.strip() for page in pages):
        raise ProductionError("at least one non-empty page id is required")
    page_order = list(dict.fromkeys(page.strip() for page in pages))
    if len(page_order) != len(pages):
        raise ProductionError("page ids must be unique")
    state_path = _state_path(project)
    if state_path.exists():
        raise ProductionError(f"production state already exists: {state_path}")

    (project / "analysis").mkdir(exist_ok=True)
    (project / ".page_work" / "repairs").mkdir(parents=True, exist_ok=True)
    (project / ".preview").mkdir(exist_ok=True)
    (project / "svg_output").mkdir(exist_ok=True)
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "created_at": _now(),
        "updated_at": _now(),
        "page_order": page_order,
        "active_page": None,
        "global_hashes": _current_global_hashes(project),
        "pages": {
            page_id: {
                "status": "pending",
                "output_file": f"{page_id}.svg",
                "png_file": f".preview/{page_id}.png",
                "svg_hash": None,
                "png_hash": None,
                "machine_check": {"status": "pending"},
                "visual_check": {"status": "pending"},
                "review_report_hash": None,
                "reviewed_png_hash": None,
                "review_passed": False,
                "blocking_issues": [],
            }
            for page_id in page_order
        },
        "samples": {"required": False, "status": "not_required", "pages": []},
        "midpoint_review": {"required": False, "status": "not_required"},
        "deck_review": {"required": False, "status": "not_required"},
    }
    _save(project, state)
    return state


def _assert_begin_allowed(state: dict[str, Any], page_id: str) -> None:
    active = state.get("active_page")
    if active:
        raise ProductionError(f"page {active} is active; pass it before beginning another page")
    repairs = [
        pid for pid in state["page_order"] if _page(state, pid).get("status") == "repair_required"
    ]
    if repairs and page_id not in repairs:
        raise ProductionError(f"repair required before continuing: {', '.join(repairs)}")

    samples = state.get("samples") or {}
    if samples.get("required") and samples.get("status") != "approved":
        if page_id not in samples.get("pages", []):
            raise ProductionError("sample approval is required before non-sample pages")
        for earlier in samples.get("pages", [])[: samples.get("pages", []).index(page_id)]:
            if _page(state, earlier).get("status") != "passed":
                raise ProductionError(f"sample order requires {earlier} to pass first")

    record = _page(state, page_id)
    if record.get("status") not in {"pending", "repair_required"}:
        raise ProductionError(f"page {page_id} cannot begin from status {record.get('status')}")

    if not samples.get("required"):
        for earlier in state["page_order"][: state["page_order"].index(page_id)]:
            if _page(state, earlier).get("status") != "passed":
                raise ProductionError(f"page order requires {earlier} to pass first")
    elif samples.get("status") == "approved":
        next_page = next(
            (
                pid for pid in state["page_order"]
                if _page(state, pid).get("status") in {"pending", "repair_required"}
            ),
            None,
        )
        if next_page is not None and page_id != next_page:
            raise ProductionError(f"director plan order requires {next_page} next")

    midpoint = state.get("midpoint_review") or {}
    if (
        midpoint.get("required")
        and midpoint.get("status") != "approved"
        and len(_passed_pages(state)) >= _midpoint_threshold(state)
    ):
        raise ProductionError("midpoint review is required before continuing")


def begin_page(project_path: str | Path, page_id: str) -> dict[str, Any]:
    project = _project(project_path)
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    _lock_or_check_global_hashes(project, state)
    _assert_begin_allowed(state, page_id)
    record = _page(state, page_id)
    current = project / CURRENT_REL
    current.parent.mkdir(parents=True, exist_ok=True)
    current.unlink(missing_ok=True)
    work_path = _work_path(project, record)
    if record.get("status") == "repair_required" and work_path.is_file():
        os.replace(work_path, current)
    record.update(
        {
            "status": "active",
            "work_file": str(CURRENT_REL),
            "svg_hash": None,
            "png_hash": None,
            "machine_check": {"status": "pending"},
        }
    )
    _reset_visual_record(record, "page begun")
    state["active_page"] = page_id
    _save(project, state)
    result = dict(record)
    result["director_requirements"] = _director_requirements(project, page_id)
    return result


def _run_quality_check(current: Path) -> subprocess.CompletedProcess[str]:
    checker = Path(__file__).resolve().parent / "svg_quality_checker.py"
    return subprocess.run(
        [sys.executable, str(checker), str(current)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _render_svg(current: Path, output: Path) -> None:
    """Delegate controlled rendering to PPT Master's native visual-review renderer."""
    try:
        from visual_review import render_svg_file
    except ImportError as exc:
        raise ProductionError("PPT Master visual_review.py is not importable") from exc
    try:
        result = render_svg_file(current, output)
    except Exception as exc:
        raise ProductionError(f"native visual-review render failed: {exc}") from exc
    if not result.get("ok") or result.get("all_background"):
        raise ProductionError("native visual-review render produced an invalid preview")


def _next_render_iteration(project: Path, page_id: str) -> int:
    preview_dir = project / ".preview"
    iterations: list[int] = []
    for path in preview_dir.glob(f"{page_id}.iter*.png"):
        suffix = path.stem.rsplit("iter", 1)[-1]
        if suffix.isdigit():
            iterations.append(int(suffix))
    return max(iterations, default=0) + 1


def check_render(project_path: str | Path) -> dict[str, Any]:
    project = _project(project_path)
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    page_id = state.get("active_page")
    if not page_id:
        raise ProductionError("no active page; run begin first")
    current = project / CURRENT_REL
    if not current.is_file():
        raise ProductionError(f"current SVG is missing: {current}")

    result = _run_quality_check(current)
    record = _page(state, page_id)
    record["machine_check"] = {
        "status": "passed" if result.returncode == 0 else "failed",
        "at": _now(),
        "exit_code": result.returncode,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-12000:],
    }
    if result.returncode != 0:
        record["status"] = "active"
        record["svg_hash"] = None
        record["png_hash"] = None
        _save(project, state)
        raise ProductionError(f"machine check failed for {page_id}")

    iteration = _next_render_iteration(project, page_id)
    output = project / ".preview" / f"{page_id}.iter{iteration}.png"
    _render_svg(current, output)
    record.update(
        {
            "status": "checked",
            "svg_hash": _sha256(current),
            "png_hash": _sha256(output),
            "png_file": str(output.relative_to(project)),
            "render_iteration": iteration,
        }
    )
    _reset_visual_record(record, "awaiting visual review")
    _save(project, state)
    return record


def _validate_visual_report(
    project: Path,
    state: dict[str, Any],
    page_id: str,
    current: Path,
    preview: Path,
) -> tuple[Path, dict[str, Any]]:
    report_path = _review_path(project, page_id)
    if not report_path.is_file():
        raise ProductionError(f"native visual review report is missing: {report_path}")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionError(f"invalid native visual review report: {exc}") from exc

    if report.get("page_id") != page_id or report.get("mode") != "controlled":
        raise ProductionError("visual review report does not identify the active controlled page")
    status = report.get("status")
    if status not in REVIEW_STATUSES:
        raise ProductionError(f"unsupported visual review status: {status!r}")
    if status not in {"ok", "fixed"}:
        raise ProductionError(f"visual review is not passed: {status}")
    blocking = report.get("blocking_issues")
    if not isinstance(blocking, list) or blocking:
        raise ProductionError("visual review has blocking issues")
    iterations = report.get("iterations")
    if not isinstance(iterations, list) or not iterations:
        raise ProductionError("visual review report must contain iterations")
    for index, item in enumerate(iterations, start=1):
        if not isinstance(item, dict) or item.get("iteration") != index:
            raise ProductionError("visual review iterations must be ordered from 1")
        if not item.get("svg_hash") or not item.get("png_hash"):
            raise ProductionError("each visual review iteration must bind SVG and PNG hashes")
        if not isinstance(item.get("findings"), list):
            raise ProductionError("each visual review iteration must contain findings")

    current_svg_hash = _sha256(current)
    current_png_hash = _sha256(preview)
    if report.get("final_svg_hash") != current_svg_hash:
        raise ProductionError("visual review report SVG hash is stale")
    if report.get("final_png_hash") != current_png_hash:
        raise ProductionError("visual review report PNG hash is stale")
    if iterations[-1].get("svg_hash") != current_svg_hash or iterations[-1].get("png_hash") != current_png_hash:
        raise ProductionError("final visual review iteration does not match current files")

    samples = (state.get("samples") or {}).get("pages", [])
    if page_id in samples:
        if len(iterations) < 2 or status != "fixed":
            raise ProductionError("sample pages require two visual-review iterations and final status fixed")
        if not iterations[0].get("findings"):
            raise ProductionError("sample iteration 1 must record at least one real finding")
        if iterations[0].get("svg_hash") == iterations[-1].get("svg_hash"):
            raise ProductionError("sample SVG must change after the first visual review")
        if iterations[0].get("png_hash") == iterations[-1].get("png_hash"):
            raise ProductionError("sample PNG must change after the first visual review")
    return report_path, report


def pass_page(
    project_path: str | Path,
    *,
    visual_check: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    project = _project(project_path)
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    page_id = state.get("active_page")
    if not page_id:
        raise ProductionError("no active page")
    record = _page(state, page_id)
    current = project / CURRENT_REL
    preview = project / record["png_file"]
    if record.get("status") != "checked":
        raise ProductionError("current page must pass check-render first")
    if record.get("machine_check", {}).get("status") != "passed":
        raise ProductionError("machine check is not passed")
    if not current.is_file() or _sha256(current) != record.get("svg_hash"):
        raise ProductionError("current SVG changed after check-render")
    if not preview.is_file() or _sha256(preview) != record.get("png_hash"):
        raise ProductionError("rendered PNG is missing or changed")

    report_path: Path | None = None
    if _requires_native_review(project):
        report_path, report = _validate_visual_report(project, state, page_id, current, preview)
    elif visual_check != "passed":
        raise ProductionError("legacy pass-page requires --visual-check passed")

    destination = project / "svg_output" / record["output_file"]
    destination.parent.mkdir(exist_ok=True)
    os.replace(current, destination)
    canonical_preview = project / ".preview" / f"{page_id}.png"
    shutil.copyfile(preview, canonical_preview)
    record.update(
        {
            "status": "passed",
            "work_file": None,
            "svg_hash": _sha256(destination),
            "png_file": str(canonical_preview.relative_to(project)),
            "png_hash": _sha256(canonical_preview),
            "visual_check": {"status": "passed", "at": _now()},
            "review_report_hash": _sha256(report_path) if report_path else None,
            "reviewed_png_hash": _sha256(canonical_preview),
            "review_passed": True,
            "blocking_issues": [],
            "passed_at": _now(),
        }
    )
    state["active_page"] = None
    _save(project, state)
    return record


def configure_director_plan(
    project_path: str | Path,
    plan: dict[str, Any],
    *,
    reset: bool = False,
) -> dict[str, Any]:
    project = _project(project_path)
    page_order = [page["page_id"] for page in _plan_pages(plan)]
    state_path = _state_path(project)
    if state_path.is_file():
        state = _load(project)
        if any(record.get("status") != "pending" for record in state.get("pages", {}).values()) and not reset:
            raise ProductionError("cannot attach a director plan after page production has started")
        if state.get("page_order") != page_order:
            if not reset and state.get("page_order"):
                raise ProductionError("director plan page order does not match initialized production state")
            state = init_state_payload(page_order, stage="sample_production")
    else:
        state = init_state_payload(page_order, stage="sample_production")
    samples = [sample["page_id"] for sample in _plan_samples(plan)]
    state["stage"] = "sample_production"
    state["samples"] = {"required": True, "status": "pending", "pages": samples}
    state["midpoint_review"] = {
        "required": True,
        "status": "pending",
        "threshold": _midpoint_threshold(state),
    }
    state["deck_review"] = {"required": True, "status": "pending"}
    state["global_hashes"] = _current_global_hashes(project)
    _save(project, state)
    return state


def init_state_payload(page_order: list[str], *, stage: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "created_at": _now(),
        "updated_at": _now(),
        "page_order": page_order,
        "active_page": None,
        "global_hashes": {},
        "pages": {
            page_id: {
                "status": "pending",
                "output_file": f"{page_id}.svg",
                "png_file": f".preview/{page_id}.png",
                "svg_hash": None,
                "png_hash": None,
                "machine_check": {"status": "pending"},
                "visual_check": {"status": "pending"},
                "review_report_hash": None,
                "reviewed_png_hash": None,
                "review_passed": False,
                "blocking_issues": [],
            }
            for page_id in page_order
        },
        "samples": {"required": False, "status": "not_required", "pages": []},
        "midpoint_review": {"required": False, "status": "not_required"},
        "deck_review": {"required": False, "status": "not_required"},
    }


def sample_decision(
    project_path: str | Path,
    decision: str,
    *,
    pages: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    project = _project(project_path)
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    samples = state.get("samples") or {}
    if not samples.get("required"):
        raise ProductionError("this project has no sample gate")
    decision = decision.upper()
    if decision == "A":
        incomplete = [pid for pid in samples["pages"] if _page(state, pid).get("status") != "passed"]
        if incomplete:
            raise ProductionError(f"all sample pages must pass before approval: {', '.join(incomplete)}")
        samples.update({"status": "approved", "approved_at": _now(), "notes": notes or ""})
        state["stage"] = "production"
    elif decision == "B":
        targets = pages or []
        if not targets or any(pid not in samples["pages"] for pid in targets):
            raise ProductionError("decision B requires one or more current sample page ids")
        if state.get("active_page"):
            raise ProductionError("finish the active page before requesting sample revision")
        for page_id in targets:
            record = _page(state, page_id)
            if record.get("status") == "passed":
                output = project / "svg_output" / record["output_file"]
                _invalidate_record(project, state, page_id, source=output, reason="sample revision requested")
        samples.update({"status": "revision_required", "notes": notes or ""})
        state["stage"] = "sample_production"
    elif decision == "C":
        replacements = pages or []
        if len(replacements) != 3 or len(set(replacements)) != 3:
            raise ProductionError("decision C requires exactly three unique replacement pages")
        if any(pid not in state["pages"] for pid in replacements):
            raise ProductionError("replacement sample page is not in director plan")
        plan_path = project / "analysis" / "director_plan.json"
        if plan_path.is_file():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            excluded = {"cover", "toc", "agenda", "closing", "ending", "plain_text", "text"}
            types = {
                page["page_id"]: str(page.get("page_role") or page.get("page_type") or "").strip().lower()
                for page in _plan_pages(plan)
            }
            invalid = [pid for pid in replacements if types.get(pid) in excluded]
            if invalid:
                raise ProductionError(f"replacement samples use excluded page types: {', '.join(invalid)}")
            sample_key = "sample_pages" if "sample_pages" in plan else "samples"
            plan_samples = plan.get(sample_key) or []
            if len(plan_samples) != 3:
                raise ProductionError("director plan does not contain three replaceable samples")
            for sample, replacement in zip(plan_samples, replacements):
                sample["page_id"] = replacement
                label = sample.get("risk_type") or sample.get("validation_dimension") or "sample risk"
                sample["reason"] = f"User-reselected page for {label}"
            _atomic_json(plan_path, plan)
            state.setdefault("global_hashes", {})["director_plan_hash"] = _sha256(plan_path)
        samples.update({"status": "pending", "pages": replacements, "notes": notes or ""})
        state["stage"] = "sample_production"
    else:
        raise ProductionError("sample decision must be A, B, or C")
    _save(project, state)
    return samples


def _review_pages(state: dict[str, Any], kind: str) -> list[str]:
    if kind == "deck":
        return list(state["page_order"])
    passed = sorted(
        _passed_pages(state),
        key=lambda pid: _page(state, pid).get("passed_at") or "",
    )
    return list(dict.fromkeys([*(state.get("samples") or {}).get("pages", []), *passed[-2:]]))


def record_review(
    project_path: str | Path,
    kind: str,
    status: str,
    *,
    reviewed_pages: list[str],
    notes: str,
) -> dict[str, Any]:
    project = _project(project_path)
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    key = "midpoint_review" if kind == "midpoint" else "deck_review"
    gate = state.get(key) or {}
    if not gate.get("required"):
        raise ProductionError(f"{kind} review is not required")
    if kind == "midpoint" and len(_passed_pages(state)) < _midpoint_threshold(state):
        raise ProductionError("midpoint threshold has not been reached")
    if kind == "deck" and len(_passed_pages(state)) != len(state["page_order"]):
        raise ProductionError("all pages must pass before deck review")
    expected = set(_review_pages(state, kind))
    if not expected.issubset(set(reviewed_pages)):
        raise ProductionError(f"review must include: {', '.join(sorted(expected))}")
    normalized = "approved" if status == "passed" else "failed"
    gate.update(
        {
            "status": normalized,
            "reviewed_pages": reviewed_pages,
            "notes": notes,
            "reviewed_at": _now(),
        }
    )
    if normalized == "approved":
        gate["approved_at"] = _now()
        state["stage"] = "production_after_midpoint" if kind == "midpoint" else "export_ready"
    _save(project, state)
    return gate


def reopen_page(project_path: str | Path, page_id: str) -> dict[str, Any]:
    project = _project(project_path)
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    if state.get("active_page"):
        raise ProductionError(f"page {state['active_page']} is already active")
    record = _page(state, page_id)
    if record.get("status") == "passed":
        output = project / "svg_output" / record["output_file"]
        _invalidate_record(project, state, page_id, source=output, reason="page reopened")
        _save(project, state)
    if _page(state, page_id).get("status") != "repair_required":
        raise ProductionError(f"page {page_id} is not available for repair")
    return begin_page(project, page_id)


def invalidate_output_file(project_path: str | Path, filename: str, *, reason: str) -> bool:
    """Invalidate one browser-edited output file in a controlled project."""
    project = _project(project_path)
    if not _state_path(project).is_file():
        return False
    state = _load(project)
    page_id = next(
        (pid for pid, rec in state["pages"].items() if rec.get("output_file") == filename),
        None,
    )
    if page_id is None:
        raise ProductionError(f"edited SVG is not registered in production state: {filename}")
    output = project / "svg_output" / filename
    _invalidate_record(project, state, page_id, source=output, reason=reason)
    _save(project, state)
    return True


def export_preflight(project_path: str | Path) -> list[str]:
    """Return blocking export errors. Legacy projects return an empty list."""
    project = _project(project_path)
    if not _state_path(project).is_file():
        return []
    state = _load(project)
    if reconcile(project, state):
        _save(project, state)
    errors: list[str] = []
    try:
        _lock_or_check_global_hashes(project, state)
    except ProductionError as exc:
        errors.append(str(exc))
    if state.get("active_page"):
        errors.append(f"active page is not passed: {state['active_page']}")
    for page_id in state["page_order"]:
        record = _page(state, page_id)
        if record.get("status") != "passed":
            errors.append(f"page {page_id} status is {record.get('status')}, expected passed")
            continue
        if record.get("machine_check", {}).get("status") != "passed":
            errors.append(f"page {page_id} machine check is not passed")
        if record.get("visual_check", {}).get("status") != "passed":
            errors.append(f"page {page_id} visual check is not passed")
        if _requires_native_review(project):
            report = _review_path(project, page_id)
            if not report.is_file() or _sha256(report) != record.get("review_report_hash"):
                errors.append(f"page {page_id} visual review report is missing or changed")
            if record.get("reviewed_png_hash") != record.get("png_hash"):
                errors.append(f"page {page_id} reviewed PNG hash is stale")

    for key, label in (
        ("samples", "sample approval"),
        ("midpoint_review", "midpoint review"),
        ("deck_review", "deck review"),
    ):
        gate = state.get(key) or {}
        if gate.get("required") and gate.get("status") != "approved":
            errors.append(f"{label} is required and not approved")
    return errors


def can_export(project_path: str | Path) -> bool:
    return not export_preflight(project_path)


def _pages_from_args(args: argparse.Namespace) -> list[str]:
    if args.pages:
        return args.pages
    if args.page_count:
        return [f"P{index:02d}" for index in range(1, args.page_count + 1)]
    raise ProductionError("init requires --pages or --page-count")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PPT Master controlled page production")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("project")
    init.add_argument("--pages", nargs="+")
    init.add_argument("--page-count", type=int)
    init.add_argument("--stage", default="production")
    begin = sub.add_parser("begin")
    begin.add_argument("project")
    begin.add_argument("page")
    check = sub.add_parser("check-render")
    check.add_argument("project")
    passed = sub.add_parser("pass-page")
    passed.add_argument("project")
    passed.add_argument("--visual-check", choices=["passed", "failed"])
    passed.add_argument("--notes")
    reopen = sub.add_parser("reopen-page")
    reopen.add_argument("project")
    reopen.add_argument("page")
    export = sub.add_parser("can-export")
    export.add_argument("project")
    sample = sub.add_parser("sample-decision")
    sample.add_argument("project")
    sample.add_argument("decision", choices=["A", "B", "C", "a", "b", "c"])
    sample.add_argument("--pages", nargs="*")
    sample.add_argument("--notes")
    review = sub.add_parser("review")
    review.add_argument("project")
    review.add_argument("kind", choices=["midpoint", "deck"])
    review.add_argument("--status", required=True, choices=["passed", "failed"])
    review.add_argument("--reviewed-pages", nargs="+", required=True)
    review.add_argument("--notes", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_production(args.project, _pages_from_args(args), stage=args.stage)
        elif args.command == "begin":
            result = begin_page(args.project, args.page)
        elif args.command == "check-render":
            result = check_render(args.project)
        elif args.command == "pass-page":
            result = pass_page(args.project, visual_check=args.visual_check, notes=args.notes)
        elif args.command == "reopen-page":
            result = reopen_page(args.project, args.page)
        elif args.command == "sample-decision":
            result = sample_decision(
                args.project,
                args.decision,
                pages=args.pages,
                notes=args.notes,
            )
        elif args.command == "review":
            result = record_review(
                args.project,
                args.kind,
                args.status,
                reviewed_pages=args.reviewed_pages,
                notes=args.notes,
            )
        else:
            errors = export_preflight(args.project)
            result = {"allowed": not errors, "errors": errors}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if not errors else 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ProductionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
