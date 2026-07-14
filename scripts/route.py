#!/usr/bin/env python3
"""Deterministic Router 2.1 entrypoint and PPT Master handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from install import (  # noqa: E402
    PackageError,
    compile_director_profile,
    load_index,
    prompt_body,
    run_tool,
    validate_prompt_index,
)


ROUTER_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
TEMPLATE_INTENTS = {"reference_elements", "native_fill", "reusable_template", "none"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_master_skill() -> Path:
    """Resolve only the Master installed with this offline Router suite."""
    skills_root = ROOT.parent
    receipt_path = skills_root / ".ppt-director" / "install_receipt.json"
    if not receipt_path.is_file():
        raise PackageError("offline install receipt is missing; install the PPT Director suite first")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError("offline install receipt is invalid") from exc
    master = Path(str((receipt.get("paths") or {}).get("master") or "")).resolve(strict=False)
    expected = (skills_root / "ppt-master").resolve(strict=False)
    if master != expected or not (master / "scripts" / "project_manager.py").is_file():
        raise PackageError("offline receipt does not point to this suite's PPT Master")
    managed = {row.get("path"): row.get("sha256") for row in receipt.get("managed_files", []) if isinstance(row, dict)}
    manager_key = "skills/ppt-master/scripts/project_manager.py"
    if managed.get(manager_key) != _sha256(master / "scripts" / "project_manager.py"):
        raise PackageError("installed PPT Master is modified or no longer managed by this suite")
    return master


def _terms(entry: dict[str, Any], key: str) -> list[str]:
    value = entry.get(key) or []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def score_profile(entry: dict[str, Any], text: str) -> tuple[int, dict[str, list[str]]]:
    lowered = text.lower()
    groups = {
        "primary": ("required_signals", 6),
        "strong": ("strong_signals", 3),
        "supporting": ("supporting_signals", 1),
        "negative": ("negative_signals", -5),
        "avoid_when": ("avoid_when", -8),
    }
    score = 0
    matched: dict[str, list[str]] = {}
    for label, (key, weight) in groups.items():
        hits = list(dict.fromkeys(term for term in _terms(entry, key) if term.lower() in lowered))
        if hits:
            matched[label] = hits
            score += weight * len(hits)
    return score, matched


def route_profile(
    index: dict[str, Any],
    text: str,
    *,
    prompt_id: str | None = None,
) -> dict[str, Any]:
    entries = validate_prompt_index(index)
    if prompt_id:
        entry = next((item for item in entries if item["id"] == prompt_id), None)
        if entry is None:
            raise PackageError(f"unknown prompt_id: {prompt_id}")
        return {"status": "selected", "entry": entry, "score": None, "matched": {"explicit": [prompt_id]}}

    ranked = []
    for entry in entries:
        score, matched = score_profile(entry, text)
        ranked.append({"entry": entry, "score": score, "matched": matched})
    ranked.sort(key=lambda item: (-item["score"], item["entry"]["id"]))
    first, second = ranked[0], ranked[1]
    if first["score"] < 3 or first["score"] - second["score"] < 2:
        return {
            "status": "needs_input",
            "question": "请确认本次 PPT 的主要场景。",
            "candidates": [
                {"id": item["entry"]["id"], "name": item["entry"]["name_zh"], "score": item["score"]}
                for item in ranked[:2]
            ],
        }
    return {"status": "selected", **first}


def detect_template_intent(
    request_text: str,
    template_paths: list[str],
    *,
    explicit: str | None = None,
) -> dict[str, Any]:
    if explicit:
        if explicit not in TEMPLATE_INTENTS:
            raise PackageError(f"unsupported template intent: {explicit}")
        if explicit != "none" and not template_paths:
            raise PackageError(f"template intent {explicit} requires a PPTX template")
        return {"status": "selected", "intent": explicit, "reason": "explicit"}
    if not template_paths:
        return {"status": "selected", "intent": "none", "reason": "no template supplied"}

    text = request_text.lower()
    reusable = ("可复用模板", "模板工作区", "模板资产包", "以后反复使用")
    reference = ("模板设计元素", "参考模板元素", "参考这个模板", "提炼设计语言", "不要套用", "不套版", "重新设计")
    native = ("套用模板", "沿用原版式", "替换内容", "原版式", "填充模板", "保持模板版式")
    hits = {
        "reusable_template": [term for term in reusable if term in text],
        "reference_elements": [term for term in reference if term in text],
        "native_fill": [term for term in native if term in text],
    }
    active = [intent for intent, terms in hits.items() if terms]
    if len(active) == 1:
        intent = active[0]
        return {"status": "selected", "intent": intent, "reason": ", ".join(hits[intent])}
    return {
        "status": "needs_input",
        "question": "这份 PPTX 是只参考设计元素、保留原版式填充，还是提炼为可复用模板？",
        "candidates": ["reference_elements", "native_fill", "reusable_template"],
    }


def _docx_opening(path: Path, limit: int = 1200) -> str:
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read("word/document.xml"))
        text = "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
        return text[:limit]
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
        return ""


def material_context(paths: list[str]) -> str:
    chunks: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser()
        chunks.append(path.name)
        if not path.is_file():
            continue
        if path.suffix.lower() in {".md", ".txt"}:
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace")[:1200])
            except OSError:
                pass
        elif path.suffix.lower() == ".docx":
            chunks.append(_docx_opening(path))
    return "\n".join(chunks)


def _project_path_from_init(output: str) -> Path:
    for line in output.splitlines():
        if line.startswith("Project created:"):
            return Path(line.split(":", 1)[1].strip()).resolve()
    raise PackageError("ppt-master init did not report a project path")


def _page_count(raw: int | None, request: str) -> int:
    if raw:
        return raw
    match = re.search(r"(\d{1,3})\s*页", request)
    if match:
        return int(match.group(1))
    raise PackageError("page count is required; pass --page-count or include it in the request")


def _imported_template(project: Path, original: str | None) -> str | None:
    if not original:
        return None
    expected = project / "sources" / Path(original).name
    if expected.is_file():
        return str(expected)
    matches = sorted((project / "sources").glob(f"{Path(original).stem}*.pptx"))
    if len(matches) == 1:
        return str(matches[0])
    raise PackageError(f"cannot identify imported template for {original}")


def _write_contract(
    project: Path,
    *,
    entry: dict[str, Any],
    profile_text: str,
    audience: str,
    purpose: str,
    page_count: int,
    template_path: str | None,
    template_intent: str,
) -> Path:
    analysis = project / "analysis"
    analysis.mkdir(exist_ok=True)
    profile_path = analysis / "director_profile.md"
    profile_path.write_text(profile_text, encoding="utf-8")
    contract = {
        "schema_version": "1.0",
        "router_version": ROUTER_VERSION,
        "profile": {
            "id": entry["id"],
            "version": str(entry.get("version") or ROUTER_VERSION),
            "sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            "validation_status": entry.get("validation_status", "experimental"),
        },
        "audience": audience,
        "purpose": purpose,
        "page_count": page_count,
        "template_path": template_path,
        "template_intent": template_intent,
    }
    contract_path = analysis / "director_contract.json"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return contract_path


def execute_route(args: argparse.Namespace) -> dict[str, Any]:
    args.source = [str(Path(path).expanduser().resolve()) for path in args.source]
    args.template = [str(Path(path).expanduser().resolve()) for path in args.template]
    index = load_index(ROOT)
    source_context = material_context([*args.source, *args.template])
    audience = args.audience or ("政府领导" if "领导" in args.request else "未指定受众")
    purpose = args.purpose or args.request
    routing_text = "\n".join([args.request, audience, purpose, source_context])
    routed = route_profile(index, routing_text, prompt_id=args.prompt_id)
    if routed["status"] != "selected":
        return routed
    intent = detect_template_intent(args.request, args.template, explicit=args.template_intent)
    if intent["status"] != "selected":
        return intent
    if len(args.template) > 1:
        raise PackageError("Router 2.1 accepts one primary template per project")

    entry = routed["entry"]
    profile_text = compile_director_profile(ROOT, entry)
    master_skill_dir = receipt_master_skill()
    manager = master_skill_dir / "scripts" / "project_manager.py"
    base = (
        Path(args.project_base).expanduser().resolve()
        if args.project_base
        else (Path.home() / "PPT Director" / "projects").resolve()
    )
    base.mkdir(parents=True, exist_ok=True)
    project_name = args.project_name or f"router_{entry['id']}"
    init_output = run_tool(
        [sys.executable, str(manager), "init", project_name, "--format", args.format, "--dir", str(base)],
        cwd=master_skill_dir.parent,
    )
    project = _project_path_from_init(init_output)

    import_inputs = list(dict.fromkeys([*args.source, *args.template]))
    if import_inputs:
        command = [sys.executable, str(manager), "import-sources", str(project), *import_inputs]
        command.append("--move" if args.move else "--copy")
        run_tool(command, cwd=master_skill_dir.parent)
    template_path = _imported_template(project, args.template[0] if args.template else None)
    contract_path = _write_contract(
        project,
        entry=entry,
        profile_text=profile_text,
        audience=audience,
        purpose=purpose,
        page_count=_page_count(args.page_count, args.request),
        template_path=template_path,
        template_intent=intent["intent"],
    )
    accept_output = run_tool(
        [sys.executable, str(manager), "router-accept", str(project)],
        cwd=master_skill_dir.parent,
    )
    try:
        accepted = json.loads(accept_output[accept_output.index("{"):])
    except (ValueError, json.JSONDecodeError) as exc:
        raise PackageError("ppt-master router-accept did not return a machine receipt") from exc
    if not accepted.get("accepted"):
        raise PackageError("ppt-master did not accept the director handoff")

    if args.director_plan:
        run_tool(
            [sys.executable, str(manager), "director-plan", str(project), args.director_plan],
            cwd=master_skill_dir.parent,
        )
    return {
        "status": "ppt-master-accepted",
        "host": args.host,
        "profile_id": entry["id"],
        "profile_name": entry["name_zh"],
        "profile_validation": entry.get("validation_status", "experimental"),
        "template_intent": intent["intent"],
        "project": str(project),
        "director_contract": str(contract_path),
        "ppt_master": accepted,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PPT Prompt Router 2.1")
    parser.add_argument("--request", required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--template", action="append", default=[])
    parser.add_argument("--template-intent", choices=sorted(TEMPLATE_INTENTS))
    parser.add_argument("--page-count", type=int)
    parser.add_argument("--audience")
    parser.add_argument("--purpose")
    parser.add_argument("--prompt-id")
    parser.add_argument("--format", default="ppt169")
    parser.add_argument("--project-name")
    parser.add_argument("--project-base")
    parser.add_argument("--director-plan")
    parser.add_argument("--host", default="codex", choices=["codex", "hermes", "claude-code", "generic"])
    parser.add_argument("--move", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute_route(build_parser().parse_args(argv))
    except PackageError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("status") == "needs_input" else 0


if __name__ == "__main__":
    raise SystemExit(main())
