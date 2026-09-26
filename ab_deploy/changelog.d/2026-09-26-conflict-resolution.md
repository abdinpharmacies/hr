# Deployment queue blockers and inspection

Recent relevant commit: b61139d034b33dcc9729643d57753ae54f99f713
Author: emadco88
Date: 2026-09-25
Original commit subject: ab_deploy/ UPD major updates and security groups and workflow

- Restricted conflict visibility and replacement to authorized executors and administrators.

Files changed (relevant to this change):
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/conflict_views.xml`
- `ab_deploy/models/jobs.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/models/request_security.py`

## Current changes before commit:

Author: emadco88
Date: 2026-09-26 (UTC)
Commit: uncommitted

- Report canceled waiting executions and remaining blockers in persistent notifications, preserving restricted record visibility.
- Offer administrator-only Check and Resolve actions from conflict and request execution lists with last-check information and inspection guidance.
- Return to refreshed conflicts after resolution without clearing selected targets or implicitly queuing a deployment.
- Mark resolved executions Finished and prevent late stage observations from reversing that stage; reject malformed remote session indicators.
- Preserve explicit inspection notes, existing SSH verification and administrator permission checks.
- Append 11 POT-derived entries to both Arabic catalogs, document the workflow, and bump the module to 19.0.4.9.0.

Validation: fresh installation and targeted upgrade passed in isolated database `ab_deploy_conflict_validation_20260926`. All 32 rolled-back ORM/SSH-mock checks passed, covering mixed and queued-only cancellation, server isolation, hidden records, administrator/executor access, missing completion evidence, remote outcomes, live sessions, SSH errors/timeouts, malformed responses, stale conflicts, preserved selection, queue release and late events. English and Arabic views and Arabic Python notifications were verified at runtime. Both catalogs passed `msgfmt --check-format`. Fixtures remain outside the addon in `/tmp/ab_deploy_conflict_validation.py`; no real SSH deployment commands were used in validation.

Rollout: confirmed the live queue was empty, backed up `deploy19` to `/tmp/deploy19_before_conflict_resolution_20260926.backup`, stopped its web and queue services, upgraded only `ab_deploy`, and restarted both services. The upgrade completed without ERROR/CRITICAL/traceback; both services are active and `/web/login` returns HTTP 200. Read-only live checks verified version 19.0.4.9.0, English/Arabic conflict views, and the unchanged Failed/Succeeded outcomes for executions 439/569 on abdin-195.

Files changed:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/resolution.py`
- `ab_deploy/views/conflict_resolution_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-26-conflict-resolution.md`
