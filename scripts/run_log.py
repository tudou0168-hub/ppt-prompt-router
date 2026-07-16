"""Append compact workflow events inside the managed project."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(paths: Iterable[str | Path]) -> list[dict[str, str]]:
    rows = []
    for raw in paths:
        path = Path(raw).expanduser().resolve(strict=False)
        value = sha256(path)
        if value:
            rows.append({"path": str(path), "sha256": value})
    return rows


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def append_event(
    project: str | Path,
    *,
    run_id: str,
    command: str,
    module: str,
    module_file: str | Path,
    inputs: Iterable[str | Path] = (),
    outputs: Iterable[str | Path] = (),
    stage_before: str | None,
    stage_after: str | None,
    exit_code: int | None,
    operation_id: str | None = None,
    error_code: str | None = None,
    event_type: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_seconds: float | None = None,
    mode: str | None = None,
    page_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    root = Path(project).expanduser().resolve()
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    finished = finished_at or datetime.now(timezone.utc).isoformat()
    event = {
        "event_id": run_id,
        "operation_id": operation_id,
        "event_type": event_type or "command_finished",
        "timestamp": finished,
        "started_at": started_at,
        "finished_at": finished,
        "duration_seconds": duration_seconds,
        "run_id": run_id,
        "command": command,
        "module": module,
        "module_file": str(Path(module_file).resolve()),
        "inputs": _files(inputs),
        "outputs": _files(outputs),
        "stage_before": stage_before,
        "stage_after": stage_after,
        "exit_code": exit_code,
        "error_code": error_code,
        "mode": mode,
        "page_id": page_id,
        "token_usage_prompt": None,
        "token_usage_completion": None,
        "token_usage_total": None,
        "token_usage_source": None,
        "success": None if exit_code is None else exit_code == 0,
        "details": details or {},
    }
    events = logs / "events.jsonl"
    with events.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    _write_summary(events, logs / "run_summary.md")


def _write_summary(events: Path, output: Path) -> None:
    rows = []
    for line in events.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    last = rows[-1] if rows else {}
    failures = sum(1 for row in rows if isinstance(row.get("exit_code"), int) and row.get("exit_code") != 0)
    modes = [row.get("mode") for row in rows if row.get("mode")]
    actual_duration = sum(
        float(row.get("duration_seconds") or 0)
        for row in rows
        if ":" not in str(row.get("run_id") or "")
    )
    token_rows = [row for row in rows if row.get("token_usage_total") is not None]
    semantic = [row.get("event_type") for row in rows]
    content = (
        "# PPT Director Run Summary\n\n"
        f"- Events: {len(rows)}\n"
        f"- Failures: {failures}\n"
        f"- Latest command: {last.get('command', 'none')}\n"
        f"- Latest stage: {last.get('stage_after') or last.get('stage_before') or 'unknown'}\n"
        f"- Latest exit code: {last.get('exit_code', 'n/a')}\n"
        f"- Selected mode: {modes[-1] if modes else 'not selected'}\n"
        f"- Actual command duration: {actual_duration:.3f} seconds\n"
        f"- Token usage: {sum(int(row['token_usage_total']) for row in token_rows) if token_rows else 'not captured by current host'}\n"
        f"- Sample rejections: {semantic.count('sample_rejected')}\n"
        f"- Stale artifact events: {semantic.count('artifact_marked_stale')}\n"
    )
    _atomic_text(output, content)
