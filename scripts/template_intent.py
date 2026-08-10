"""PPTX/workspace intent annotations for ppt-prompt-router 3.1.3.

PPT Master 4.4 owns top-level route selection.  This module does **not** choose a
Master route; it only preserves the user's apparent intent so the Router can
hand the original signal to PPT Master without translating it into the old
Router 2.0 state machine.

Current annotations:
    visual_reference          use an existing deck / visual source as reference
    fill_native               keep native PPTX shells and replace/fill content
    create_reusable_template  create a reusable Brand/Style/Layout/Deck workspace
    enhance_native            preserve visible slides and add native enhancements
    workspace_candidate       an exact template workspace root was supplied
    none                      no reference/template intent is evident
    unspecified               a reference exists but intent is not safely resolved

Legacy Router 2.0 aliases are accepted by :func:`normalize_legacy_intent`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


VALID_INTENTS = (
    "visual_reference",
    "fill_native",
    "create_reusable_template",
    "enhance_native",
    "workspace_candidate",
    "none",
    "unspecified",
)

LEGACY_INTENT_MAP = {
    "reference_elements": "visual_reference",
    "native_fill": "fill_native",
    "reusable_template": "create_reusable_template",
    "none": "none",
}

# These are semantic hints only.  The authoritative route decision remains
# skills/ppt-master/workflows/routing.md in PPT Master 4.4.
MASTER_ROUTE_HINTS = {
    "fill_native": "fill_native_pptx",
    "create_reusable_template": "create_template",
    "enhance_native": "enhance_native_pptx",
    "workspace_candidate": "generate_pptx",
    "visual_reference": "generate_pptx",
}

INTENT_TRIGGERS: dict[str, tuple[str, ...]] = {
    "visual_reference": (
        "提炼", "借鉴", "参考设计", "参考风格", "设计语言", "视觉语言",
        "重新设计", "重做", "美化", "参考这个ppt", "参考这份ppt",
    ),
    "fill_native": (
        "套用", "填充", "填入", "填回", "页面壳", "只替换", "替换内容", "替换文案", "替换文字", "保留版式", "原版式", "保留模板",
        "保留母版", "保持版式", "直接套用", "用这套模板", "按这个模板填",
    ),
    "create_reusable_template": (
        "制作模板", "创建模板", "做成模板", "可复用的模板", "做成以后可复用", "以后复用", "复用模板",
        "模板工作区", "沉淀为模板", "可复用模板", "brand workspace",
        "style workspace", "layout workspace", "deck workspace",
    ),
    "enhance_native": (
        "保持页面不变", "保留现有页面", "不改可见页面", "不改变页面", "演讲者备注", "演讲备注",
        "speaker notes", "旁白", "配音", "音频", "timing", "timings",
        "转场", "transition", "动画", "播放时长", "自动播放",
    ),
}


@dataclass(frozen=True)
class IntentMatch:
    matched_intents: list[str]
    matched_keywords: dict[str, list[str]]


def normalize_legacy_intent(value: str) -> str:
    """Normalize either a current intent or a Router 2.0 alias."""
    if value in VALID_INTENTS:
        return value
    if value in LEGACY_INTENT_MAP:
        return LEGACY_INTENT_MAP[value]
    raise ValueError(f"unsupported PPTX intent: {value}")


def _expression_only(text: str) -> str:
    """Remove obvious paths/flags while retaining natural-language intent."""
    out = text or ""
    out = re.sub(r"(?:[A-Za-z]:[\\/]|/|~/)[^\s\"']+", " ", out)
    out = re.sub(r"--[\w-]+", " ", out)
    return re.sub(r"\s+", " ", out).strip().lower()


def detect(text: str, reference_paths: list[str] | None = None) -> IntentMatch:
    """Return all semantic intent matches; never select a PPT Master route."""
    expr = _expression_only(text)
    matched_keywords: dict[str, list[str]] = {}
    for intent, triggers in INTENT_TRIGGERS.items():
        hits = [trigger for trigger in triggers if trigger.lower() in expr]
        if hits:
            matched_keywords[intent] = hits

    # Natural-language reusable-template intent is often compositional rather
    # than a fixed phrase (e.g. “提取可复用的品牌/版式模板”). Treat the
    # combination as an annotation without trying to decide Brand/Style/Layout/Deck;
    # that child-workflow classification remains PPT Master's job.
    reusable_terms = ("可复用", "以后复用", "沉淀", "复用")
    template_terms = ("模板", "品牌", "版式", "布局", "风格工作区", "模板工作区")
    if any(x in expr for x in reusable_terms) and any(x in expr for x in template_terms):
        matched_keywords.setdefault("create_reusable_template", []).append("可复用 + 模板语义")
    creation_terms = ("创建", "制作", "沉淀", "提取", "做成", "打造")
    if any(x in expr for x in creation_terms) and "模板" in expr:
        matched_keywords.setdefault("create_reusable_template", []).append("创建动作 + 模板")

    return IntentMatch(
        matched_intents=list(matched_keywords.keys()),
        matched_keywords=matched_keywords,
    )


def classify(
    text: str,
    reference_paths: list[str] | None = None,
    *,
    workspace_roots: list[str] | None = None,
) -> str:
    """Return one intent annotation without stealing PPT Master routing authority.

    Ambiguous references now remain ``unspecified``.  Router 3.1.3 deliberately
    does not fall back to the old ``reference_elements`` behavior because PPT
    Master 4.4 has distinct Generate / Create Template / Fill Native / Enhance
    Native routes whose discriminator belongs to ``routing.md``.
    """
    reference_paths = list(reference_paths or [])
    workspace_roots = list(workspace_roots or [])
    match = detect(text, reference_paths)

    if len(match.matched_intents) == 1:
        return match.matched_intents[0]
    if len(match.matched_intents) > 1:
        # Preserve clear native/reusable intent even when words like "美化/提炼" also appear.
        for preferred in ("enhance_native", "create_reusable_template", "fill_native"):
            if preferred in match.matched_intents:
                return preferred
        return "unspecified"
    if workspace_roots:
        return "workspace_candidate"
    if reference_paths:
        return "unspecified"
    return "none"


def route_hint(intent: str) -> str | None:
    """Return a non-authoritative Master route hint for diagnostics only."""
    return MASTER_ROUTE_HINTS.get(normalize_legacy_intent(intent))
