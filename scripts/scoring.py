from __future__ import annotations
from dataclasses import dataclass
from .semantics import positive_occurrences

ANNUAL_REVIEW_COUNTERSIGNALS = (
    "专项规划", "建设方案", "实施方案", "战略规划", "路线图",
)


def is_government_annual_review(text: str, semantics: dict) -> bool:
    low = text.lower()
    return (
        "government" in set(semantics.get("domains", []))
        and "annual_review" in set(semantics.get("jobs", []))
        and not any(term in low for term in ANNUAL_REVIEW_COUNTERSIGNALS)
    )


@dataclass
class ScoreResult:
    profile_id: str
    score: int
    matched: dict


def score_profile(entry: dict, text: str, semantics: dict | None = None) -> ScoreResult:
    low = text.lower()
    score = 0
    matched = {'required': [], 'strong': [], 'supporting': [], 'counter': [], 'downrank': [], 'domain': [], 'job': []}
    groups = [
        ('required_signals', 6, 'required'), ('strong_signals', 3, 'strong'),
        ('supporting_signals', 1, 'supporting'), ('counter_signals', -5, 'counter'),
        ('downrank_when', -8, 'downrank'),
    ]
    seen = {}
    for key, weight, label in groups:
        for raw in entry.get(key, []):
            term = str(raw).strip()
            if not term:
                continue
            current = seen.get(term.lower())
            if current is None or abs(weight) > abs(current[0]):
                seen[term.lower()] = (weight, label, term)

    for term, (weight, label, original) in seen.items():
        present = positive_occurrences(low, term) > 0 if weight > 0 else term in low
        if present:
            score += weight
            matched[label].append(original)

    if semantics:
        domains = set(semantics.get('domains', []))
        jobs = set(semantics.get('jobs', []))
        domain_strength = dict(semantics.get('domain_scores', []))
        government_annual_review = is_government_annual_review(low, semantics)
        for domain in entry.get('domains', []):
            if domain in domains:
                score += 4
                matched['domain'].append(domain)
        for job in entry.get('jobs', []):
            if job in jobs:
                score += 5
                matched['job'].append(job)

        pid = entry.get('id')
        if pid == 'business_proposal' and 'proposal' in jobs: score += 10
        if pid == 'course_assignment' and 'assignment' in jobs: score += 10
        if pid == 'classroom_lesson' and 'classroom' in jobs and 'assignment' not in jobs: score += 8
        if pid == 'business_bid' and 'bid' in jobs: score += 9
        if pid == 'decision_meeting' and 'decide' in jobs: score += 5
        if pid == 'teaching_explainer' and 'explain' in jobs and ('government' in domains or 'education' in domains): score += 3
        if pid == 'corporate_training' and 'teach' in jobs and 'business' in domains: score += 3
        if pid == 'product_technical' and 'technology' in domains and domain_strength.get('technology', 0) >= 2: score += 4
        if pid == 'product_technical' and 'technology' in domains and domain_strength.get('technology', 0) >= 2 and 'explain' in jobs: score += 4
        if pid == 'government_annual_summary' and government_annual_review: score += 26
        if pid == 'government_annual_summary' and 'government' not in domains: score -= 6
        if pid == 'government_strategy' and 'government' in domains and ('report' in jobs or 'review' in jobs): score += 10
        if pid == 'government_strategy' and government_annual_review: score -= 12
        if pid == 'work_report' and government_annual_review: score -= 10
        if pid == 'data_analysis' and 'analyze' in jobs: score += 4
        if pid == 'data_analysis' and 'analyze' not in jobs: score -= 5
        if pid == 'meeting_speech' and 'speak' in jobs and any(x in low for x in ('讲话','发言','演讲')): score += 4
        if pid == 'public_talk' and 'public' in domains and (any(x in low for x in ('分享','沙龙')) or ('公开课' in low and 'speak' in jobs)): score += 5
        if pid == 'product_introduction' and 'product' in domains and 'present' in jobs and 'technology' not in domains: score += 4
        if pid == 'event_promotion' and 'promote' in jobs: score += 5
        if pid == 'corporate_training' and 'teach' in jobs and any(x in low for x in ('员工','内部','内训')): score += 2
        if pid == 'teaching_explainer' and 'education' in domains and ('teach' in jobs or 'explain' in jobs): score += 2
        if pid == 'planning_proposal' and 'plan' in jobs and not any(x in low for x in ('比较','选项','拍板','怎么选')): score += 4
        if pid == 'work_report' and 'report' in jobs and 'business' in domains and 'data' not in domains: score += 3

        if not domains:
            if pid == 'work_report' and 'report' in jobs: score += 6
            if pid == 'planning_proposal' and 'plan' in jobs: score += 4
            if pid == 'teaching_explainer' and 'explain' in jobs: score += 4

    return ScoreResult(entry.get('id', ''), score, matched)


def rank(index: dict, text: str, semantics: dict | None = None):
    results = [score_profile(e, text, semantics) for e in index.get('prompts', [])]
    results.sort(key=lambda x: (-x.score, x.profile_id))
    return results


def is_ambiguous(results):
    if not results or results[0].score < 5:
        return True
    return len(results) > 1 and results[0].score - results[1].score < 3


def confidence(results):
    if not results: return 'low'
    top = results[0].score
    gap = top - (results[1].score if len(results) > 1 else 0)
    if top >= 12 and gap >= 4: return 'high'
    if top >= 7 and gap >= 2: return 'medium'
    return 'low'
