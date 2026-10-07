# Bulk server parameters and command defaults

Commit: b61139d034b33dcc9729643d57753ae54f99f713
Author: emadco88
Date: 2026-09-25
Original commit subject: ab_deploy/ UPD major updates and security groups and workflow

- Introduced administrator-managed server parameter rows and shell-quoted parameter resolution before approval.

Files changed (parameter implementation in that commit):
- `ab_deploy/models/command_parameters.py`
- `ab_deploy/views/command_parameters_views.xml`

## Current changes before commit:

Author: emadco88
Date: 2026-09-30 (UTC)
Commit: uncommitted

- Add an editable server selection, Add All Deployment Servers, Key, Value, and Set Parameter to the command form.
- Add all active servers, including maintenance servers, without duplicates; create or update only the entered key on selected servers.
- With an empty selection, save an editable shared command default; server-specific values override defaults, including for future servers.
- Share validation, command locking, administrator checks and audit behavior between server parameters and defaults. Keep inputs separate from applied values and clear inputs when copying commands.
- Preserve approved scripts and frozen executions. Existing script revision and queue validation detect changes to resolved defaults for affected servers.
- Add both Arabic translations using exported Odoo POT references, update documentation, and bump version from 19.0.4.12.6 to 19.0.4.13.1.
- Put the script editor and Server Parameters on separate notebook pages. Show parameter guidance in a full-width notes box and organize bulk controls, defaults, and server overrides in module-scoped responsive panels with RTL-aware borders.
- Preserve pre-existing uncommitted dependency, revision, execution-order, and SSH-report work documented in the other changelog entries.

Files changed for this feature:
- `ab_deploy/models/command_parameters.py`
- `ab_deploy/views/command_parameters_views.xml`
- `ab_deploy/static/src/scss/command_editor.scss`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-30-bulk-server-parameters.md`

Validation:
- Fresh installation and targeted upgrade passed on isolated database `ab_deploy_parameters_validation_20260930`; no Odoo ERROR/CRITICAL entries in install or upgrade logs.
- 56 rolled-back ORM checks passed: bulk upserts, deduplication, defaults, server isolation, validation, uniqueness, role restrictions, copying, audit history, submission with linked checks, revision detection, queue blocking, and frozen execution scripts.
- Tests blocked SSH and queue scheduling; test records and in-memory queue jobs were rolled back. No operational database upgrade or remote deployment was performed.
- Exported `/tmp/ab_deploy_parameters.pot`, merged new entries/references without replacing existing translations, and passed `msgfmt --check-format` for both PO files.
- Verified Arabic buttons, help text, and field labels at runtime with `ar_001` against `en_US`.
- Notebook follow-up: targeted upgrade, SCSS compilation, combined inherited view placement, full-width notes structure, and Arabic notes heading passed; references exported to `/tmp/ab_deploy_parameters_view.pot`.
- Python/XML parsing and `git diff --check` passed. Test scripts remain outside the addon under `/tmp/ab_deploy_parameters_*`.
