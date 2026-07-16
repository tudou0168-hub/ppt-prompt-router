"""Compute effective SVG font sizes for PPT Director profile minimums."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1, 0, 0, 1, 0, 0)
TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
FONT_RE = re.compile(r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(px)?\s*$", re.I)


class TypographyError(ValueError):
    pass


def _multiply(left: Matrix, right: Matrix) -> Matrix:
    a, b, c, d, e, f = left; g, h, i, j, k, l = right
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)


def _transform(value: str | None) -> Matrix:
    result = IDENTITY
    if not value:
        return result
    consumed = ""
    for match in TRANSFORM_RE.finditer(value):
        consumed += match.group(0)
        name = match.group(1).lower(); values = [float(item) for item in NUMBER_RE.findall(match.group(2))]
        if name == "matrix" and len(values) == 6:
            current = tuple(values)  # type: ignore[assignment]
        elif name == "translate" and len(values) in {1, 2}:
            current = (1, 0, 0, 1, values[0], values[1] if len(values) == 2 else 0)
        elif name == "scale" and len(values) in {1, 2}:
            current = (values[0], 0, 0, values[-1], 0, 0)
        elif name == "rotate" and len(values) in {1, 3}:
            angle = math.radians(values[0]); cosine, sine = math.cos(angle), math.sin(angle)
            rotation = (cosine, sine, -sine, cosine, 0, 0)
            if len(values) == 3:
                cx, cy = values[1], values[2]
                current = _multiply(_multiply((1, 0, 0, 1, cx, cy), rotation), (1, 0, 0, 1, -cx, -cy))
            else:
                current = rotation
        elif name == "skewx" and len(values) == 1:
            current = (1, 0, math.tan(math.radians(values[0])), 1, 0, 0)
        elif name == "skewy" and len(values) == 1:
            current = (1, math.tan(math.radians(values[0])), 0, 1, 0, 0)
        else:
            raise TypographyError(f"unsupported or invalid transform: {match.group(0)}")
        result = _multiply(result, current)
    if re.sub(r"[\s,]+", "", value.replace(consumed, "")):
        raise TypographyError(f"unparsed transform: {value}")
    return result


def _style(element: ET.Element) -> dict[str, str]:
    result = {}
    for declaration in element.get("style", "").split(";"):
        if ":" in declaration:
            key, value = declaration.split(":", 1)
            result[key.strip().lower()] = value.strip()
    return result


def _font_size(element: ET.Element, inherited: float | None) -> float:
    style = _style(element)
    raw = style.get("font-size") or element.get("font-size")
    if raw is None:
        if inherited is None:
            raise TypographyError("visible text has no resolvable font-size")
        return inherited
    match = FONT_RE.match(raw)
    if not match:
        raise TypographyError(f"unsupported font-size: {raw}")
    value = float(match.group(1))
    if value <= 0:
        raise TypographyError(f"invalid font-size: {raw}")
    return value


def _hidden(element: ET.Element, inherited: bool) -> bool:
    style = _style(element)
    return inherited or element.get("display") == "none" or element.get("visibility") == "hidden" or element.get("opacity") == "0" or style.get("display") == "none" or style.get("visibility") == "hidden" or style.get("opacity") == "0"


def _nested_svg_matrix(element: ET.Element) -> Matrix:
    if element.tag.rsplit("}", 1)[-1] != "svg" or not element.get("viewBox"):
        return IDENTITY
    values = [float(value) for value in NUMBER_RE.findall(element.get("viewBox", ""))]
    if len(values) != 4 or values[2] == 0 or values[3] == 0:
        raise TypographyError("invalid nested svg viewBox")
    width = element.get("width"); height = element.get("height")
    if not width or not height:
        return IDENTITY
    width_match, height_match = FONT_RE.match(width), FONT_RE.match(height)
    if not width_match or not height_match:
        raise TypographyError("nested svg width/height must use px values")
    return (float(width_match.group(1))/values[2], 0, 0, float(height_match.group(1))/values[3], 0, 0)


def _minimums(svg_path: Path) -> dict[str, float]:
    project = svg_path.resolve()
    for candidate in (project.parent, *project.parents):
        contract = candidate / "analysis" / "director_contract.json"
        if contract.is_file():
            profile = json.loads(contract.read_text(encoding="utf-8"))["profile"]["id"]
            body = 20 if profile in {"government_strategy", "decision_meeting"} else 18
            return {"body": body, "supporting": 16, "footnote": 12, "source": 12}
    return {"body": 18, "supporting": 16, "footnote": 12, "source": 12}


def effective_font_size_errors(svg_path: str | Path, root: ET.Element | None = None) -> list[str]:
    path = Path(svg_path).resolve()
    try:
        root = root or ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"typography check cannot parse SVG: {exc}"]
    minimums = _minimums(path)
    errors: list[str] = []

    def walk(element: ET.Element, matrix: Matrix, font: float | None, role: str, hidden: bool) -> None:
        local = element.tag.rsplit("}", 1)[-1]
        try:
            matrix = _multiply(matrix, _transform(element.get("transform")))
            if local == "svg" and element is not root:
                matrix = _multiply(matrix, _nested_svg_matrix(element))
            font = _font_size(element, font) if local in {"text", "tspan"} else font
        except TypographyError as exc:
            errors.append(str(exc))
            return
        role = element.get("data-pptx-text-role") or role
        hidden = _hidden(element, hidden)
        direct_text = (element.text or "").strip()
        if local in {"text", "tspan"} and direct_text and not hidden:
            if font is None:
                errors.append("visible text has no font-size")
            else:
                determinant = matrix[0] * matrix[3] - matrix[1] * matrix[2]
                if abs(determinant) < 1e-12:
                    errors.append("visible text uses a non-invertible transform")
                else:
                    vertical_scale = math.sqrt(matrix[2] ** 2 + matrix[3] ** 2)
                    effective = font * vertical_scale
                    normalized = role if role in minimums else "body"
                    minimum = minimums[normalized]
                    if effective + 1e-6 < minimum:
                        errors.append(f"effective font size {effective:.2f}px is below {normalized} minimum {minimum}px: {direct_text[:40]}")
        for child in element:
            walk(child, matrix, font, role, hidden)
            tail = (child.tail or "").strip()
            if tail and local in {"text", "tspan"} and not hidden and font is not None:
                effective = font * math.sqrt(matrix[2] ** 2 + matrix[3] ** 2)
                normalized = role if role in minimums else "body"
                if effective + 1e-6 < minimums[normalized]:
                    errors.append(f"effective font size {effective:.2f}px is below {normalized} minimum {minimums[normalized]}px: {tail[:40]}")

    try:
        root_viewport = _nested_svg_matrix(root)
    except TypographyError as exc:
        return [str(exc)]
    walk(root, root_viewport, None, "body", False)
    return list(dict.fromkeys(errors))
