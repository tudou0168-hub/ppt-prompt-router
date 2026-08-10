# Codex Actual Test — Minimal Representative Pages Only

Use the supplied Router package as-is. Do not rewrite its professional Prompts and do not modify PPT Master source.

## Test objective

Verify that the Router can take real client inputs — source material, PPT/template/reference paths, user prompt and explicit requirements — select the correct professional Prompt, generate `presentation_plan.md`, and activate PPT Master through the short typed-path handoff.

This is not a full-deck production test.

## Test method

Test one Profile at a time:

1. `government_annual_summary`
2. `government_strategy`
3. `work_report`
4. `decision_meeting`
5. `product_technical`

For each Profile:

1. Use one real, previously unoptimized client task.
2. Run Router from the normal task entrance.
3. Verify the selected Profile before continuing.
4. Generate `presentation_plan.md` in the isolated Router Director context.
5. Inspect the Plan before invoking PPT Master.
6. If the Plan is professionally wrong, factually wrong, ignores user requirements, or is clearly too generic: STOP. Do not invoke PPT Master.
7. If the Plan is valid, start a fresh PPT Master context using only the typed paths, user requirements and short activation prompt.
8. From the real Plan, choose only 3–4 representative pages. Do not use fixed page numbers.
9. Run the native PPT Master stages needed to produce only those representative pages.
10. Inspect the representative output. Do not generate the rest of the deck.

## Representative page roles

Choose only roles that truly exist in the material.

### government_annual_summary
- result/evidence
- mechanism/experience
- next-step action
- issue/recommendation

### government_strategy
- current state/gap
- overall system or key construction task
- implementation path/guarantee
- decision/request if present

### work_report
- key result/KPI
- progress deviation/problem/risk
- next action
- resource/coordination if present

### decision_meeting
- decision question/constraint
- option comparison or trade-off
- recommendation/risk
- final decision action

### product_technical
- business scenario/capability
- architecture/system relationship
- key process or data flow
- implementation/governance/value

## Fail fast

Stop the current test immediately when the first meaningful defect is sufficient to locate the broken layer.

Classify the first distortion:

1. Wrong Profile / scene recognition → Router routing/semantics/registry.
2. Wrong professional reasoning in Plan → professional Profile.
3. Lost path / user constraint / context contamination → Router handoff.
4. PPT Master native process not properly activated → activation/call chain.
5. Plan and Design Spec are correct, but SVG/layout/image-lock/internal Executor errors occur → PPT Master upstream defect.

For cases 1–4: stop and report exact evidence. Do not continue with later pages or later Profiles until the Router-side problem is fixed from the root and the same test is restarted from the Router entrance.

For case 5: stop and report the PPT Master defect. Do not modify PPT Master source and do not add Router geometry/font/template/page-specific compensation rules.

## Pass condition

A Profile passes when 3–4 representative pages are enough to confirm:

- correct Profile;
- professional, fact-grounded Plan;
- user requirements preserved;
- typed-path isolation works;
- PPT Master consumes the Plan;
- the appropriate native/high-level/conditional capabilities are active;
- representative pages are professionally usable without project-specific Router hacks.

Once a Profile passes, stop it and move to the next Profile. Never generate a full deck merely to prove the program works.

## Return evidence only

For each Profile return:

- real source path;
- template/reference/workspace paths;
- user request;
- selected Profile;
- `presentation_plan.md` path;
- selected 3–4 representative page IDs and why they were selected;
- `design_spec.md` / `spec_lock.md` path if reached;
- representative PNG/SVG paths;
- first defect and first-distortion classification, or PASS;
- whether the test was stopped.

Do not continue after a meaningful failure just to finish a report.
