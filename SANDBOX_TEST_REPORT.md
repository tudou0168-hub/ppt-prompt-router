# PPT Prompt Router 3.1.3 — Sandbox Program Validation

## Scope

This sandbox validation tests the Router program only. It does not generate a full PPT deck and does not modify PPT Master.

Validated Direct Plan Profiles:

- `government_annual_summary`
- `government_strategy`
- `work_report`
- `decision_meeting`
- `product_technical`

## Program changes

1. Four newly migrated prompts were rewritten to the V15 structure:
   - Goals
   - Skills
   - Workflows
   - 语义导演
   - 每页输出格式
   - 与 PPT Master 衔接
2. Removed page-specific examples and fixed page-number examples to reduce Agent anchoring and imitation.
3. Router Director handoff is now path-only:
   - professional prompt path
   - material paths
   - template/reference/workspace paths
   - user task and explicit constraints
   - output path
4. Direct Plan Profiles no longer stack a Secondary Lens. One professional Profile owns the Director context.
5. Router → PPT Master remains typed-path-only with a short activation prompt.
6. LIGHT/BYPASS/unmigrated FULL do not receive a nonexistent `presentation_plan.md`.
7. Program regression was reduced to representative, high-value checks instead of 188 repeated routing variants.

## Sandbox validation

`python3 scripts/regression.py`

Result:

```json
{
  "router_version": "3.1.3",
  "representative_routes": 6,
  "direct_plan_profiles": 5,
  "path_only_director": "passed",
  "typed_master_handoff": "passed",
  "prompt_anti_anchoring": "passed",
  "non_plan_paths": "passed"
}
```

Additional checks:

- `python3 -m py_compile scripts/*.py installers/*.py install.py` — PASS
- `python3 -m json.tool prompt-index.json` — PASS
- `python3 install.py install --target <temp>` — PASS
- `python3 install.py validate --target <temp>` — PASS
- Regression re-run from the installed temporary package — PASS

## Representative routing checked

- Government annual/half-year summary → `government_annual_summary`
- Government digital/strategic construction plan → `government_strategy`
- Enterprise/project work review → `work_report`
- Management decision meeting → `decision_meeting`
- Product/technical solution → `product_technical`
- Government annual-vs-strategy counter-signal boundary → strategy wins when explicit planning/construction language is present

## What this does not claim

This report does not claim final PPT visual quality has been validated. The sandbox package does not contain the user's local PPT Master runtime, templates or real project assets. Actual PPT validation should be performed by Codex using `CODEX_ACTUAL_TEST.md`: one Profile at a time, 3–4 representative pages only, fail fast on the first meaningful defect.
