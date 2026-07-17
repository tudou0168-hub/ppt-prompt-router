# PPT Director Managed Runtime

For a project containing `analysis/director_contract.json`, use the public
`ppt-prompt-router/scripts/route.py` entrypoint only. Internal PPT Master CLIs,
legacy fallbacks, direct writes to `svg_output/`, and direct exports are blocked.

The Router command output lists the exact context for the current stage. Read
those files before acting. `page-begin` also returns the current page's Director
Plan fields; use them to decide the content relationship, resource choice, and
SVG composition. PPT Master resources and custom SVG remain equal design
options. Do not force a resource when it does not match the relationship.

Production order is enforced by `production_state.json`. A page must pass the
existing SVG quality checker, be rendered, have its latest PNG opened and
visually reviewed, and pass the bound review before the next page begins.
Every Phase-1 mode uses three different formal design probes. Each probe follows the
existing `page-begin`, SVG check, render, review, and `page-pass` flow. Once all three
are sealed, stop for Design Approval. Do not create style samples, A/B/C directions,
candidate directories, or two-by-three direction variants.

Router role Context is written only to `.director/context/current/<role>.json` and
overwritten on the next call. The Slide Designer remains the existing PPT Master
Executor and reads only its current-page Context, the matched template evidence, the
previous PNG when present, the Genome summary and Executor standards. Do not read full
project state, logs, unrelated SVG, Builder reasoning, or capability snapshots.

Deep-fusion production stops after every reviewed non-probe page; a hash-bound page
approval is required before sealing it. Probe pages require the unified Design Approval,
not three separate page approvals.
