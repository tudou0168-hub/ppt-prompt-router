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
Standard mode's three risk samples stop at `sample_confirmation`. Template and
premium modes render A/B/C directions for the same overview/complex page pair,
then stop at the same gate. A later independent user decision is required before
full production. `sample-reject` returns the grouped flow to sample production
with the user's feedback; it does not create another plan or state file.
