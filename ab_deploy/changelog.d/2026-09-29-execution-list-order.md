# Execution list ordering and failure decorations

Recent relevant commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Retain existing deployment conflict controls and module packaging.

Files changed (relevant to this update):
- `ab_deploy/__manifest__.py`

## Current changes before commit:

Author: emadco88
Date: 2026-09-29 (UTC)
Commit: uncommitted

- Set the deployment job model's Python default ordering to Last Checked At descending, with descending job ID as the tie-breaker. Remove both One2many and standalone job-list XML overrides; keep 80 rows per page in the One2many.
- Use native Odoo danger and bold row decorations for Failed and Unknown in Execution Jobs and both Target Servers lists.
- Preserve Target Servers ordering and pagination. Keep historical failed jobs decorated even when a later execution makes the target successful.
- Bump the module to 19.0.4.12.5. No user-facing strings changed; no translation additions required.
- Earlier uncommitted dependency, command-update and SSH-report work remains documented in the September 26 and September 28 changelog entries.

Validation:
- Targeted upgrade passed in isolated `ab_deploy_dependency_validation_20260926`.
- Eleven isolated checks passed: both combined job views inherit the Python default; the One2many retains its 80-row limit and decorations; Target Servers ordering remains unchanged. ORM searches place an older, more recently checked job first and use descending ID for timestamp ties. Latest-attempt target status and retry eligibility still use job ID, independently of display ordering.
- Evaluated both decorations across all eight statuses: only Failed and Unknown match. Verified the Odoo renderer maps these decorations to text-danger and fw-bold.
- git diff whitespace validation passed. No live database upgrade, service restart or deployment records changed.

Files changed (this portion of the current working tree):
- `ab_deploy/models/jobs.py`
- `ab_deploy/views/display_order_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/changelog.d/2026-09-29-execution-list-order.md`
