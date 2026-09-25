# Server database name

Recent relevant commit: c1cae6c254e799fd89afd932aaad50a64bd0bed3
Author: emadco88
Date: 2026-09-23
Original commit subject: ab_deploy/ UPD post-deployment

- Added linked post-deployment checks and approval snapshots.

Files changed in that commit:
- `README.md`, `__manifest__.py`, `models/commands.py`, `models/deployment.py`
- `views/command_editor_views.xml`, `views/command_type_views.xml`
- `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/2026-09-23-linked-checks.md`

## Current changes before commit:

Author: emadco88
Date: 2026-09-24 (UTC)
Commit: uncommitted

- Add optional Database Name (`database_name`) on deployment servers, defaulting to `abdin_replica19`.
- Show it beside Odoo configuration paths and as an optional Servers list column.
- Store metadata for future automation; command execution and approval rules are unchanged.
- Add both Arabic translations and increment version to 19.0.4.6.0.
- Earlier uncommitted retry changes are documented in `2026-09-23-retry-script-failures.md`.

Validation: Python/XML parsing, msgfmt --check-format for both Arabic catalogs, and diff whitespace checks passed. Targeted deploy19 upgrade exited successfully without ERROR/CRITICAL/traceback. Rolled-back ORM checks verified the default, saved custom value, optional empty value, and runtime Arabic field/action translations. No remote deployments performed. Main and queue services restarted after verification; no started/enqueued queue jobs before stopping services.

Files changed for this feature:
- `ab_deploy/models/deployment.py`
- `ab_deploy/views/odoo_logs_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-24-server-database.md`
