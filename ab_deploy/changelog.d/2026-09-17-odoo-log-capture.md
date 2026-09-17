# Optional Odoo log capture

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Add four defaulted Odoo paths and optional request log capture, validating all paths at submission and freezing them in the target snapshot.
- Collect warning/error/critical records and tracebacks during remote command execution with a standalone Python follower; report missing files, rotation and truncation separately from command results.
- Download bounded chunks through the existing queue coordinator, preserving full filtered output in ordered immutable attachments and a bounded preview.
- Continue collection after command completion, deduplicate retries, stop stalled downloads, and recover incomplete log downloads without replaying commands.
- Add inherited server/request/job views, read-only viewer access, Arabic translations, documentation and version 19.0.3.3.0.

## Validation

- Targeted upgrade passed on disposable database `ab_deploy_queue_validation_20260917`.
- 41 ORM/view checks passed, including prior tag-selection regressions, path validation, frozen settings, completed-job collection, chunk reconstruction, retry handling and viewer access restrictions.
- Collector checks passed for timestamp filtering, large tracebacks, rotation/truncation, missing interpreter and independent command failure, using temporary files and a stub tmux executable.
- Eight existing engine checks passed, including idempotent launch and the 70-thread ceiling with mocked SSH.
- Both Arabic catalogs passed format checks; translated Odoo paths and capture checkbox were verified in an Arabic runtime context. Python/XML syntax and whitespace checks passed.
- No real branch SSH, tmux sessions, live database upgrade or service restart used.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/models/odoo_logs.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/runner/log_collector.py`
- `ab_deploy/runner/README.md`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/odoo_logs_views.xml`
- `ab_deploy/wizard/recovery.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-odoo-log-capture.md`
