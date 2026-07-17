# PPT Director Strategist Contract

Read `analysis/director_profile.md` in full before planning. Produce one and
only one planning file: `analysis/director_plan.json`. Do not create separate
Storyline, content map, slide plan, page order, or sample-plan files.

The plan may contain the complete content map, fact boundary, and storyline,
but page production reads only `pages` and `sample_pages`. New 3.1 projects use
non-visual page requirements only. Each page must include:

- `page_id`
- `page_role`
- `page_intent`
- `required_messages`
- `source_refs`
- `factual_constraints`
- `unresolved_questions`

Do not add layout, grid, card count, columns, colors, fonts, composition,
visual archetype, visual style, icon/image placement, `relationship_type`,
`visual_anchor`, `image_strategy`, or `rhythm_role`. PPT Master owns those
decisions during actual page design.

Each content page expresses one core conclusion. Source references use a
project-relative Markdown line range (`sources/file.md#L10-L20`) or a unique
heading anchor (`sources/file.md#H:Heading`). Facts, goals, estimates, proposals,
and inferences must remain distinguishable.

Read `.director/generation_mode.json` before selecting candidates. Director selects
candidate page ids only; PPT Master chooses every visual relationship, composition,
resource, template element, image treatment, color, and typography decision.

For every mode, select exactly three non-cover, non-TOC, non-ending,
non-plain-text design probes:

1. `information_density`: the page most likely to collapse into card stacking.
2. `complex_relationship`: the densest process, mechanism, or relationship page.
3. `visual_signature`: the page best able to prove the project's distinctive
   image, chart, architecture, or core visual language.

The three pages must be different. Their structures must test different design
risks rather than merely provide attractive examples.

The three probe records must use distinct `page_id` values and the canonical
`expression_task` values `information_density`, `complex_relationship` and
`visual_signature`. Each record uses `sample_role` and `reason`; it does not
prescribe a layout.

Do not create style samples, A/B/C directions, layout decisions, or fixed page
components. The three probes are formal pages and are sealed before Design Approval.
