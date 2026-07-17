"""PPT Director mode, capability, handoff, and context boundary helpers."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


CAPABILITY_STATES = {"available_tool", "available_model_workflow", "degraded", "unavailable"}
QUALITY_LEVELS = {"speed", "balanced", "quality"}
MODES = {"standard", "template", "premium"}
REFERENCE_RE = re.compile(r"(?:\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)|`([^`]+\.(?:md|py))`)")
OperationReporter = Callable[[str, str, list[Path], list[Path], str | None], None]
ROLE_NAMES = {"director", "content_strategist", "template_analyst", "visual_director", "slide_designer", "visual_reviewer"}
ROLE_OUTPUTS = {
    "content_strategist": "analysis/director_plan.json",
    "template_analyst": "analysis/template_profile.json",
    "visual_director": "design_genome.json",
    "slide_designer": ".page_work/current.svg",
    "visual_reviewer": ".review/<active_page>.json",
}
TEMPLATE_PROFILE_FIELDS = {
    "visual_identity", "spatial_grammar", "page_archetypes", "relationship_patterns",
    "image_treatment", "reusable_components", "reference_slides",
}
GENOME_FORBIDDEN_FIELDS = {
    "layout", "grid", "column_count", "card_count", "coordinates", "coordinate",
    "x", "y", "width", "height", "fixed_component", "component", "chart_type",
    "image_position", "image_placement", "relationship_diagram_template",
}


class DirectorRuntimeError(RuntimeError):
    def __init__(self, message: str, *, code: str = "WORKFLOW_BLOCKED", next_actions: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.next_actions = next_actions or []


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def semantic_hash(value: Any) -> str:
    payload = json.dumps(_canonical(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DirectorRuntimeError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DirectorRuntimeError(f"expected JSON object: {path}")
    return value


def load_modes(router_root: str | Path) -> dict[str, Any]:
    path = Path(router_root).resolve() / "runtime" / "config" / "generation_modes.yaml"
    data = _json(path)
    if set((data.get("modes") or {})) != MODES:
        raise DirectorRuntimeError("generation mode configuration must define standard, template, and premium")
    return data


def _modes_hash(router_root: str | Path) -> str:
    return sha256(Path(router_root).resolve() / "runtime" / "config" / "generation_modes.yaml") or "missing"


def _runtime_relative(runtime: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(runtime.resolve()).as_posix()
    except ValueError:
        return path.name


def _resolve_runtime_reference(runtime: Path, owner: Path, raw: str) -> Path | None:
    normalized = raw.strip().replace("\\", "/")
    if not normalized or "://" in normalized or normalized.startswith("#"):
        return None
    if any(token in normalized for token in ("<", ">", " ")) or Path(normalized).name in {"design_spec.md", "spec_lock.md"}:
        return None
    if normalized.startswith("skills/ppt-master/"):
        candidate = runtime / normalized.removeprefix("skills/ppt-master/")
    elif normalized.split("/", 1)[0] in {"scripts", "references", "workflows", "templates", "resources", "modes", "visual-styles"}:
        candidate = runtime / normalized
    elif "/" not in normalized and normalized.endswith(".py"):
        candidate = runtime / "scripts" / normalized
    else:
        candidate = owner.parent / normalized
    try:
        return candidate.resolve() if candidate.resolve().is_relative_to(runtime.resolve()) else None
    except (OSError, ValueError):
        return None


def _python_references(runtime: Path, path: Path) -> list[Path]:
    if path.suffix != ".py":
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []
    references: list[Path] = []
    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.Import):
            module = node.names[0].name if node.names else None
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(max(0, node.level - 1)):
                    base = base.parent
                module_path = Path(*(node.module or "").split(".")) if node.module else Path()
                candidate = (base / module_path).with_suffix(".py")
                if candidate.is_file():
                    references.append(candidate.resolve())
                continue
            module = node.module
        if module:
            candidate = runtime / "scripts" / Path(*module.split(".")).with_suffix(".py")
            if candidate.is_file():
                references.append(candidate.resolve())
    return references


def _reference_closure(runtime: Path, entries: Iterable[Path]) -> list[dict[str, str]]:
    pending = [entry.resolve() for entry in entries if entry.is_file()]
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        try:
            path.relative_to(runtime.resolve())
        except ValueError:
            continue
        visited.add(path)
        body = path.read_text(encoding="utf-8", errors="replace")
        for match in REFERENCE_RE.finditer(body):
            candidate = _resolve_runtime_reference(runtime, path, match.group(1) or match.group(2))
            if candidate and candidate.is_file():
                pending.append(candidate)
        pending.extend(_python_references(runtime, path))
    return [
        {"logical_path": _runtime_relative(runtime, path), "sha256": sha256(path) or "missing"}
        for path in sorted(visited, key=lambda item: _runtime_relative(runtime, item))
    ]


def _runtime_fingerprint(runtime: Path) -> str:
    names = (
        "MASTER.md", "references/strategist.md", "references/executor-base.md",
        "references/shared-standards.md", "references/template-designer.md",
        "workflows/create-template.md", "scripts/project_manager.py",
        "scripts/svg_quality_checker.py", "scripts/visual_review.py",
        "scripts/pptx_intake.py", "scripts/pptx_template_import.py",
        "scripts/svg_authoring_view.py", "scripts/extract_svg_assets.py",
        "scripts/svg_to_pptx/pptx_package/cli.py", "scripts/production.py",
    )
    return semantic_hash(_reference_closure(runtime, [runtime / name for name in names]))


def _dependency_fingerprint() -> str:
    rows = [f"python:{sys.version_info.major}.{sys.version_info.minor}"]
    for module in ("pptx", "xlsxwriter"):
        try:
            imported = __import__(module)
            rows.append(f"{module}:{getattr(imported, '__version__', 'available')}")
        except ImportError:
            rows.append(f"{module}:missing")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _tool(runtime: Path, name: str, relative: str, *, module: str | None = None, entry_kind: str = "cli") -> dict[str, Any]:
    if entry_kind not in {"cli", "library"}:
        raise DirectorRuntimeError(f"unsupported tool entry kind: {entry_kind}")
    path = runtime / relative
    result: dict[str, Any] = {
        "name": name, "status": "unavailable", "execution_type": "tool",
        "entry": str(path), "entry_logical_path": _runtime_relative(runtime, path),
        "entry_sha256": sha256(path), "closure": _reference_closure(runtime, [path]),
        "checks": {}, "error": None,
    }
    if not path.is_file():
        result["error"] = "entry file is missing"
        return result
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        result["checks"]["syntax"] = True
    except (OSError, SyntaxError) as exc:
        result["error"] = f"syntax check failed: {exc}"
        return result
    scripts = runtime / "scripts"
    import_name = module or path.stem
    command = (
        "import importlib,sys;"
        f"sys.path.insert(0,{str(scripts)!r});"
        f"importlib.import_module({import_name!r})"
    )
    imported = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True, timeout=30)
    result["checks"]["import"] = imported.returncode == 0
    if imported.returncode:
        result["error"] = (imported.stderr or imported.stdout).strip()[-1000:]
        return result
    help_command = [sys.executable, "-m", module, "--help"] if module else [sys.executable, str(path), "--help"]
    help_env = os.environ.copy()
    help_env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(scripts), help_env.get("PYTHONPATH"))))
    help_result = subprocess.run(
        help_command,
        cwd=str(scripts),
        env=help_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    result["checks"]["dry_run"] = help_result.returncode == 0
    result["checks"]["output_recognized"] = entry_kind == "library" or "usage:" in (help_result.stdout + help_result.stderr).lower()
    if not all(result["checks"].values()):
        result["status"] = "degraded"
        result["error"] = "help/dry-run contract is incomplete"
        return result
    result["status"] = "available_tool"
    return result


def _workflow(runtime: Path, name: str, entries: list[str], tool_dependencies: list[str], tools: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    paths = [runtime / entry for entry in entries]
    result: dict[str, Any] = {
        "name": name, "status": "unavailable", "execution_type": "model_workflow",
        "verified": False, "entries": [str(path) for path in paths],
        "entry_logical_paths": [_runtime_relative(runtime, path) for path in paths],
        "closure": _reference_closure(runtime, paths), "tool_dependencies": sorted(tool_dependencies),
        "checks": {}, "error": None,
    }
    if not all(path.is_file() and path.stat().st_size > 80 for path in paths):
        result["error"] = "workflow entry or reference is missing/empty"
        return result
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths)
    result["checks"]["responsibility"] = all(keyword.lower() in text.lower() for keyword in keywords)
    broken = []
    for path in paths:
        body = path.read_text(encoding="utf-8", errors="replace")
        for match in REFERENCE_RE.finditer(body):
            raw = match.group(1) or match.group(2)
            candidate = _resolve_runtime_reference(runtime, path, raw)
            if candidate and not candidate.exists():
                broken.append(_runtime_relative(runtime, candidate))
    result["checks"]["references"] = not broken
    missing_tools = [tool for tool in tool_dependencies if (tools.get(tool) or {}).get("status") != "available_tool"]
    result["checks"]["tools"] = not missing_tools
    if all(result["checks"].values()):
        result["status"] = "available_model_workflow"
    elif result["checks"]["responsibility"]:
        result["status"] = "degraded"
        result["error"] = f"broken references={broken[:3]} missing tools={missing_tools}"
    else:
        result["error"] = "workflow does not contain the required responsibility"
    return result


def _phase1_role_capability(
    runtime: Path,
    name: str,
    required_references: list[str],
    tool_dependencies: list[str],
    tools: dict[str, Any],
) -> dict[str, Any]:
    """Validate a Phase-1 role by its actual contract and entrypoints.

    Markdown links outside the declared references remain diagnostic evidence;
    they never decide whether a 4.0 role can perform its defined task.
    """
    paths = [runtime / reference for reference in required_references]
    missing = [_runtime_relative(runtime, path) for path in paths if not path.is_file() or path.stat().st_size == 0]
    broken: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        for match in REFERENCE_RE.finditer(path.read_text(encoding="utf-8", errors="replace")):
            candidate = _resolve_runtime_reference(runtime, path, match.group(1) or match.group(2))
            if candidate and not candidate.exists():
                broken.append(_runtime_relative(runtime, candidate))
    missing_tools = [tool for tool in tool_dependencies if (tools.get(tool) or {}).get("status") != "available_tool"]
    checks = {
        "required_references": not missing,
        "necessary_tools": not missing_tools,
        "diagnostic_references": not broken,
    }
    status = "available_tool" if not missing and not missing_tools else "unavailable"
    return {
        "name": name, "status": status, "execution_type": "controlled_same_session",
        "verified": status == "available_tool", "entry_logical_paths": required_references,
        "closure": _reference_closure(runtime, paths), "tool_dependencies": sorted(tool_dependencies),
        "required_references": required_references, "diagnostic_references": broken,
        "checks": checks,
        "warnings": [f"diagnostic references: {broken}" ] if broken else [],
        "error": None if status == "available_tool" else f"missing required references={missing} tools={missing_tools}",
    }


def _capability_semantic_hash(
    runtime_hash: str,
    dependency_hash: str,
    generation_modes_hash: str,
    capabilities: dict[str, Any],
    modes: dict[str, Any],
) -> str:
    rows = {}
    for name, value in sorted(capabilities.items()):
        rows[name] = {
            "status": value.get("status"), "execution_type": value.get("execution_type"),
            "entry_logical_path": value.get("entry_logical_path"), "entry_sha256": value.get("entry_sha256"),
            "entry_logical_paths": value.get("entry_logical_paths"), "closure": value.get("closure") or [],
            "tool_dependencies": value.get("tool_dependencies") or [],
            "tool_statuses": {
                dependency: (capabilities.get(dependency) or {}).get("status")
                for dependency in sorted(value.get("tool_dependencies") or [])
            },
        }
    return semantic_hash({
        "schema_version": "1.0", "runtime_hash": runtime_hash,
        "dependency_hash": dependency_hash, "generation_modes_hash": generation_modes_hash,
        "capabilities": rows, "modes": {
            name: {"status": value.get("status"), "required_capabilities": sorted(value.get("required_capabilities") or [])}
            for name, value in sorted(modes.items())
        },
    })


def capability_preflight(
    project_path: str | Path,
    runtime_root: str | Path,
    *,
    force: bool = False,
    operation_reporter: OperationReporter | None = None,
) -> dict[str, Any]:
    project, runtime = Path(project_path).resolve(), Path(runtime_root).resolve()
    destination = project / ".director" / "capability_snapshot.json"
    router_root = Path(__file__).resolve().parents[1]
    runtime_hash, dependency_hash, generation_modes_hash = _runtime_fingerprint(runtime), _dependency_fingerprint(), _modes_hash(router_root)
    if destination.is_file() and not force:
        current = _json(destination)
        if (
            current.get("runtime_hash") == runtime_hash
            and current.get("dependency_hash") == dependency_hash
            and current.get("generation_modes_hash") == generation_modes_hash
        ):
            return current
    if operation_reporter:
        operation_reporter("tool_started", "capability_preflight", [], [destination], None)
    try:
        tools = {
            "quality_checker": _tool(runtime, "quality_checker", "scripts/svg_quality_checker.py"),
            "visual_review": _tool(runtime, "visual_review", "scripts/visual_review.py"),
            "exporter": _tool(runtime, "exporter", "scripts/svg_to_pptx/pptx_package/cli.py", module="svg_to_pptx.pptx_package.cli"),
            "pptx_intake": _tool(runtime, "pptx_intake", "scripts/pptx_intake.py"),
            "pptx_template_import": _tool(runtime, "pptx_template_import", "scripts/pptx_template_import.py"),
            "authoring_view": _tool(runtime, "authoring_view", "scripts/svg_authoring_view.py"),
            "vector_extraction": _tool(runtime, "vector_extraction", "scripts/extract_svg_assets.py"),
            "page_gate": _tool(runtime, "page_gate", "scripts/production.py"),
        }
        capabilities: dict[str, Any] = dict(tools)
        capabilities.update({
            "strategist": _workflow(runtime, "strategist", ["MASTER.md", "references/strategist.md"], [], tools, ["strategist", "design_spec"]),
            "executor": _workflow(runtime, "executor", ["MASTER.md", "references/executor-base.md", "references/shared-standards.md"], [], tools, ["svg", "page"]),
            "template_analysis": _workflow(runtime, "template_analysis", ["MASTER.md", "references/strategist.md"], ["pptx_intake"], tools, ["template", "source_profile"]),
            "create_template": _workflow(runtime, "create_template", ["workflows/create-template.md"], ["pptx_template_import", "authoring_view", "vector_extraction"], tools, ["create", "template", "fidelity"]),
            "template_designer": _workflow(runtime, "template_designer", ["references/template-designer.md"], [], tools, ["template", "design"]),
            "fidelity_workflow": _workflow(runtime, "fidelity_workflow", ["workflows/create-template.md", "references/template-designer.md"], ["pptx_template_import", "authoring_view", "vector_extraction"], tools, ["fidelity", "template"]),
            "mirror_workflow": _workflow(runtime, "mirror_workflow", ["workflows/create-template.md", "references/template-designer.md"], ["pptx_template_import", "authoring_view", "vector_extraction"], tools, ["mirror", "restoration", "source"]),
        })
        # Phase-1 exposes a deliberately small capability vocabulary to the
        # router.  These aliases retain the stable Master entrypoints rather
        # than adding another execution system.
        capabilities.update({
            "renderer": capabilities["visual_review"],
            "fact_guard": _tool(runtime, "fact_guard", "scripts/fact_guard.py", entry_kind="library"),
            "template_intake": capabilities["pptx_intake"],
            "template_renderer": capabilities["visual_review"],
            "deep_template": capabilities["fidelity_workflow"],
            "reviewer": capabilities["visual_review"],
        })
        capabilities.update({
            "content_strategist": _phase1_role_capability(runtime, "content_strategist", [
                "references/ppt-director-roles/content_strategist.md", "scripts/director_plan.py",
            ], [], tools),
            "template_analyst": _phase1_role_capability(runtime, "template_analyst", [
                "references/ppt-director-roles/template_analyst.md", "scripts/pptx_intake.py",
            ], ["pptx_intake", "visual_review"], tools),
            "visual_director": _phase1_role_capability(runtime, "visual_director", [
                "references/ppt-director-roles/visual_director.md", "scripts/production.py",
            ], [], tools),
            "slide_designer": _phase1_role_capability(runtime, "slide_designer", [
                "references/executor-base.md", "references/shared-standards.md", "scripts/production.py",
            ], ["quality_checker", "visual_review", "page_gate"], tools),
            "visual_reviewer": _phase1_role_capability(runtime, "visual_reviewer", [
                "references/ppt-director-roles/visual_reviewer.md", "scripts/production.py",
            ], ["visual_review"], tools),
        })
        modes = load_modes(router_root)["modes"]
        mode_status: dict[str, Any] = {}
        for mode_id, config in modes.items():
            rows = [capabilities.get(name, {"status": "unavailable"}) for name in config["required_capabilities"]]
            statuses = [row["status"] for row in rows]
            if any(status == "unavailable" for status in statuses):
                status = "unavailable"
            elif any(status == "degraded" for status in statuses):
                status = "degraded"
            else:
                status = "available_model_workflow"
            mode_status[mode_id] = {
                "status": status,
                "required_capabilities": list(config["required_capabilities"]),
                "missing_or_degraded": [name for name in config["required_capabilities"] if capabilities.get(name, {}).get("status") not in {"available_tool", "available_model_workflow"}],
            }
        compact_capabilities = {
            name: {
                "capability_id": name,
                "status": "available" if value.get("status") in {"available_tool", "available_model_workflow"} else value.get("status"),
                "entry_hash": value.get("entry_sha256") or semantic_hash(value.get("entry_logical_paths") or value.get("entry_logical_path") or name),
                "necessary_dependencies": list(value.get("tool_dependencies") or []),
                "execution_mode": value.get("execution_type") or "tool",
                "checks": value.get("checks") or {},
                "error": value.get("error"),
                "required_references": value.get("required_references") or value.get("entry_logical_paths") or [],
                "diagnostic_references": value.get("diagnostic_references") or [],
                "warnings": value.get("warnings") or [],
            }
            for name, value in capabilities.items()
        }
        snapshot = {
            "schema_version": "1.0", "captured_at": datetime.now(timezone.utc).isoformat(),
            "runtime_root": str(runtime), "runtime_hash": runtime_hash, "dependency_hash": dependency_hash,
            "generation_modes_hash": generation_modes_hash, "capabilities": compact_capabilities, "modes": mode_status,
            "capability_semantic_hash": _capability_semantic_hash(runtime_hash, dependency_hash, generation_modes_hash, capabilities, mode_status),
            "meaning": "Paths and execution contracts are available; task execution is not implied.",
        }
        _atomic_json(destination, snapshot)
    except Exception as exc:
        if operation_reporter:
            operation_reporter("tool_failed", "capability_preflight", [], [destination], str(exc))
        raise
    if operation_reporter:
        operation_reporter("tool_completed", "capability_preflight", [], [destination], None)
    return snapshot


def ensure_capability_snapshot(
    project_path: str | Path,
    runtime_root: str | Path,
    *,
    operation_reporter: OperationReporter | None = None,
) -> tuple[dict[str, Any], bool]:
    project, runtime = Path(project_path).resolve(), Path(runtime_root).resolve()
    path = project / ".director" / "capability_snapshot.json"
    stale = True
    if path.is_file():
        snapshot = _json(path)
        stale = (
            snapshot.get("runtime_hash") != _runtime_fingerprint(runtime)
            or snapshot.get("dependency_hash") != _dependency_fingerprint()
            or snapshot.get("generation_modes_hash") != _modes_hash(Path(__file__).resolve().parents[1])
        )
        if not stale:
            return snapshot, False
    return capability_preflight(project, runtime, force=True, operation_reporter=operation_reporter), True


def _contract(project: Path) -> dict[str, Any]:
    return _json(project / "analysis" / "director_contract.json")


def propose_mode(
    project_path: str | Path,
    router_root: str | Path,
    runtime_root: str | Path,
    *,
    quality_preference: str,
    fidelity_requirement: str | None = None,
    requested_mode: str | None = None,
    operation_reporter: OperationReporter | None = None,
) -> dict[str, Any]:
    if quality_preference not in QUALITY_LEVELS:
        raise DirectorRuntimeError(f"unsupported quality preference: {quality_preference}")
    if requested_mode and requested_mode not in MODES:
        raise DirectorRuntimeError(f"unsupported requested mode: {requested_mode}")
    project = Path(project_path).resolve()
    snapshot, refreshed = ensure_capability_snapshot(project, runtime_root, operation_reporter=operation_reporter)
    contract, configs = _contract(project), load_modes(router_root)["modes"]
    template = (contract.get("template") or {}).get("path")
    if requested_mode:
        recommended, reason = requested_mode, "user requested mode"
    elif not template:
        recommended, reason = "standard", "no reference PPTX"
    elif quality_preference == "speed":
        recommended, reason = "standard", "speed preference"
    elif fidelity_requirement == "mirror":
        recommended, reason = "premium", "explicit mirror restoration request"
    elif quality_preference == "quality" or fidelity_requirement == "high":
        recommended, reason = "premium", "quality or fidelity requirement"
    else:
        recommended, reason = "template", "reference PPTX with balanced quality"
    available = [mode for mode in ("standard", "template", "premium") if snapshot["modes"][mode]["status"] == "available_model_workflow" and (mode == "standard" or template)]
    mirror_available = snapshot["capabilities"]["mirror_workflow"]["status"] == "available"
    if fidelity_requirement == "mirror" and not mirror_available:
        recommended = None
        reason += "; mirror workflow is unavailable"
    if recommended not in available:
        fallback = next((mode for mode in ("template", "standard") if mode in available), None)
        reason += f"; {recommended} unavailable"
        recommended = fallback
    return {
        "available_modes": available, "recommended_mode": recommended,
        "recommendation_reason": reason, "quality_preference": quality_preference,
        "fidelity_requirement": fidelity_requirement, "capability_snapshot": str(project / ".director" / "capability_snapshot.json"),
        "capability_snapshot_refreshed": refreshed,
        "mirror_available": mirror_available,
        "estimated_time_level": configs[recommended]["estimated_time_level"] if recommended else None,
        "estimated_token_level": configs[recommended]["estimated_token_level"] if recommended else None,
        "whether_user_confirmation_required": True,
    }


def _source_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows = contract.get("source_files") or []
    return [row for row in rows if isinstance(row, dict) and row.get("path")]


def _logical_project_path(project: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return path.name


def _source_hashes(project: Path, contract: dict[str, Any]) -> list[dict[str, str | None]]:
    rows = []
    for row in _source_rows(contract):
        path = Path(str(row["path"])).expanduser()
        rows.append({"logical_path": _logical_project_path(project, path), "sha256": sha256(path)})
    return sorted(rows, key=lambda item: (item["logical_path"], item["sha256"] or ""))


def _template_hash(project: Path, contract: dict[str, Any]) -> str | None:
    raw = (contract.get("template") or {}).get("path")
    return sha256(Path(raw).expanduser()) if raw else None


def _mode_semantic_inputs(
    project: Path,
    contract: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    mode: str,
    quality_preference: str,
    fidelity_requirement: str | None,
    replication_mode: str | None,
    sample_strategy: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "runtime_hash": snapshot.get("runtime_hash"),
        "generation_modes_hash": snapshot.get("generation_modes_hash"),
        "capability_semantic_hash": snapshot.get("capability_semantic_hash"),
        "mode": mode,
        "quality_preference": quality_preference,
        "fidelity_requirement": fidelity_requirement,
        "replication_mode": replication_mode,
        "sample_strategy": sample_strategy,
        "source_hashes": _source_hashes(project, contract),
        "template_hash": _template_hash(project, contract),
    }


def current_mode_semantic_hash(project_path: str | Path) -> str:
    project = Path(project_path).resolve()
    selection = require_mode(project)
    contract = _contract(project)
    inputs = dict(selection.get("semantic_inputs") or {})
    if not inputs:
        return selection.get("mode_semantic_hash") or sha256(project / ".director" / "generation_mode.json") or "missing"
    inputs["source_hashes"] = _source_hashes(project, contract)
    inputs["template_hash"] = _template_hash(project, contract)
    return semantic_hash(inputs)


def _handoff(project: Path, contract: dict[str, Any], selection: dict[str, Any]) -> str:
    template = contract.get("template") or {}
    sources = _source_rows(contract)
    source_text = "\n".join(f"- `{row['path']}` sha256=`{row.get('sha256')}`" for row in sources) or "- none"
    references = [row for row in contract.get("reference_files") or [] if isinstance(row, dict) and row.get("path")]
    reference_text = "\n".join(f"- `{row['path']}` sha256=`{row.get('sha256')}`" for row in references) or "- none"
    return f"""# PPT Master Task Handoff

