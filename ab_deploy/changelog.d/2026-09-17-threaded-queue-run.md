# One queue job with streaming SSH progress

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Replace repeated coordinator scheduling with one queue job per deployment run, using up to 70 SSH threads and persistent SSH monitoring.
- Save progress through short independent transactions in the main thread; SSH threads exchange bounded plain-data events and never access the ORM. Persist launch intent before remote side effects.
- Display per-server execution stages, failure categories, blockers, queue runs and immutable connection-attempt history.
- Store full command output and optional Odoo warning/error output in ordered immutable attachments, with incremental download offsets and bounded previews.
- Confirm same-server conflicts before queueing. Allow Executors/Administrators to cancel only older unstarted executions on overlapping servers; audit the actor and replacement deployment. Reconfirm when conflicts change.
- Allow selected SSH-failure retries with frozen approval/settings. Reconnect to existing remote execution keys after uncertain launches; setup/script failures require a new request.
- Support explicit monitoring recovery, per-server observation deadlines and a one-hour batch deadline without terminating remote scripts. Waiting batches can observe stale blockers without creating polling queue records.
- Preserve compatibility entrypoints for serialized old queue tasks, handing them to deduplicated batch jobs without retaining coordinator scheduling or adding a cron.
- Add inherited views, module-owned ACLs, English/Arabic strings, documentation and version 19.0.4.0.0.

## Validation

- Targeted module upgrade passed on disposable database `ab_deploy_queue_validation_20260917`.
- Twenty-three workflow checks passed: batch deduplication, overlap-scoped cancellation, conflict changes, running-script protection, retry classification, attempt history and log access restrictions.
- All 21 existing target-tag, mixed-environment, approval-freezing and access regression checks passed.
- A 72-target test reached exactly 70 SSH threads, verified progress from a separate database cursor before completion, stored both log streams, and retained one queue record. Redelivery did not replay completed work.
- Timeout/recovery checks preserved uncertain execution state and resumed the same remote key without launching again.
- Local streaming checks used stub SSH/tmux executables and temporary files: live stages, incremental output, large logs, optional Odoo capture, script failure, preflight SSH failure, timeout survival and monitoring-only resume.
- Existing collector filtering/rotation/truncation checks passed. Arabic retry/resume controls, conflict confirmation and stage labels were verified at runtime. Both catalogs passed format validation.
- No live service restart, live database upgrade, branch SSH execution or real tmux session operation was performed.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/data/queue_jobs.xml`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/models/odoo_logs.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/runner/threaded.py`
- `ab_deploy/runner/README.md`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/batch_views.xml`
- `ab_deploy/wizard/__init__.py`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/conflict_views.xml`
- `ab_deploy/wizard/recovery.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-threaded-queue-run.md`
