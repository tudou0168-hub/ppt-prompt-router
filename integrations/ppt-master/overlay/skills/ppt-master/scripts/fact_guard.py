"""Source-bound hard-fact checks for SVG text and speaker notes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


QUALIFIERS = ("[建议]", "[目标]", "[假设]", "[预计]", "[测算]", "[规划]", "拟", "计划", "预计", "力争", "建议", "待确认")
NUMBER_RE = re.compile(r"(?<![A-Za-z])(?:19|20)\d{2}年?|\d+(?:\.\d+)?(?:%|％|万元|亿元|元|万|亿|年|月|日|项|个|家|次|倍)")
ORG_RE = re.compile(r"[\u4e00-\u9fff]{2,20}(?:人民政府|政府|委员会|办公室|管理局|服务中心|中心|公司|集团)")
RESPONSIBILITY_RE = re.compile(r"(?:由|责任单位[:：]?|牵头单位[:：]?)([\u4e00-\u9fff]{2,24})(?:负责|牵头|承办|实施)")
CASE_EFFECT_RE = re.compile(r"(?:案例|实践|试点)[^。；\n]{0,40}(?:提升|下降|减少|增长|节省|覆盖)[^。；\n]{0,30}")


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _hidden(element: ET.Element, inherited: bool) -> bool:
    style = element.get("style", "").replace(" ", "").lower()
    return inherited or element.get("display") == "none" or element.get("visibility") == "hidden" or element.get("opacity") == "0" or "display:none" in style or "visibility:hidden" in style or "opacity:0" in style


def _svg_blocks(path: Path) -> list[str]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    blocks: list[str] = []

    def walk(element: ET.Element, hidden: bool, excluded: bool) -> None:
        local = _local(element)
        excluded = excluded or local in {"defs", "metadata"}
        hidden = _hidden(element, hidden)
        role = element.get("data-pptx-text-role", "").lower()
        if local == "text" and not hidden and not excluded and role not in {"source", "footnote"}:
            text = "".join(element.itertext()).strip()
            if text:
                blocks.append(text)
            return
        for child in element:
            walk(child, hidden, excluded)

    walk(root, False, False)
    return blocks


def _notes_blocks(project: Path, page_id: str) -> list[str]:
    for suffix in (".md", ".txt"):
        path = project / "notes" / f"{page_id}{suffix}"
        if path.is_file():
            return [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    total = project / "notes" / "total.md"
    if total.is_file():
        from total_md_split import parse_total_md
        stems = [path.stem for path in sorted((project / "svg_output").glob("*.svg"))]
        text = parse_total_md(total, stems, verbose=False).get(page_id, "")
        return [line.strip() for line in text.splitlines() if line.strip()]
    return []


def _claims(block: str) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    claims.extend(("number_date_amount_ratio", match.group(0)) for match in NUMBER_RE.finditer(block))
    claims.extend(("organization", match.group(0)) for match in ORG_RE.finditer(block))
    claims.extend(("responsible_department", match.group(1)) for match in RESPONSIBILITY_RE.finditer(block))
    claims.extend(("case_outcome", match.group(0)) for match in CASE_EFFECT_RE.finditer(block))
    return list(dict.fromkeys(claims))


def scan_deck_facts(project_path: str | Path) -> list[dict[str, Any]]:
    project = Path(project_path).expanduser().resolve()
    from director_plan import load_plan, resolve_evidence_ref
    plan = load_plan(project)
    issues: list[dict[str, Any]] = []
    for page in plan["pages"]:
        page_id = page["page_id"]
        refs = page.get("source_refs", page.get("evidence_refs", []))
        evidence = "\n".join(resolve_evidence_ref(project, ref)["text"] for ref in refs)
        blocks = [*_svg_blocks(project / "svg_output" / f"{page_id}.svg"), *_notes_blocks(project, page_id)]
        for block in blocks:
            if any(marker in block for marker in QUALIFIERS):
                continue
            for category, token in _claims(block):
                if token not in evidence:
                    issues.append({"page_id": page_id, "category": category, "token": token, "message": f"unverified {category}: {token}"})
    return issues
