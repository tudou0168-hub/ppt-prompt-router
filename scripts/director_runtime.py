"""PPT Director mode, capability, handoff, and context boundary helpers."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
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


def _tool(runtime: Path, name: str, relative: str, *, module: str | None = None) -> dict[str, Any]:
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
    result["checks"]["output_recognized"] = "usage:" in (help_result.stdout + help_result.stderr).lower()
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
        snapshot = {
            "schema_version": "1.0", "captured_at": datetime.now(timezone.utc).isoformat(),
            "runtime_root": str(runtime), "runtime_hash": runtime_hash, "dependency_hash": dependency_hash,
            "generation_modes_hash": generation_modes_hash, "capabilities": capabilities, "modes": mode_status,
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
    mirror_available = snapshot["capabilities"]["mirror_workflow"]["status"] == "available_model_workflow"
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
        return {"status": "complete", "outputs": outputs}
    output = project / "analysis" / "deep_template"
    invoke("pptx_template_import", runtime / "scripts" / "pptx_template_import.py", [str(template), "-o", str(output)], [output])
    for source_name, target_name, prefix in (("svg", "authoring-svg", "layered"), ("svg-flat", "authoring-svg-flat", "flat")):
        source = output / source_name
        if not source.is_dir():
            continue
        target = output / target_name
        invoke(f"authoring_view:{source_name}", runtime / "scripts" / "svg_authoring_view.py", [str(source), "-o", str(target)], [target])
        invoke(f"vector_extraction:{source_name}", runtime / "scripts" / "extract_svg_assets.py", [str(target), "--icons-dir", str(output / "icons"), "--inplace", "--id-prefix", prefix, "--min-decoration-bytes", "3000", "--clean-stale"], [output / "icons"])
    workflow_context = [runtime / "workflows" / "create-template.md", runtime / "references" / "template-designer.md"]
    expected_outputs = [project / "design_spec.md", project / "spec_lock.md"]
    if operation_reporter:
        operation_reporter("model_workflow_context_issued", "premium_template_design", workflow_context, expected_outputs, None)
    return {
        "status": "deterministic_tools_complete", "outputs": [str(output / name) for name in ("manifest.json", "native_structure.json", "summary.md") if (output / name).exists()],
        "required_context": [str(path) for path in workflow_context],
        "expected_outputs": [str(path) for path in expected_outputs],
    }


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
    template_result = _prepare_template(project, runtime, selected, Path(template_raw) if template_raw else None, operation_reporter=operation_reporter)
    return {
        "mode": selected, "generation_mode": str(mode_path), "master_handoff": str(handoff_path),
        "template_processing": template_result, "stage": "director_pending", "next_allowed_actions": ["plan"],
    }


def require_mode(project_path: str | Path) -> dict[str, Any]:
    path = Path(project_path).resolve() / ".director" / "generation_mode.json"
    if not path.is_file():
        raise DirectorRuntimeError("generation mode must be selected before planning", next_actions=["mode-propose", "mode-select"])
    return _json(path)


def refresh_context(
    project_path: str | Path,
    *,
    command: str,
    page: dict[str, Any] | None = None,
    previous_page: str | None = None,
    router_root: str | Path | None = None,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
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
        ("master", runtime / "MASTER.md"),
        ("strategist", runtime / "references" / "strategist.md"),
        ("executor", runtime / "references" / "executor-base.md"),
        ("shared_standards", runtime / "references" / "shared-standards.md"),
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
    template = (contract.get("template") or {}).get("path")
    if template:
        add("reference_pptx", Path(str(template)).expanduser())
    analysis_dir = project / "analysis" / ("deep_template" if mode["mode"] == "premium" else "template_intake")
    if mode["mode"] != "standard":
        for output in sorted(analysis_dir.rglob("*.json")):
            add("template_analysis", output)
    required.sort(key=lambda item: (item["role"], item["logical_path"]))

    previous_artifacts: list[dict[str, str | None]] = []
    if previous_page:
        previous_artifacts.append({
            "page_id": previous_page,
            "svg_hash": sha256(project / "svg_output" / f"{previous_page}.svg"),
            "png_hash": sha256(project / ".preview" / f"{previous_page}.png"),
            "review_hash": sha256(project / ".review" / f"{previous_page}.json"),
        })
    feedback = project / ".director" / "sample_feedback.md"
    context_payload = {
        "schema_version": "1.0", "command": command, "mode": mode["mode"],
        "page_id": (page or {}).get("page_id"),
        "mode_semantic_hash": current_mode_semantic_hash(project),
        "required_context": required, "current_page": page or {},
        "previous_artifacts": previous_artifacts,
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
