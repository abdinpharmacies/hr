# Optional repository analysis

Use only for a repository architecture report requiring the bundled detector. Read [coverage and blind spots](../resources/c4/assets/detection-coverage.md) first. The detectors do not provide specialized Odoo or Flutter discovery; inspect those frameworks manually and add evidence-backed findings. A missing graph is missing analysis, not absence of components.

Read [the analyzer procedure](../resources/c4/GUIDE.md), using `resources/c4` wherever it says `<skill>`. It documents scripts, facts/model schemas, diagnostics and report generation. Keep the facts separate from the interpreted model; preserve user edits and account for relevant detected facts or exclusions.

For this unified workflow, the requested scope controls completion: people, flows and code views are optional when irrelevant, and Level 4 is never mandatory. Prefer existing project renderer tooling; do not let the analyzer's npx fallback download packages implicitly. Start with `--no-svg` when a local renderer is not established, then render requested views using the Diagrams route. Choose output location from the task/project convention; do not run analysis as an incidental side effect of a question.

Check status, parsing warnings and model drift, then manually validate important relationships against code. Automated coverage measures recognized patterns only. Inspect rendered outputs before claiming readability. Give the overview, findings with evidence, justified recommendations and unverified assumptions at the requested depth.
