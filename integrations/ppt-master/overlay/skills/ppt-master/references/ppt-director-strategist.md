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

Read `.director/generation_mode.json` before selecting samples.

For `standard`, preserve the existing three-risk contract and select exactly
three non-cover, non-TOC, non-ending, non-plain-text samples:

1. `information_density`: the page most likely to collapse into card stacking.
2. `complex_relationship`: the densest process, mechanism, or relationship page.
3. `visual_signature`: the page best able to prove the project's distinctive
   image, chart, architecture, or core visual language.

The three pages must be different. Their structures must test different design
risks rather than merely provide attractive examples.

For `template` and `premium`, select exactly two test pages after the full Plan
is complete and order them as:

1. `sample_role: overview`: one cover, overview, executive-summary, or summary page.
2. `sample_role: complex`: one relationship-dense content page with at least two
   required messages. It cannot be a simple title, plain-text, ending, or one-card page.

Director selects only the page pair. A/B/C later reuse the exact same `page_id`,
`page_intent`, `required_messages`, `source_refs`, `factual_constraints`, template
input, and content scope. Do not prescribe three different layouts. PPT Master
may vary only design direction, visual expression, composition, information
organization, and its own resource/template choices.
