# Prompt Router 2.1 Integration

## Ownership

| Owner | Responsibility |
|---|---|
| `ppt-prompt-router` | Select one Profile, identify template intent, create the director contract/profile snapshot, create/import the project, and call `router-accept`. |
| PPT Master Strategist | Create the only `analysis/director_plan.json`. |
| PPT Master production control | Enforce samples, serial page production, midpoint review, deck review, invalidation, and export preflight through the only `analysis/production_state.json`. |

Router must not create Storyline, slide plans, page state, review receipts, or export state.

## Receiver

```bash
python3 scripts/project_manager.py router-accept <project>
```

The receiver validates:

- `analysis/director_contract.json`
- `analysis/director_profile.md`
- Profile SHA256
- page count and template intent

It returns `accepted: true` only after controlled production is initialized. A status message without this machine response is not a handoff.

## Director Plan

The Strategist must fully read `analysis/director_profile.md` and write one plan containing `content_map`, fact boundary, Storyline, ordered `pages`, one core conclusion per page, and exactly three risk-selected `sample_pages`.

```bash
python3 scripts/project_manager.py director-plan <project> <plan.json>
```

Director Plan 2.0 page fields are limited to `page_id`, `headline`, `page_goal`, `page_role`, `key_message`, `relationship_type`, `visual_anchor`, `evidence_refs`, and `rhythm_role`. Layout, font, color, resource id, and SVG implementation remain Executor decisions.

The three samples must be three different pages, exclude cover, contents, closing, and ordinary text pages, and cover exactly:

- `card_stack_risk` — the page most likely to collapse into repeated cards
- `relationship_density` — the densest and most relationally complex page
- `visual_signature` — the page that best proves this project's distinctive visual ability

## Reference Elements

For `template_intent: reference_elements`, `router-accept` extracts the reference PPTX into project `design_spec.md`, `spec_lock.md`, and `analysis/template_reference/`.

The structure mode is always `flat`. Source masters, layouts, placeholders, coordinates, page count, and page roster are forbidden. Skip the normal style, font, palette, and brand selection UI; keep technical font, contrast, canvas, and asset validation.

## Controlled Page Loop

When `analysis/production_state.json` exists, never write directly to `svg_output/`.

```text
production.py begin
→ handwrite .page_work/current.svg
→ production.py check-render
→ open the latest .preview/Pxx.iterN.png
→ apply references/visual-review.md in controlled report-only mode
→ Executor edits and check-render runs again when needed
→ write/update the native .review/Pxx.json evidence
→ production.py pass-page
→ next page
```

Only passed pages are promoted to `svg_output/`. Any SVG mutation invalidates the latest PNG and report for release purposes. Router 2.1 pages cannot pass on a self-declared `--visual-check passed`; Production verifies the native report and current hashes. Legacy controlled projects retain the old parameter for compatibility.

## Quality Gates

- Before sample approval, only the three sample pages may begin.
- Every sample requires two real render/review iterations, a first-round finding, changed SVG/PNG hashes, and final status `fixed`.
- Ordinary Router 2.1 pages require at least one current native visual-review iteration.
- `A` approves samples, `B` reopens selected samples, and `C` selects three replacements.
- At half of the ordered pages, production blocks until midpoint review compares samples and recent pages.
- After all pages pass, production blocks export until whole-deck review.
- `svg_to_pptx.py` automatically runs production preflight whenever production state exists.
