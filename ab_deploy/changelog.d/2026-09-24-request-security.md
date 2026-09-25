# Request privacy and assigned execution

Recent relevant commit: c1cae6c254e799fd89afd932aaad50a64bd0bed3
Author: emadco88
Date: 2026-09-23
Original commit subject: ab_deploy/ UPD post-deployment

- Added required linked checks and frozen approval scripts.

Files changed in that commit:
- `README.md`, `__manifest__.py`, `models/commands.py`, `models/deployment.py`
- `views/command_editor_views.xml`, `views/command_type_views.xml`
- `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/2026-09-23-linked-checks.md`

## Current changes before commit:

Author: emadco88
Date: 2026-09-24 (UTC)
Commit: uncommitted

- Limit requests and related command/target/job/run/attempt/log records to owners, role-qualified assigned approvers/executors, and Deployment Administrators, preserving company restrictions.
- Add Assigned Executor; assigned approvers select an existing active executor before approval. Protect ownership and executor assignment against direct writes and context defaults.
- Enforce owner-only developer actions and assigned-executor execution actions in Python, with administrative override. Prevent self-approval even when an administrator submits on an owner's behalf.
- Require valid executor assignment for new queue/retry actions on legacy approved requests. Block reassignment during active executions/queue runs without changing approved scripts or historical work.
- Restrict audit and raw deployment queue internals to administrators; retain request-level Queue Runs and execution logs for participants.
- Hide inaccessible conflicts and hash conflict fingerprints; permit waiting, but prevent unauthorized cancellation/replacement. Filter displayed waiting executions through user access.
- Add module-scoped stored request links on messages/attachments and rules to protect historical recipients/authors; reject forged access links. Filter future notification recipients and enforce request access on deployment binary downloads even with a public flag/token.
- Preserve configured Telegram group audiences and existing shared catalog/server access. Update UI, both Arabic catalogs, documentation and version 19.0.4.8.0.
- Earlier uncommitted retry, database-name and parameter work is documented in its separate entries.

Validation:
- Targeted deploy19 upgrade completed without ERROR/CRITICAL/traceback after fixing inherited-view anchors and conflict-list fields.
- Rolled-back security scenarios passed for owners, assigned/unassigned approvers and executors, viewers, administrators and combined roles. Temporary role fixtures were XML and fully rolled back.
- Verified approval assignment, no self-approval, queue creation, active-run reassignment rejection, ownership forgery rejection, private related records, hidden conflicts, blocked replacement, queue metadata isolation and reassignment visibility.
- Verified message-author/recipient restrictions, private log attachments, public/token download enforcement, notification filtering, role revocation, legacy assignment requirements and Arabic runtime labels.
- Found and corrected an Odoo in-memory domain edge case: disabled role branches use impossible ID -1 instead of 0, so empty assignments cannot grant direct record access.
- Python/XML syntax, git diff whitespace and both msgfmt --check-format validations passed. Queue serialization/worker sudo handling inspected; no SSH, remote deployment or Telegram delivery during tests.
- No started/enqueued queue jobs before shutdown. Main Odoo and queue runner restarted after validation.

Files changed for this feature:
- `ab_deploy/models/request_security.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/security/request_rules.xml`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/request_security_views.xml`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/views/execution_views.xml`
- `ab_deploy/views/batch_views.xml`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/conflict_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-24-request-security.md`
