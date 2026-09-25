# Per-server command parameters

Recent relevant commit: c1cae6c254e799fd89afd932aaad50a64bd0bed3
Author: emadco88
Date: 2026-09-23
Original commit subject: ab_deploy/ UPD post-deployment

- Added required linked checks and frozen action/check blocks.

Files changed in that commit:
- `README.md`, `__manifest__.py`, `models/commands.py`, `models/deployment.py`
- `views/command_editor_views.xml`, `views/command_type_views.xml`
- `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/2026-09-23-linked-checks.md`

## Current changes before commit:

Author: emadco88
Date: 2026-09-24 (UTC)
Commit: uncommitted

- Add admin-only ab_deploy_command_parameter rows (Server, Variable Name, Value) on Command Catalog, unique per command/server/name.
- Validate DEPLOY_ names; reserve built-in database and Odoo path variables and reject null bytes/oversized custom values.
- Resolve command/server rows through a private scoped lookup after access checks. Freeze shell-quoted Bash assignments into each command at submission; preserve existing snapshots and retry behavior.
- Populate automatic database, Python, config, server path, log path and odoo-bin variables from the target server; require values only for referenced variables.
- Document literal/comment reference detection, quoted references, local shell-variable behavior and the ordinary-values-only security boundary.
- Add English/Arabic UI/help and ACLs, update documentation and bump to 19.0.4.7.0.
- Earlier uncommitted retry and database-name changes remain documented in their separate changelog entries.

Validation:
- Targeted deploy19 upgrade completed with no ERROR/CRITICAL/traceback; repaired README literal formatting reported during the preceding upgrade.
- Rolled-back ORM checks passed for server isolation, missing/duplicate/invalid values, reserved names, snapshot stability, admin-only CRUD/read/fields access and non-admin developer submission.
- Harmless local Bash checks preserved quotes, newlines, command-substitution syntax and backticks as literal values. Scripts without parameter references remained unchanged.
- Python/XML checks, both msgfmt --check-format checks and diff whitespace checks passed; Arabic view text verified in a rolled-back transaction.
- No real SSH, remote deployment or Telegram delivery during validation. Services restarted after checks; no started/enqueued queue jobs before stopping services.

Files changed for this feature:
- `ab_deploy/models/command_parameters.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/command_parameters_views.xml`
- `ab_deploy/views/command_editor_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-24-command-parameters.md`
