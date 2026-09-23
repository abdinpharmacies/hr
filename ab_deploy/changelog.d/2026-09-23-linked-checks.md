# Required checks linked to deployment actions

Recent relevant commit: 0897a30f3b19170e888aa4ec1814e3d5375f4b65
Author: emadco88
Date: 2026-09-23
Original commit subject: ab_deploy/ UI and Actions

- Added command types, required post-deployment checks and individual/selected SSH tests.

Files changed in that commit:
- `README.md`, `__manifest__.py`
- `models/commands.py`, `models/deployment.py`, `runner/engine.py`
- `views/command_editor_views.xml`, `views/command_type_views.xml`, `views/request_targets_views.xml`
- `i18n/ar.po`, `i18n/ar_001.po`
- `changelog.d/2026-09-22-post-deployment-checks.md`
- `changelog.d/2026-09-22-selected-ssh-test.md`, `changelog.d/2026-09-22-test-ssh.md`

## Current changes before commit:

Author: emadco88
Date: 2026-09-23 (UTC)
Commit: uncommitted

- Require active deployment actions to link one or more active checks; prevent archiving or converting checks referenced by active actions.
- Generate protected check rows immediately after each action on save, with shared checks repeated per action and standalone checks last.
- Support draft refresh, block reordering through action sequence, replacement/removal, and duplication without duplicate generated rows.
- Freeze complete action/check blocks with policy version 2, preserving version 1 and pre-policy approvals and scripts.
- Add catalog fields, refresh button, execution order, help, English/Arabic translations and usage documentation; bump to 19.0.4.4.0.
- Keep existing catalog data unchanged; configure required checks on existing actions before editing or submitting new requests.

Validation:
- Targeted deploy19 upgrade completed without ERROR, CRITICAL or traceback.
- Rolled-back ORM checks passed for catalog requirements, shared checks, generated-row protections, idempotent refresh, frozen snapshots after catalog changes, duplication, reorder, replacement/removal, check-only requests and legacy snapshots.
- Harmless local Bash execution passed. No validation SSH connections, remote deployments or Telegram messages.
- Python/XML syntax and git diff whitespace checks passed; both Arabic catalogs passed `msgfmt --check-format` using a temporary extracted gettext binary (no system installation).
- Arabic view text verified at runtime in a rolled-back language activation transaction.
- Main Odoo and queue runner services restarted and active; no started/enqueued queue jobs before shutdown.

Files changed:
- `ab_deploy/models/commands.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/views/command_type_views.xml`
- `ab_deploy/views/command_editor_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-23-linked-checks.md`