## Original Task

{contract.get('request') or contract.get('purpose') or '未记录'}

## Inputs

- Project: `{project}`
- Audience: {contract.get('audience') or '未指定'}
- Purpose: {contract.get('purpose') or '未指定'}
- Target pages: {contract.get('page_count')}
- Generation mode: {selection['mode']}
- Quality preference: {selection['quality_preference']}
- Reference PPTX: `{template.get('path') or 'none'}`
- Reference SHA256: `{template.get('sha256') or 'none'}`

### Source Documents

{source_text}

### Reference Materials (not factual sources)

{reference_text}

## User Requirements And Fact Boundary

- Preserve the user's original task and explicit constraints.
- Facts must remain traceable to project source Markdown.
- Targets, recommendations, estimates, and assumptions must be labeled.
- Output goal: an editable PPTX suitable for the stated audience and purpose.

## Responsibility Boundary

Director only manages routing, state, logs, gates, evidence and export.
PPT Master owns content interpretation, visual direction, layout decisions and page generation.
"""


def _run_tool(path: Path, arguments: list[str]) -> None:
    result = subprocess.run([sys.executable, str(path), *arguments], capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise DirectorRuntimeError((result.stderr or result.stdout).strip() or f"Master tool failed: {path.name}")


def _prepare_template(
    project: Path,
    runtime: Path,
    mode: str,
    template: Path | None,
    context_rehydrate: Path,
    *,
    operation_reporter: OperationReporter | None = None,
) -> dict[str, Any]:
    def invoke(name: str, path: Path, arguments: list[str], outputs: list[Path]) -> None:
        if operation_reporter:
            operation_reporter("tool_started", name, [path, *[Path(arg) for arg in arguments if Path(arg).exists()]], outputs, None)
        try:
            _run_tool(path, arguments)
        except Exception as exc:
            if operation_reporter:
                operation_reporter("tool_failed", name, [path], outputs, str(exc))
            raise
        if operation_reporter:
            operation_reporter("tool_completed", name, [path], outputs, None)

    if mode == "standard" or template is None:
        return {"status": "not_required", "outputs": []}
    if mode == "template":
        output = project / "analysis" / "template_intake"
        invoke("pptx_intake", runtime / "scripts" / "pptx_intake.py", [str(template), "-o", str(output)], [output])
        outputs = sorted(str(path) for path in output.glob("*.json"))
        workflow = runtime / "references" / "strategist.md"
        workflow_context = [project / ".director" / "master_handoff.md", context_rehydrate, workflow]
        if operation_reporter:
            operation_reporter("model_workflow_context_issued", "template_analysis", workflow_context, [output / "summary.md"], None)
        return {"status": "native_analysis_ready", "outputs": outputs, "required_context": [str(path) for path in workflow_context]}
    output = project / "analysis" / "deep_template"
    invoke("pptx_template_import", runtime / "scripts" / "pptx_template_import.py", [str(template), "-o", str(output)], [output])
    for source_name, target_name, prefix in (("svg", "authoring-svg", "layered"), ("svg-flat", "authoring-svg-flat", "flat")):
        source = output / source_name
        if not source.is_dir():
            continue
        target = output / target_name
        invoke(f"authoring_view:{source_name}", runtime / "scripts" / "svg_authoring_view.py", [str(source), "-o", str(target)], [target])
        invoke(f"vector_extraction:{source_name}", runtime / "scripts" / "extract_svg_assets.py", [str(target), "--icons-dir", str(output / "icons"), "--inplace", "--id-prefix", prefix, "--min-decoration-bytes", "3000", "--clean-stale"], [output / "icons"])
    workflow = runtime / "workflows" / "create-template.md"
    workflow_context = [project / ".director" / "master_handoff.md", context_rehydrate, workflow]
    expected_outputs = [output / "source_profile.json", output / "summary.md", output / "native_structure.json"]
    if operation_reporter:
        operation_reporter("model_workflow_context_issued", "premium_template_design", workflow_context, expected_outputs, None)
    return {
        "status": "deterministic_tools_complete", "outputs": [str(output / name) for name in ("manifest.json", "native_structure.json", "summary.md") if (output / name).exists()],
        "required_context": [str(path) for path in workflow_context],
        "expected_outputs": [str(path) for path in expected_outputs],
    }


def refresh_template_analysis(
    project_path: str | Path,
    runtime_root: str | Path,
    *,
    operation_reporter: OperationReporter | None = None,
) -> dict[str, Any]:
    project, runtime = Path(project_path).resolve(), Path(runtime_root).resolve()
    selection = require_mode(project)
    contract = _contract(project)
    template_raw = (contract.get("template") or {}).get("path")
    if selection["mode"] == "standard" or not template_raw:
        raise DirectorRuntimeError("template analysis refresh requires template or premium mode")
    context = refresh_context(project, command="template-analysis-redo", runtime_root=runtime)
    return _prepare_template(
        project,
        runtime,
        selection["mode"],
        Path(str(template_raw)).expanduser(),
        Path(context["path"]),
        operation_reporter=operation_reporter,
    )


def select_mode(
    project_path: str | Path,
    router_root: str | Path,
    runtime_root: str | Path,
    *,
    mode: str,
    quality_preference: str,
    fidelity_requirement: str | None = None,
    operation_reporter: OperationReporter | None = None,
) -> dict[str, Any]:
    project, runtime = Path(project_path).resolve(), Path(runtime_root).resolve()
    proposal = propose_mode(project, router_root, runtime, quality_preference=quality_preference, fidelity_requirement=fidelity_requirement, operation_reporter=operation_reporter)
    selected = proposal["recommended_mode"] if mode == "auto" else mode
    if selected not in MODES:
        raise DirectorRuntimeError(f"unsupported mode: {selected}")
    if selected not in proposal["available_modes"]:
        status = _json(project / ".director" / "capability_snapshot.json")["modes"][selected]
        raise DirectorRuntimeError(f"mode {selected} is not selectable: {status}", next_actions=["mode-propose"])
    if fidelity_requirement == "mirror" and (selected != "premium" or not proposal["mirror_available"]):
        raise DirectorRuntimeError("mirror requires an explicit premium selection and a complete mirror workflow", next_actions=["mode-propose"])
    contract = _contract(project)
    template_raw = (contract.get("template") or {}).get("path")
    if selected != "standard" and not template_raw:
        raise DirectorRuntimeError(f"mode {selected} requires a reference PPTX")
    snapshot_path = project / ".director" / "capability_snapshot.json"
    snapshot = _json(snapshot_path)
    config = load_modes(router_root)["modes"][selected]
    replication_mode = "mirror" if fidelity_requirement == "mirror" else ("fidelity" if selected == "premium" else None)
    semantic_inputs = _mode_semantic_inputs(
        project,
        contract,
        snapshot,
        mode=selected,
        quality_preference=quality_preference,
        fidelity_requirement=fidelity_requirement,
        replication_mode=replication_mode,
        sample_strategy=config["sample_strategy"],
    )
    selection = {
        "schema_version": "1.0", "mode": selected, "selected_by": "auto" if mode == "auto" else "manual",
        "recommendation_reason": proposal["recommendation_reason"], "quality_preference": quality_preference,
        "fidelity_requirement": fidelity_requirement, "template_analysis_level": config["template_analysis_level"],
        "replication_mode": replication_mode,
        "sample_strategy": config["sample_strategy"], "estimated_time_level": config["estimated_time_level"],
        "estimated_token_level": config["estimated_token_level"], "selected_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": semantic_inputs["source_hashes"], "template_hash": semantic_inputs["template_hash"],
        "capability_snapshot_hash": sha256(snapshot_path), "capability_semantic_hash": snapshot.get("capability_semantic_hash"),
        "semantic_inputs": semantic_inputs, "mode_semantic_hash": semantic_hash(semantic_inputs),
    }
    mode_path, handoff_path = project / ".director" / "generation_mode.json", project / ".director" / "master_handoff.md"
    _atomic_json(mode_path, selection)
    _atomic_text(handoff_path, _handoff(project, contract, selection))
    context = refresh_context(project, command="template-analysis", router_root=router_root, runtime_root=runtime)
    template_result = _prepare_template(
        project,
        runtime,
        selected,
        Path(template_raw) if template_raw else None,
        Path(context["path"]),
        operation_reporter=operation_reporter,
    )
    return {
        "mode": selected, "generation_mode": str(mode_path), "master_handoff": str(handoff_path),
        "context_rehydrate": context, "template_processing": template_result, "stage": "director_pending", "next_allowed_actions": ["plan"],
    }


def require_mode(project_path: str | Path) -> dict[str, Any]:
    path = Path(project_path).resolve() / ".director" / "generation_mode.json"
    if not path.is_file():
        raise DirectorRuntimeError("generation mode must be selected before planning", next_actions=["mode-propose", "mode-select"])
    return _json(path)


def _context_path(project: Path, role: str) -> Path:
    return project / ".director" / "context" / "current" / f"{role}.json"


def _context_entry(project: Path, path: Path, *, kind: str, excerpt: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"kind": kind, "path": _logical_project_path(project, path), "sha256": sha256(path)}
    if excerpt is not None:
        entry["excerpt"] = excerpt
    return entry


def _template_analysis_files(project: Path, mode: str) -> list[Path]:
    root = project / "analysis" / ("deep_template" if mode == "premium" else "template_intake")
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.is_dir() else []


def _load_plan_if_present(project: Path) -> dict[str, Any] | None:
    path = project / "analysis" / "director_plan.json"
    if not path.is_file():
        return None
    from director_plan import load_plan
    return load_plan(project)


def _page_expression_task(plan: dict[str, Any] | None, page_id: str) -> str:
    if not plan:
        return "non_probe"
    mapping = ("information_density", "complex_relationship", "visual_signature")
    for index, sample in enumerate(plan.get("sample_pages") or []):
        if sample.get("page_id") == page_id:
            raw = str(sample.get("expression_task") or sample.get("risk_type") or sample.get("sample_role") or "").strip()
            return raw if raw in mapping else mapping[index] if index < len(mapping) else "non_probe"
    return "non_probe"


def semantic_plan_hashes(project_path: str | Path) -> dict[str, Any]:
    """Return the phase-1 deck and page semantic hashes; never use plan bytes as authority."""
    project = Path(project_path).resolve()
    plan = _load_plan_if_present(project)
    if not plan:
        return {"deck_plan_hash": None, "page_semantic_hashes": {}}
    contract = _contract(project)
    pages = list(plan.get("pages") or [])
    deck = {
        "audience": contract.get("audience"), "purpose": contract.get("purpose"),
        "core_viewpoint": (plan.get("content_map") or {}).get("core_argument"),
        "storyline": plan.get("storyline"),
        "page_count": len(pages), "page_order": [page.get("page_id") for page in pages],
        "fact_boundary": plan.get("fact_boundary"),
    }
    hashes = {}
    for page in pages:
        page_id = str(page.get("page_id"))
        payload = {key: page.get(key) for key in (
            "page_id", "page_role", "page_intent", "required_messages", "source_refs", "factual_constraints",
        )}
        payload["expression_task"] = _page_expression_task(plan, page_id)
        hashes[page_id] = semantic_hash(payload)
    return {"deck_plan_hash": semantic_hash(deck), "page_semantic_hashes": hashes}


def validate_template_profile(project_path: str | Path, candidate: str | Path) -> dict[str, Any]:
    project, path = Path(project_path).resolve(), Path(candidate).resolve()
    value = _json(path)
    missing = sorted(TEMPLATE_PROFILE_FIELDS - set(value))
    if missing:
        raise DirectorRuntimeError(f"template_profile.json missing fields: {', '.join(missing)}")
    slides = value.get("reference_slides")
    if not isinstance(slides, list) or not slides:
        raise DirectorRuntimeError("template_profile.reference_slides must be a non-empty list")
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            raise DirectorRuntimeError(f"reference_slides[{index}] must be an object")
        raw = slide.get("path") or slide.get("artifact_path")
        if not isinstance(raw, str) or not raw.strip():
            raise DirectorRuntimeError(f"reference_slides[{index}] must reference a real artifact path")
        artifact = (project / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            artifact.relative_to(project)
        except ValueError as exc:
            raise DirectorRuntimeError("template reference slide must be inside the project") from exc
        if not artifact.is_file() or not sha256(artifact):
            raise DirectorRuntimeError(f"template reference slide is missing: {raw}")
        declared = slide.get("sha256")
        if declared and declared != sha256(artifact):
            raise DirectorRuntimeError(f"template reference slide hash is stale: {raw}")
    return value


def _contains_forbidden_genome_field(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in GENOME_FORBIDDEN_FIELDS or normalized.endswith("_coordinates"):
                return str(key)
            found = _contains_forbidden_genome_field(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _contains_forbidden_genome_field(child)
            if found:
                return found
    return None


def validate_design_genome(project_path: str | Path, candidate: str | Path) -> dict[str, Any]:
    project, path = Path(project_path).resolve(), Path(candidate).resolve()
    value = _json(path)
    required = {"visual_direction", "template_inheritance", "color_system", "font_system", "canvas", "safe_margins", "information_hierarchy", "image_strategy", "relationship_principles", "page_rhythm", "design_probes", "page_visual_tasks"}
    missing = sorted(required - set(value))
    if missing:
        raise DirectorRuntimeError(f"design_genome.json missing fields: {', '.join(missing)}")
    forbidden = _contains_forbidden_genome_field(value)
    if forbidden:
        raise DirectorRuntimeError(f"design_genome.json contains forbidden fixed layout field: {forbidden}")
    plan = _load_plan_if_present(project)
    probes = value.get("design_probes")
    if not isinstance(probes, list) or len(probes) != 3:
        raise DirectorRuntimeError("design_genome.design_probes must contain exactly three probes")
    ids = [str(item.get("page_id")) for item in probes if isinstance(item, dict)]
    tasks = [str(item.get("expression_task")) for item in probes if isinstance(item, dict)]
    allowed = {page["page_id"] for page in (plan or {}).get("pages", [])}
    if len(ids) != 3 or len(set(ids)) != 3 or not set(ids).issubset(allowed):
        raise DirectorRuntimeError("design_genome probes must use three unique Director Plan page ids")
    if set(tasks) != {"information_density", "complex_relationship", "visual_signature"}:
        raise DirectorRuntimeError("design_genome probes must cover the three required expression tasks")
    return value


def compile_design_spec(project_path: str | Path) -> dict[str, Any]:
    project = Path(project_path).resolve()
    genome_path = project / "design_genome.json"
    genome = validate_design_genome(project, genome_path)
    contract = _contract(project)
    mode = require_mode(project).get("mode")
    profile_path = project / "analysis" / "template_profile.json"
    if mode in {"template", "premium"}:
        validate_template_profile(project, profile_path)
    genome_hash = sha256(genome_path)
    body = ["# Design Spec", "", f"design_genome_sha256: {genome_hash}", "", "## Visual Direction", "", str(genome["visual_direction"]), "", "## Template Inheritance", "", str(genome["template_inheritance"]), "", "## Page Rhythm", "", json.dumps(genome["page_rhythm"], ensure_ascii=False, indent=2), "", "## Page Visual Tasks", "", json.dumps(genome["page_visual_tasks"], ensure_ascii=False, indent=2), ""]
    lock = ["# Spec Lock", "", f"design_genome_sha256: {genome_hash}", f"canvas: {json.dumps(genome['canvas'], ensure_ascii=False)}", f"safe_margins: {json.dumps(genome['safe_margins'], ensure_ascii=False)}", f"color_system: {json.dumps(genome['color_system'], ensure_ascii=False)}", f"font_system: {json.dumps(genome['font_system'], ensure_ascii=False)}"]
    minimum = (20, 16, 12) if str((contract.get("profile") or {}).get("id")) in {"government_strategy", "decision_meeting"} else (18, 16, 12)
    lock.extend([f"minimum_font_sizes: body={minimum[0]}px supporting={minimum[1]}px footnote={minimum[2]}px", "", "## Image Strategy", "", str(genome["image_strategy"]), "", "## Relationship Principles", "", str(genome["relationship_principles"]), ""])
    _atomic_text(project / "design_spec.md", "\n".join(body))
    _atomic_text(project / "spec_lock.md", "\n".join(lock))
    return {"design_genome": str(genome_path), "design_genome_hash": genome_hash, "design_spec": str(project / "design_spec.md"), "spec_lock": str(project / "spec_lock.md")}


def _role_contract(runtime: Path, role: str) -> Path | None:
    candidate = runtime / "references" / "ppt-director-roles" / f"{role}.md"
    return candidate if candidate.is_file() else None


def assemble_role_context(project_path: str | Path, *, role: str, page: dict[str, Any] | None = None, previous_page: str | None = None, router_root: str | Path | None = None, runtime_root: str | Path | None = None, feedback: str | None = None) -> dict[str, Any]:
    if role not in ROLE_NAMES:
        raise DirectorRuntimeError(f"unsupported role: {role}")
    project = Path(project_path).resolve()
    runtime = Path(runtime_root).resolve() if runtime_root else Path(__file__).resolve().parents[1] / "runtime" / "ppt-master"
    contract, mode = _contract(project), require_mode(project)
    plan = _load_plan_if_present(project)
    inputs: list[dict[str, Any]] = []
    role_contract = _role_contract(runtime, role)
    if role_contract:
        inputs.append(_context_entry(project, role_contract, kind="role_contract"))
    if role == "content_strategist":
        profile = project / "analysis" / "director_profile.md"
        inputs.append(_context_entry(project, profile, kind="matched_profile"))
        for row in _source_rows(contract):
            inputs.append(_context_entry(project, Path(str(row["path"])), kind="source_material"))
    elif role == "template_analyst":
        raw = (contract.get("template") or {}).get("path")
        if not raw:
            raise DirectorRuntimeError("template analyst requires a template")
        inputs.append(_context_entry(project, Path(str(raw)), kind="template"))
        for artifact in _template_analysis_files(project, mode["mode"]):
            inputs.append(_context_entry(project, artifact, kind="template_render" if artifact.suffix.lower() in {".png", ".svg"} else "template_analysis"))
    elif role == "visual_director":
        if not plan:
            raise DirectorRuntimeError("visual director requires an approved Director Plan")
        state_path = project / "analysis" / "production_state.json"
        state = _json(state_path) if state_path.is_file() else {}
        if ((state.get("samples") or {}).get("phase1") and
                ((state.get("samples") or {}).get("confirmations") or {}).get("brief") != "approved"):
            raise DirectorRuntimeError("visual director requires brief approval")
        inputs.append(_context_entry(project, project / "analysis" / "director_plan.json", kind="director_plan"))
        profile = project / "analysis" / "template_profile.json"
        if profile.is_file():
            inputs.append(_context_entry(project, profile, kind="template_profile"))
        elif mode["mode"] in {"template", "premium"}:
            raise DirectorRuntimeError("template mode requires a valid Template Profile")
    elif role == "slide_designer":
        if not page:
            raise DirectorRuntimeError("slide designer requires a current page")
        from director_plan import resolve_evidence_ref
        excerpts = [resolve_evidence_ref(project, ref) for ref in page.get("source_refs") or []]
        inputs.append({"kind": "current_page", "page": page, "source_excerpts": excerpts})
        genome = project / "design_genome.json"
        inputs.append(_context_entry(project, genome, kind="design_genome"))
        previous = project / ".preview" / f"{previous_page}.png" if previous_page else None
        if previous and previous.is_file():
            inputs.append(_context_entry(project, previous, kind="previous_page_png"))
        if feedback:
            inputs.append({"kind": "revision_feedback", "text": feedback})
        executor = runtime / "references" / "executor-base.md"
        inputs.append(_context_entry(project, executor, kind="executor_standard"))
    elif role == "visual_reviewer":
        if not page:
            raise DirectorRuntimeError("visual reviewer requires a current page")
        png = project / ".preview" / f"{page['page_id']}.png"
        inputs.append(_context_entry(project, png, kind="latest_png"))
        inputs.append({"kind": "current_page_semantics", "page_id": page["page_id"], "page_intent": page.get("page_intent"), "required_messages": page.get("required_messages"), "factual_constraints": page.get("factual_constraints")})
        inputs.append(_context_entry(project, project / "design_genome.json", kind="design_genome"))
        if plan:
            ordered = [item["page_id"] for item in plan.get("pages") or []]
            index = ordered.index(page["page_id"]) if page["page_id"] in ordered else -1
            for neighbor_id in ordered[max(0, index - 1): index + 2]:
                neighbor = project / ".preview" / f"{neighbor_id}.png"
                if neighbor.is_file() and neighbor != png:
                    inputs.append(_context_entry(project, neighbor, kind="adjacent_page_png"))
    else:
        inputs.append({"kind": "task_summary", "request": contract.get("request"), "audience": contract.get("audience"), "purpose": contract.get("purpose")})
    payload = {"schema_version": "4.0-phase1", "role": role, "execution_mode": "controlled_same_session", "mode": mode["mode"], "inputs": inputs, "allowed_output": ROLE_OUTPUTS.get(role), "forbidden": ["logs", "production_state", "capability_snapshot", "full_master", "unrelated_svg", "builder_reasoning"]}
    payload["context_hash"] = semantic_hash(payload)
    destination = _context_path(project, role)
    _atomic_json(destination, payload)
    snapshot_root = os.environ.get("PPT_DIRECTOR_CONTEXT_SNAPSHOT_DIR")
    if snapshot_root:
        target = Path(snapshot_root).expanduser().resolve() / project.name / role / f"{payload['context_hash']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, target)
    return {"path": str(destination), "sha256": sha256(destination), "role": role, "context_hash": payload["context_hash"], "semantic_dependency_hash": payload["context_hash"], "input_hashes": [item.get("sha256") for item in inputs if isinstance(item, dict) and item.get("sha256")]}


def submit_role_artifact(project_path: str | Path, *, role: str, artifact: str | Path) -> dict[str, Any]:
    project, source = Path(project_path).resolve(), Path(artifact).resolve()
    if role not in ROLE_OUTPUTS:
        raise DirectorRuntimeError(f"role {role} cannot submit artifacts")
    if not source.is_file():
        raise DirectorRuntimeError(f"artifact does not exist: {source}")
    if role == "content_strategist":
        from director_plan import validate_director_plan
        value = _json(source); validate_director_plan(project, value); destination = project / "analysis" / "director_plan.json"
    elif role == "template_analyst":
        validate_template_profile(project, source); destination = project / "analysis" / "template_profile.json"
    elif role == "visual_director":
        validate_design_genome(project, source); destination = project / "design_genome.json"
    elif role == "slide_designer":
        destination = project / ".page_work" / "current.svg"
    else:
        destination = project / ".review" / f"{source.stem}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source != destination:
        shutil.copy2(source, destination)
    return {"role": role, "artifact": str(destination), "sha256": sha256(destination)}


def refresh_context(
    project_path: str | Path,
    *,
    command: str,
    role: str | None = None,
    page: dict[str, Any] | None = None,
    previous_page: str | None = None,
    router_root: str | Path | None = None,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    role_for_command = {
        "director-plan": "content_strategist",
        "template-analysis": "template_analyst",
        "template-analysis-redo": "template_analyst",
        "design-spec": "visual_director",
        "page-begin": "slide_designer",
        "page-review": "visual_reviewer",
    }.get(command)
    if role or role_for_command:
        return assemble_role_context(
            project_path,
            role=role or role_for_command or "director",
            page=page,
            previous_page=previous_page,
            router_root=router_root,
            runtime_root=runtime_root,
        )
    project = Path(project_path).resolve()
    router = Path(router_root).resolve() if router_root else Path(__file__).resolve().parents[1]
    runtime = Path(runtime_root).resolve() if runtime_root else router / "runtime" / "ppt-master"
    mode = require_mode(project)
    contract = _contract(project)

    def logical_path(path: Path) -> str:
        try:
            return path.resolve().relative_to(project).as_posix()
        except ValueError:
            try:
                return f"runtime/ppt-master/{path.resolve().relative_to(runtime).as_posix()}"
            except ValueError:
                try:
                    return f"router/{path.resolve().relative_to(router).as_posix()}"
                except ValueError:
                    return path.name

    required: list[dict[str, str]] = []

    def add(role: str, path: Path) -> None:
        if path.is_file():
            required.append({"role": role, "logical_path": logical_path(path), "sha256": sha256(path) or "missing"})

    for role, path in (
        ("director_profile", project / "analysis" / "director_profile.md"),
        ("director_plan", project / "analysis" / "director_plan.json"),
        ("design_spec", project / "design_spec.md"),
        ("spec_lock", project / "spec_lock.md"),
        ("master_handoff", project / ".director" / "master_handoff.md"),
        ("generation_mode", project / ".director" / "generation_mode.json"),
        ("capability_snapshot", project / ".director" / "capability_snapshot.json"),
        ("selected_sample", project / ".director" / "selected_sample.json"),
        ("production_state", project / "analysis" / "production_state.json"),
    ):
        add(role, path)
    for row in _source_rows(contract):
        add("source", Path(str(row["path"])).expanduser())
    for row in contract.get("reference_files") or []:
        if isinstance(row, dict) and row.get("path"):
            add("reference_material", Path(str(row["path"])).expanduser())
    template = (contract.get("template") or {}).get("path")
    if template:
        add("reference_pptx", Path(str(template)).expanduser())
    analysis_dir = project / "analysis" / ("deep_template" if mode["mode"] == "premium" else "template_intake")
    if mode["mode"] != "standard":
        for output in sorted(path for path in analysis_dir.rglob("*") if path.is_file()):
            add("template_analysis", output)
    feedback = project / ".director" / "sample_feedback.md"
    add("sample_feedback", feedback)

    previous_artifacts: list[dict[str, str | None]] = []
    if previous_page:
        previous_png = project / ".preview" / f"{previous_page}.png"
        add("previous_page_png", previous_png)
        previous_artifacts.append({
            "page_id": previous_page,
            "svg_hash": sha256(project / "svg_output" / f"{previous_page}.svg"),
            "png_hash": sha256(project / ".preview" / f"{previous_page}.png"),
            "review_hash": sha256(project / ".review" / f"{previous_page}.json"),
        })
    required.sort(key=lambda item: (item["role"], item["logical_path"]))
    production_state_path = project / "analysis" / "production_state.json"
    production_state = _json(production_state_path) if production_state_path.is_file() else {}
    confirmations = _canonical((production_state.get("samples") or {}).get("confirmations") or {})
    context_payload = {
        "schema_version": "1.0", "command": command, "mode": mode["mode"],
        "page_id": (page or {}).get("page_id"),
        "mode_semantic_hash": current_mode_semantic_hash(project),
        "required_context": required, "current_page": page or {},
        "previous_artifacts": previous_artifacts,
        "confirmations": confirmations,
        "sample_feedback_hash": sha256(feedback) if feedback.is_file() else None,
    }
    context_payload["semantic_dependency_hash"] = semantic_hash(context_payload)
    lines = [
        "# PPT Master Context Rehydrate", "",
        f"schema_version: {context_payload['schema_version']}",
        f"command: {command}",
        f"mode: {mode['mode']}",
        f"page_id: {context_payload['page_id'] or 'none'}",
        f"semantic_dependency_hash: {context_payload['semantic_dependency_hash']}",
        "", "## required_context", "",
        "| role | logical_path | sha256 |", "| --- | --- | --- |",
    ]
    lines.extend(f"| {row['role']} | `{row['logical_path']}` | `{row['sha256']}` |" for row in required)
    lines.extend(["", "## confirmations", "", "```json", json.dumps(confirmations, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## current_page", "", "```json", json.dumps(_canonical(page or {}), ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## previous_artifacts", "", "```json", json.dumps(previous_artifacts, ensure_ascii=False, indent=2), "```"])
    if context_payload["sample_feedback_hash"]:
        lines.extend(["", "sample_feedback_hash: " + str(context_payload["sample_feedback_hash"])])
    destination = project / ".director" / "context_rehydrate.md"
    _atomic_text(destination, "\n".join(lines) + "\n")
    return {
        "path": str(destination), "sha256": sha256(destination), "mode": mode["mode"],
        "semantic_dependency_hash": context_payload["semantic_dependency_hash"],
    }
