#!/usr/bin/env python3
"""从干净上游与本地修改版生成最小 PPT Master 覆盖层。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROUTER_OVERLAY_PATHS = (
    "skills/ppt-master/SKILL.md",
    "skills/ppt-master/references/prompt-router-integration.md",
    "skills/ppt-master/references/strategist.md",
    "skills/ppt-master/references/visual-review.md",
    "skills/ppt-master/workflows/visual-review.md",
    "skills/ppt-master/scripts/project_manager.py",
    "skills/ppt-master/scripts/director_plan.py",
    "skills/ppt-master/scripts/production.py",
    "skills/ppt-master/scripts/visual_review.py",
)
FORBIDDEN_MARKERS = ("/" + "Users/", "五" + "寨", "api" + "_key", "app" + "_secret", "tenant" + "_id")
PURPOSES = {
    "skills/ppt-master/SKILL.md": "激活 Router 受控项目的导演规划、逐页生产和导出门禁说明。",
    "skills/ppt-master/references/prompt-router-integration.md": "定义 Router 与 PPT Master 的唯一合同、规划和生产状态边界。",
    "skills/ppt-master/references/strategist.md": "要求 Strategist 读取导演 Profile 并生成唯一 Director Plan。",
    "skills/ppt-master/references/visual-review.md": "复用原生视觉复核规则，并定义受控页面的报告要求。",
    "skills/ppt-master/workflows/visual-review.md": "将既有视觉复核接入 Router 受控项目的逐页流程。",
    "skills/ppt-master/scripts/project_manager.py": "校验 Router 合同并初始化受控生产。",
    "skills/ppt-master/scripts/director_plan.py": "校验唯一 Director Plan、风险样张和页面节奏。",
    "skills/ppt-master/scripts/production.py": "执行逐页 Hash、样张、中途检查、全稿检查和导出放行。",
    "skills/ppt-master/scripts/visual_review.py": "渲染当前受控页面，供既有视觉复核流程使用。",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def ensure_safe(path: Path) -> None:
    if path.suffix.lower() in {".pptx", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".zip", ".mp4", ".mp3"}:
        raise ValueError(f"覆盖层不允许二进制文件：{path}")
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    for marker in FORBIDDEN_MARKERS:
        if marker.lower() in lowered:
            raise ValueError(f"覆盖层包含敏感标记 {marker!r}：{path}")


def sync(upstream_root: Path, modified_root: Path, output: Path, *, tested: bool = False) -> dict:
    if not (modified_root / ".git").exists():
        raise ValueError("modified-root 必须是可识别上游基线的 Git 工作区")
    overlay_root = output / "overlay"
    if overlay_root.exists():
        shutil.rmtree(overlay_root)
    files: list[dict] = []
    for relative in ROUTER_OVERLAY_PATHS:
        upstream = upstream_root / relative
        modified = modified_root / relative
        if not modified.is_file():
            raise ValueError(f"修改版缺少必要文件：{relative}")
        if upstream.is_file() and sha256(upstream) == sha256(modified):
            continue
        ensure_safe(modified)
        target = overlay_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(modified, target)
        files.append({
            "path": relative,
            "action": "modify" if upstream.is_file() else "add",
            "purpose": PURPOSES[relative],
            "upstream_hash": sha256(upstream) if upstream.is_file() else None,
            "overlay_hash": sha256(target),
            "required_by": "Router 2.1 受控生产链路",
            "tested": tested,
        })
    if not files:
        raise ValueError("未发现需要固化的 Router 2.1 覆盖文件")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "1.0", "files": files}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lock = {
        "repository": git_value(modified_root, "remote", "get-url", "origin"),
        "commit": git_value(modified_root, "rev-parse", "HEAD"),
        "version": "未声明",
        "required_capabilities": ["router-accept", "director-plan", "production-control", "visual-review"],
    }
    (output / "upstream.lock").write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"files": files, "upstream": lock}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 PPT Master 最小覆盖层")
    parser.add_argument("--upstream-root", required=True)
    parser.add_argument("--modified-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tested", action="store_true", help="仅在覆盖层已通过真实安装验证后写入")
    args = parser.parse_args()
    result = sync(Path(args.upstream_root), Path(args.modified_root), Path(args.output), tested=args.tested)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
