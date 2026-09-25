# Retry selected SSH and script failures

Recent relevant commit: c1cae6c254e799fd89afd932aaad50a64bd0bed3
Author: emadco88
Date: 2026-09-23
Original commit subject: ab_deploy/ UPD post-deployment

- Linked required checks to deployment actions and froze ordered action/check blocks.

Files changed in that commit:
- `README.md`, `__manifest__.py`
- `models/commands.py`, `models/deployment.py`
- `views/command_editor_views.xml`, `views/command_type_views.xml`
- `i18n/ar.po`, `i18n/ar_001.po`
- `changelog.d/2026-09-23-linked-checks.md`

## Current changes before commit:

Author: emadco88
Date: 2026-09-23 (UTC)
Commit: uncommitted

- Rename buttons to Retry Selected Failures, Retry Failure and Select All Failures; reuse Selected for SSH and script failures.
- Retry confirmed script/check failures with a fresh execution and remote key using the full frozen approved script, preserving previous outcomes and logs through Retry Of.
- Remove the one-execution-per-target constraint while retaining unique execution keys. Target status and reports continue using the latest execution.
- Preserve SSH reconnection/reconciliation behavior and compatibility wrappers for existing action names.
- Require approved requests and latest eligible executions; reject stale, successful, setup, cancelled and manually resolved executions, plus active queue handlers.
- Retain same-server scheduling and remote locking. Update English/Arabic wording, documentation and version 19.0.4.5.0.

Validation:
- Targeted deploy19 upgrade completed without ERROR, CRITICAL or traceback; verified removal of the old target uniqueness constraint and retention of the key constraint.
- Rolled-back ORM tests passed for selected mixed failures, retry history/log isolation, repeated retries, stale/success/setup rejection, approved-only enforcement, SSH reconciliation, actual queue creation, active queue rejection, same-server blocking, latest target status and report counts.
- Harmless local Bash verified full approved action/check execution and nonzero check failure. No remote deployments, SSH connections or Telegram deliveries during validation.
- Python/XML syntax, git diff whitespace checks and both Arabic catalogs passed; msgfmt used from a temporary extracted gettext binary. Arabic view translation verified at runtime in a rolled-back transaction.
- Main Odoo and queue runner services restarted and active. No started/enqueued queue jobs existed before shutdown.

Files changed:
- `ab_deploy/models/batch.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/views/batch_views.xml`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-23-retry-script-failures.md`
