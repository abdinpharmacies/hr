# On-demand health collection

Commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Retained SSH execution, conflict handling, and administrator resolution for unknown executions, which health collection now reuses.

Files changed in that commit:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/changelog.d/2026-09-26-conflict-resolution.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/batch.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/views/conflict_resolution_views.xml`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/conflict_views.xml`

## Current changes before commit:

Author: emadco88
Date: 2026-10-05 (UTC)
Commit: uncommitted

- Add Health Collection as a request purpose and Collect Health Report for administrator-authored check commands; preserve normal deployment defaults and approvals.
- Reuse approved script snapshots, revisions, target selection, queue execution, SSH, and immutable full output parts. Continue remaining commands only for health collection when an earlier command fails.
- Store one report per server execution, with collection status separate from health, counters, readable check details, JSON payload, and protected JSON download. Resume updates the existing report; a new execution creates a new report.
- Validate marked schema-version-1 JSON, stable check identifiers, statuses, diagnostic lengths, durations, duplicate keys, and bounded size/count. Preserve valid results and critical findings alongside explicit unknown collection errors.
- Show access-filtered latest server results ordered by execution start time; prevent delayed older executions from replacing newer snapshots. Reports and downloads follow request participant/company rules and reject public creation, modification, and deletion.
- Add native report views, request/job/server links, both Arabic translations merged from exported POT references, and command/deployment instructions. Bump `ab_deploy` from `19.0.4.13.1` to `19.0.4.14.0`.
- Preserve pre-existing uncommitted deployment work, documented in the earlier feature changelogs. This entry lists only files changed for health collection.

Files changed:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/health_report.py`
- `ab_deploy/models/script_revisions.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/runner/health.py`
- `ab_deploy/security/health_security.xml`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/command_type_views.xml`
- `ab_deploy/views/health_report_views.xml`
- `ab_deploy/changelog.d/2026-10-05-health-collection.md`

Validation:
- Fresh installation and targeted upgrade passed on isolated database `ab_deploy_health_validation_20261005`. Temporary fixture XML IDs were separated from addon-owned metadata; no fixture migration or hook is shipped.
- 26 parser/renderer checks passed, including ordinary-render compatibility, fail-fast behavior, critical health with successful execution, failures followed by later checks, split UTF-8/chunks, full output beyond 64 KiB, malformed/duplicate JSON, limits, and collision-free synthetic check identifiers.
- 46 rolled-back ORM/security checks passed, including approvals, snapshots, revision validation, access restrictions, downloads, latest-server ordering, retries/resume, ordinary requests, 500-check partial/final results, and per-server reports. SSH and queue scheduling were mocked; no test commands were sent to branch servers.
- Six HTTP checks confirmed JSON downloads for authorized request participants/administrators and denied unrelated/anonymous access.
- Exported `/tmp/ab_deploy_health.pot`, preserved existing translations, and added all new strings/references in `ar.po` and `ar_001.po`. Both passed `msgfmt --check-format`; Arabic menu/view and purpose labels differed from English at runtime.
- Python/XML parsing and `git diff --check` passed. Development tests and fixtures remain outside the runtime addon under `/tmp/ab_deploy_health_work`.
- Collector rollout: backed up `deploy19` to `/var/backups/odoo19-monitoring/deploy19_before_health_collection_20261005.backup`, validated its archive, applied only `-u ab_deploy`, and restarted the idle Odoo/queue services. Both are active, and the support URL and local Odoo endpoint return HTTP 200. No health commands, pilot requests, or test fixtures were installed in the collector.
