#!/usr/bin/env python3
"""Validate and install the single Strategist director plan for a project."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


LEGACY_SCHEMA_VERSION = "1.0"
SCHEMA_VERSION = "2.0"
EXCLUDED_SAMPLE_TYPES = {
    "cover",
    "toc",
    "agenda",
    "closing",
    "ending",
    "plain_text",
    "text",
}
LEGACY_SAMPLE_DIMENSIONS = {"content_logic", "information_density", "visual_direction"}
SAMPLE_RISK_TYPES = {"card_stack_risk", "relationship_density", "visual_signature"}
PAGE_FIELDS = (
    "page_id",
    "headline",
    "page_goal",
    "page_role",
    "key_message",
    "relationship_type",
    "visual_anchor",
    "rhythm_role",
)
RHYTHM_ROLES = {"anchor", "build", "explain", "transition", "climax", "close"}


class DirectorPlanError(RuntimeError):
    """Raised when the director plan violates the planning contract."""


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DirectorPlanError(f"{path} must be a non-empty string")
    return value.strip()


def _validate_common(plan: dict[str, Any]) -> None:
    content_map = plan.get("content_map")
    if not isinstance(content_map, dict):
        raise DirectorPlanError("content_map must be an object")
    for key in ("core_argument", "key_findings", "root_causes", "recommendations"):
        value = content_map.get(key)
        if key == "core_argument":
            _require_string(value, f"content_map.{key}")
        elif not isinstance(value, list) or not value:
            raise DirectorPlanError(f"content_map.{key} must be a non-empty list")

    fact_boundary = plan.get("fact_boundary")
    if not isinstance(fact_boundary, dict) or not fact_boundary:
        raise DirectorPlanError("fact_boundary must be a non-empty object")
    storyline = plan.get("storyline")
    if not isinstance(storyline, dict):
        raise DirectorPlanError("storyline must be an object")
    _require_string(storyline.get("core_narrative"), "storyline.core_narrative")
    logic_flow = storyline.get("logic_flow")
    if not isinstance(logic_flow, list) or not logic_flow:
        raise DirectorPlanError("storyline.logic_flow must be a non-empty list")


def _validate_legacy_plan(plan: dict[str, Any], *, expected_pages: int | None = None) -> dict[str, Any]:
    if plan.get("schema_version") != LEGACY_SCHEMA_VERSION:
        raise DirectorPlanError(f"legacy schema_version must be {LEGACY_SCHEMA_VERSION}")
    _validate_common(plan)

    slides = plan.get("slides")
    if not isinstance(slides, list) or not slides:
        raise DirectorPlanError("slides must be a non-empty list")
    if expected_pages is not None and len(slides) != expected_pages:
        raise DirectorPlanError(f"slides count {len(slides)} does not match expected {expected_pages}")
    ids: list[str] = []
    types: list[str] = []
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            raise DirectorPlanError(f"slides[{index}] must be an object")
        page_id = _require_string(slide.get("page_id"), f"slides[{index}].page_id")
        if page_id in ids:
            raise DirectorPlanError(f"duplicate page_id: {page_id}")
        ids.append(page_id)
        for key in ("page_name", "page_goal", "page_type", "key_message", "visual_structure"):
            _require_string(slide.get(key), f"slides[{index}].{key}")
        types.append(str(slide["page_type"]).strip().lower())
    for index in range(len(types) - 2):
        if types[index] == types[index + 1] == types[index + 2]:
            raise DirectorPlanError(
                f"three consecutive slides use page_type {types[index]!r} at {ids[index]}"
            )

    samples = plan.get("samples")
    if not isinstance(samples, list) or len(samples) != 3:
        raise DirectorPlanError("samples must contain exactly three pages")
    sample_ids: list[str] = []
    dimensions: set[str] = set()
    slide_by_id = {slide["page_id"]: slide for slide in slides}
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise DirectorPlanError(f"samples[{index}] must be an object")
        page_id = _require_string(sample.get("page_id"), f"samples[{index}].page_id")
        dimension = _require_string(sample.get("validation_dimension"), f"samples[{index}].validation_dimension")
        _require_string(sample.get("reason"), f"samples[{index}].reason")
        if page_id not in slide_by_id:
            raise DirectorPlanError(f"sample page not found in slides: {page_id}")
        if page_id in sample_ids:
            raise DirectorPlanError(f"duplicate sample page: {page_id}")
        page_type = str(slide_by_id[page_id]["page_type"]).strip().lower()
        if page_type in EXCLUDED_SAMPLE_TYPES:
            raise DirectorPlanError(f"sample page {page_id} uses excluded type {page_type}")
        if dimension not in LEGACY_SAMPLE_DIMENSIONS:
            raise DirectorPlanError(f"unsupported sample validation_dimension: {dimension}")
        sample_ids.append(page_id)
        dimensions.add(dimension)
    if dimensions != LEGACY_SAMPLE_DIMENSIONS:
        raise DirectorPlanError("samples must cover content_logic, information_density, and visual_direction")
    return plan


def _validate_v2_plan(plan: dict[str, Any], *, expected_pages: int | None = None) -> dict[str, Any]:
    declared = plan.get("schema_version")
    if declared not in (None, SCHEMA_VERSION):
        raise DirectorPlanError(f"schema_version must be {SCHEMA_VERSION} when pages is used")
    _validate_common(plan)

    pages = plan.get("pages")
    if not isinstance(pages, list) or not pages:
        raise DirectorPlanError("pages must be a non-empty list")
    if expected_pages is not None and len(pages) != expected_pages:
        raise DirectorPlanError(f"pages count {len(pages)} does not match expected {expected_pages}")

    ids: list[str] = []
    structure_signatures: list[tuple[str, str]] = []
    page_by_id: dict[str, dict[str, Any]] = {}
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise DirectorPlanError(f"pages[{index}] must be an object")
        for field in PAGE_FIELDS:
            _require_string(page.get(field), f"pages[{index}].{field}")
        page_id = str(page["page_id"]).strip()
        if page_id in ids:
            raise DirectorPlanError(f"duplicate page_id: {page_id}")
        ids.append(page_id)
        page_by_id[page_id] = page

        evidence_refs = page.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            raise DirectorPlanError(f"pages[{index}].evidence_refs must be a list")
        page_role = str(page["page_role"]).strip().lower()
        if page_role not in EXCLUDED_SAMPLE_TYPES and not evidence_refs:
            raise DirectorPlanError(f"pages[{index}].evidence_refs must cite source material")
        rhythm_role = str(page["rhythm_role"]).strip().lower()
        if rhythm_role not in RHYTHM_ROLES:
            raise DirectorPlanError(f"unsupported rhythm_role: {rhythm_role}")
        structure_signatures.append(
            (
                str(page["relationship_type"]).strip().lower(),
                str(page["visual_anchor"]).strip().lower(),
            )
        )

    for index in range(len(structure_signatures) - 2):
        if len(set(structure_signatures[index:index + 3])) == 1:
            raise DirectorPlanError(
                f"three consecutive pages repeat relationship_type and visual_anchor at {ids[index]}"
            )

    samples = plan.get("sample_pages")
    if not isinstance(samples, list) or len(samples) != 3:
        raise DirectorPlanError("sample_pages must contain exactly three pages")
    sample_ids: list[str] = []
    risk_types: set[str] = set()
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise DirectorPlanError(f"sample_pages[{index}] must be an object")
        page_id = _require_string(sample.get("page_id"), f"sample_pages[{index}].page_id")
        risk_type = _require_string(sample.get("risk_type"), f"sample_pages[{index}].risk_type")
        _require_string(sample.get("reason"), f"sample_pages[{index}].reason")
        if page_id not in page_by_id:
            raise DirectorPlanError(f"sample page not found in pages: {page_id}")
        if page_id in sample_ids:
            raise DirectorPlanError(f"duplicate sample page: {page_id}")
        page_role = str(page_by_id[page_id]["page_role"]).strip().lower()
        if page_role in EXCLUDED_SAMPLE_TYPES:
            raise DirectorPlanError(f"sample page {page_id} uses excluded role {page_role}")
        if risk_type not in SAMPLE_RISK_TYPES:
            raise DirectorPlanError(f"unsupported sample risk_type: {risk_type}")
        sample_ids.append(page_id)
        risk_types.add(risk_type)
    if risk_types != SAMPLE_RISK_TYPES:
        raise DirectorPlanError(
            "sample_pages must cover card_stack_risk, relationship_density, and visual_signature"
        )
    return plan


def validate_director_plan(plan: dict[str, Any], *, expected_pages: int | None = None) -> dict[str, Any]:
    """Validate Director Plan 2.0 while preserving the installed 1.0 contract."""
    if not isinstance(plan, dict):
        raise DirectorPlanError("director plan must be an object")
    if "pages" in plan or plan.get("schema_version") == SCHEMA_VERSION:
        return _validate_v2_plan(plan, expected_pages=expected_pages)
    return _validate_legacy_plan(plan, expected_pages=expected_pages)


def plan_pages(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan.get("pages") or plan.get("slides") or [])


def plan_samples(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan.get("sample_pages") or plan.get("samples") or [])


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def install_director_plan(
    project_path: str | Path,
    plan_path: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    project = Path(project_path).expanduser().resolve()
    source = Path(plan_path).expanduser().resolve()
    if not project.is_dir():
        raise DirectorPlanError(f"project not found: {project}")
    if not source.is_file():
        raise DirectorPlanError(f"director plan not found: {source}")
    try:
        plan = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DirectorPlanError(f"invalid JSON: {exc}") from exc

    contract_path = project / "analysis" / "director_contract.json"
    expected_pages = None
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        expected_pages = int(contract["page_count"])
    validate_director_plan(plan, expected_pages=expected_pages)

    destination = project / "analysis" / "director_plan.json"
    if destination.exists() and not force:
        raise DirectorPlanError(f"director_plan.json already exists: {destination}")
    _atomic_json(destination, plan)

    from production import configure_director_plan

    configure_director_plan(project, plan, reset=force)
    return {
        "project": str(project),
        "director_plan": str(destination),
        "page_count": len(plan_pages(plan)),
        "samples": [sample["page_id"] for sample in plan_samples(plan)],
        "stage": "sample_production",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install and validate director_plan.json")
    parser.add_argument("project")
    parser.add_argument("plan")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = install_director_plan(args.project, args.plan, force=args.force)
    except DirectorPlanError as exc:
        print(f"error: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
