#!/usr/bin/env python3
"""Validate and install the single PPT Director plan."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


PAGE_FIELDS = (
    "page_id", "chapter", "page_goal", "key_message", "relationship_type",
    "visual_anchor", "image_strategy", "evidence_refs", "risk_tags", "rhythm_role",
)
PAGE_FIELDS_31 = (
    "page_id", "page_role", "page_intent", "required_messages", "source_refs",
    "factual_constraints", "unresolved_questions",
)
PAGE_OPTIONAL_31 = {"optional_notes"}
PAGE_FORBIDDEN_31 = {
    "layout", "grid", "card_count", "column_count", "color_scheme", "font_rule",
    "composition", "visual_archetype", "visual_style", "icon_strategy",
    "image_position", "decoration_rule", "relationship_type", "visual_anchor",
    "image_strategy", "rhythm_role",
}
RISK_TYPES = {"information_density", "complex_relationship", "visual_signature"}
EXCLUDED_SAMPLE_ROLES = {"cover", "toc", "agenda", "closing", "ending", "plain_text", "text"}
RHYTHM_ROLES = {"anchor", "build", "explain", "transition", "climax", "close"}
REFERENCE_RE = re.compile(r"^(?P<path>[^#]+)#(?:(?:L(?P<start>\d+)-L(?P<end>\d+))|(?:H:(?P<heading>.+)))$")


class DirectorPlanError(RuntimeError):
    pass


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


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DirectorPlanError(f"{label} must be a non-empty string")
    return value.strip()


def _project_file(project: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() not in {".md", ".markdown"}:
        raise DirectorPlanError(f"evidence reference must use project-relative Markdown: {relative}")
    path = (project / rel).resolve()
    try:
        path.relative_to(project.resolve())
    except ValueError as exc:
        raise DirectorPlanError(f"evidence reference escapes project: {relative}") from exc
    if not path.is_file():
        raise DirectorPlanError(f"evidence file not found: {relative}")
    return path


def resolve_evidence_ref(project: str | Path, reference: str) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    match = REFERENCE_RE.match(reference.strip())
    if not match:
        raise DirectorPlanError(f"invalid evidence reference: {reference}")
    path = _project_file(root, match.group("path"))
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if match.group("start"):
        start, end = int(match.group("start")), int(match.group("end"))
        if start < 1 or end < start or end > len(lines):
            raise DirectorPlanError(f"evidence line range is invalid: {reference}")
    else:
        heading = match.group("heading").strip()
        found = []
        for number, line in enumerate(lines, start=1):
            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading_match and heading_match.group(2).strip() == heading:
                found.append((number, len(heading_match.group(1))))
        if len(found) != 1:
            raise DirectorPlanError(f"evidence heading must match exactly once: {reference}")
        start, level = found[0]
        end = len(lines)
        for number in range(start + 1, len(lines) + 1):
            heading_match = re.match(r"^(#{1,6})\s+", lines[number - 1])
            if heading_match and len(heading_match.group(1)) <= level:
                end = number - 1
                break
    return {"reference": reference, "path": str(path), "start_line": start, "end_line": end, "text": "\n".join(lines[start - 1:end])}


def validate_director_plan(project: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    if not isinstance(plan, dict):
        raise DirectorPlanError("director plan must be an object")
    pages = plan.get("pages")
    if not isinstance(pages, list) or not pages:
        raise DirectorPlanError("pages must be a non-empty list")
    contract = json.loads((root / "analysis" / "director_contract.json").read_text(encoding="utf-8"))
    expected = int(contract["page_count"])
    if len(pages) != expected:
        raise DirectorPlanError(f"page count {len(pages)} does not match contract {expected}")
    schema_31 = str(plan.get("schema_version") or "3.0") == "3.1"
    ids, signatures, page_by_id = [], [], {}
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise DirectorPlanError(f"pages[{index}] must be an object")
        fields = PAGE_FIELDS_31 if schema_31 else PAGE_FIELDS
        missing = [field for field in fields if field not in page]
        if missing:
            raise DirectorPlanError(f"pages[{index}] missing fields: {', '.join(missing)}")
        if schema_31:
            forbidden = sorted(PAGE_FORBIDDEN_31.intersection(page))
            unknown = sorted(set(page) - set(PAGE_FIELDS_31) - PAGE_OPTIONAL_31)
            if forbidden:
                raise DirectorPlanError(f"pages[{index}] contains Director-owned visual fields: {', '.join(forbidden)}")
            if unknown:
                raise DirectorPlanError(f"pages[{index}] contains unsupported fields: {', '.join(unknown)}")
        for field in fields:
            if field in {"evidence_refs", "risk_tags", "required_messages", "source_refs", "factual_constraints", "unresolved_questions"}:
                if not isinstance(page[field], list):
                    raise DirectorPlanError(f"pages[{index}].{field} must be a list")
            else:
                _string(page[field], f"pages[{index}].{field}")
        page_id = page["page_id"].strip()
        if page_id in ids:
            raise DirectorPlanError(f"duplicate page_id: {page_id}")
        ids.append(page_id)
        page_by_id[page_id] = page
        if not schema_31 and page["rhythm_role"].strip().lower() not in RHYTHM_ROLES:
            raise DirectorPlanError(f"invalid rhythm_role on {page_id}")
        role = str(page.get("page_role") or "").strip().lower()
        refs = page["source_refs"] if schema_31 else page["evidence_refs"]
        if role not in EXCLUDED_SAMPLE_ROLES and not refs:
            raise DirectorPlanError(f"{page_id} must include evidence_refs")
        for reference in refs:
            resolve_evidence_ref(root, _string(reference, f"{page_id}.evidence_refs"))
        if not schema_31:
            signatures.append((page["relationship_type"].strip().lower(), page["visual_anchor"].strip().lower()))
    if not schema_31:
        for index in range(len(signatures) - 2):
            if len(set(signatures[index:index + 3])) == 1:
                raise DirectorPlanError(f"three consecutive pages mechanically repeat at {ids[index]}")

    samples = plan.get("sample_pages")
    mode_path = root / ".director" / "generation_mode.json"
    mode = json.loads(mode_path.read_text(encoding="utf-8")).get("mode") if mode_path.is_file() else "standard"
    expected_samples = 2 if schema_31 and mode in {"template", "premium"} else 3
    if not isinstance(samples, list) or len(samples) != expected_samples:
        raise DirectorPlanError(f"sample_pages must contain exactly {expected_samples} pages")
    if expected_samples == 2:
        roles = [sample.get("sample_role") for sample in samples if isinstance(sample, dict)]
        if roles != ["overview", "complex"]:
            raise DirectorPlanError("template/premium sample_pages must be ordered as overview and complex")
    risks, sample_ids = set(), set()
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise DirectorPlanError(f"sample_pages[{index}] must be an object")
        page_id = _string(sample.get("page_id"), f"sample_pages[{index}].page_id")
        risk = _string(sample.get("risk_type"), f"sample_pages[{index}].risk_type") if expected_samples == 3 else str(sample.get("sample_role"))
        _string(sample.get("reason"), f"sample_pages[{index}].reason")
        if page_id not in page_by_id or page_id in sample_ids:
            raise DirectorPlanError(f"invalid or duplicate sample page: {page_id}")
        role = str(page_by_id[page_id].get("page_role") or "").strip().lower()
        if expected_samples == 3 and role in EXCLUDED_SAMPLE_ROLES:
            raise DirectorPlanError(f"sample page {page_id} uses excluded role {role}")
        if expected_samples == 3 and risk not in RISK_TYPES:
            raise DirectorPlanError(f"unsupported sample risk: {risk}")
        if expected_samples == 2 and risk == "overview" and role not in {"cover", "overview", "executive_summary", "summary"}:
            raise DirectorPlanError(f"overview sample {page_id} must be a cover or overview page")
        if expected_samples == 2 and risk == "complex":
            if role in EXCLUDED_SAMPLE_ROLES:
                raise DirectorPlanError(f"complex sample {page_id} uses excluded role {role}")
            if len(page_by_id[page_id].get("required_messages") or []) < 2:
                raise DirectorPlanError(f"complex sample {page_id} must contain multiple required messages")
        risks.add(risk); sample_ids.add(page_id)
    if expected_samples == 3 and risks != RISK_TYPES:
        raise DirectorPlanError("sample_pages must cover information_density, complex_relationship, and visual_signature")
    return plan


def load_plan(project: str | Path) -> dict[str, Any]:
    path = Path(project).expanduser().resolve() / "analysis" / "director_plan.json"
    if not path.is_file():
        raise DirectorPlanError("analysis/director_plan.json is required")
    return validate_director_plan(project, json.loads(path.read_text(encoding="utf-8")))


def plan_pages(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan["pages"])


def plan_samples(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan["sample_pages"])


def page_by_id(plan: dict[str, Any], page_id: str) -> dict[str, Any]:
    page = next((item for item in plan_pages(plan) if item["page_id"] == page_id), None)
    if page is None:
        raise DirectorPlanError(f"page is not in director plan: {page_id}")
    return page


def planning_context(project: str | Path, router_root: str | Path, runtime_root: str | Path) -> dict[str, Any]:
    root, router, runtime = Path(project).resolve(), Path(router_root).resolve(), Path(runtime_root).resolve()
    return {"stage": "director_pending", "required_context": [str(path) for path in (
        router / "SKILL.md", runtime / "MASTER.md", runtime / "references" / "strategist.md",
        runtime / "references" / "ppt-director-strategist.md",
        root / "analysis" / "director_profile.md", root / ".director" / "generation_mode.json",
        root / ".director" / "master_handoff.md", *sorted((root / "sources").glob("*.md")),
    )], "required_output": str(root / "analysis" / "director_plan.json"), "next_allowed_actions": ["plan --apply <candidate.json>"]}


def install_director_plan(project: str | Path, candidate: str | Path) -> dict[str, Any]:
    root, source = Path(project).expanduser().resolve(), Path(candidate).expanduser().resolve()
    destination = root / "analysis" / "director_plan.json"
    if destination.exists():
        raise DirectorPlanError("director_plan.json is immutable after installation; only sample-confirm C may update sample_pages")
    if not source.is_file():
        raise DirectorPlanError(f"candidate plan not found: {source}")
    plan = validate_director_plan(root, json.loads(source.read_text(encoding="utf-8")))
    _atomic_json(destination, plan)
    from production import attach_director_plan
    state = attach_director_plan(root)
    return {"director_plan": str(destination), "stage": state["stage"], "page_count": len(plan["pages"]), "sample_pages": plan["sample_pages"], "next_allowed_actions": ["lock-spec"]}


def replace_sample_pages(project: str | Path, replacements: list[str]) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    path = root / "analysis" / "director_plan.json"
    plan = load_plan(root)
    if len(replacements) != 3 or len(set(replacements)) != 3:
        raise DirectorPlanError("sample-confirm C requires exactly three unique pages")
    page_ids = {page["page_id"] for page in plan["pages"]}
    if any(page_id not in page_ids for page_id in replacements):
        raise DirectorPlanError("replacement sample page is not in director plan")
    updated = json.loads(json.dumps(plan, ensure_ascii=False))
    for sample, page_id in zip(updated["sample_pages"], replacements):
        sample["page_id"] = page_id
        sample["reason"] = f"User reselected {page_id} for {sample['risk_type']} risk"
    validate_director_plan(root, updated)
    _atomic_json(path, updated)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project"); parser.add_argument("candidate")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install_director_plan(args.project, args.candidate), ensure_ascii=False, indent=2))
        return 0
    except DirectorPlanError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
