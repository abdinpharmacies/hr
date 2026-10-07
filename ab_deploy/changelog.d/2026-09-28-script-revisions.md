# Approved script updates and execution history

Recent relevant commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Preserve deployment conflict inspection, replacement controls and request access restrictions.
- Add English and Arabic queue guidance.

Files changed (relevant to this change):
- `ab_deploy/models/batch.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`

## Current changes before commit:

Author: emadco88
Date: 2026-09-28 (UTC)
Commit: uncommitted

- Replace the earlier pending-approval revision flow with administrator-only Confirm Update. The required reason and ready-made preview apply to all changed Delayed/Failed servers; unchanged servers are skipped automatically.
- Show Update Commands only when eligible servers have catalog, required-check or parameter changes (or a rendering error to inspect). Computing visibility does not lock or mutate deployment records; refreshing/opening the form reevaluates it.
- Display Update Commands as a red danger button. Block queueing, direct queue confirmation and retries when selected servers have changed or invalid commands; selecting servers remains allowed.
- Recheck the catalog under command locks before queued jobs launch. Fail an unlaunched stale job with an actionable setup error so its commands can be updated after the queue run finishes, then retried. Preserve monitoring of already running executions.
- Regenerate and compare the complete proposal under locks at confirmation. Reject stale previews, active queue runs and duplicate confirmations atomically.
- Create revisions directly as Approved, including on the confirming administrator's own request. Create no approval activity, pending state or execution job. Initial request approval remains unchanged.
- Post one escaped internal chatter note, Commands updated and approved, with the native revision link, servers, changed commands, reason and administrator.
- Preserve immutable revision/job history and the original connection/log settings. Revised retries use fresh jobs/keys, including SSH/setup failures; historical monitoring continues using its original snapshot.
- Restrict revision creation and wizard access to Deployment Administrators. Remove normal approve/reject controls and APIs. Preserve historical states and allow administrators to explicitly cancel any legacy pending revision; never silently approve old proposals.
- Retain participant restrictions for revisions, lines and attachments and the earlier uncommitted per-server dependency implementation documented in `2026-09-26-request-dependencies.md`.
- Update the README and bump the module to 19.0.4.12.1. Preserve existing Arabic messages, add 11 POT-derived entries for this simplification in both catalogs (in addition to the earlier 74 revision/retry entries), and retain relevant exported references.

Validation:
- Version 19.0.4.12.1 targeted upgrade passed in the isolated dependency-validation database. 125 checks passed on this version: 19 deployment-guard/recovery/Arabic checks, 62 dependency checks, 32 conflict checks and 12 UI/Arabic checks. Verified the red button in the combined form and the translated blocking error through the actual queue action.
- Exported the updated POT and appended the new blocking message to both Arabic catalogs; both pass msgfmt format checks. Python/XML parsing and git diff whitespace checks pass. Current guard fixtures/results remain under `/tmp/ab_deploy_guard_*` and roll back without SSH.
- Fresh installation passed in `ab_deploy_simple_validation_20260928`; targeted upgrade of the prior revision version passed in `ab_deploy_dependency_validation_20260926`, without module ERROR/CRITICAL/traceback entries.
- Before the deployment guard was added, 151 checks passed: 41 simplified-workflow/history/permission checks, 62 dependency regressions, 32 conflict regressions, 4 concurrent-transaction checks and 12 Arabic/UI/read-only checks.
- Verified immediate approval, required reasons, unchanged-server skipping, absent approval activities/jobs, a single escaped chatter note, parameter/check change detection, failed retry history, active-run rejection, legacy cancellation and administrator confirmation of their own request.
- Separate transactions proved queuing and duplicate confirmation cannot cross confirmation locks; queuing after commit uses the newly approved snapshot. Viewing update availability acquires no deployment locks and creates no records.
- Verified the actual wizard Form flow, Arabic preview/confirmation/error/chatter rendering with `ar_001`, administrator-only button visibility and the removal of approval controls. Both catalogs pass `msgfmt --check-format`; Python/XML parsing and `git diff --check` pass.
- Fixtures/results remain outside the addon under `/tmp/ab_deploy_simple_*`. Workflow fixtures roll back. The concurrency fixture commits only in the isolated simple-validation database and leaves its request cancelled/archived and server archived, with no committed execution job. No real remote deployment commands ran.
- No live database upgrade or service restart was performed for this change. No migrations, hooks or test fixtures are shipped in the addon.

Files changed (current module working tree, including the earlier dependency work):
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/dependencies.py`
- `ab_deploy/models/script_revisions.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/models/request_security.py`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/security/revision_security.xml`
- `ab_deploy/views/dependency_views.xml`
- `ab_deploy/views/script_revision_views.xml`
- `ab_deploy/wizard/__init__.py`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/script_update.py`
- `ab_deploy/wizard/script_update_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-26-request-dependencies.md`
- `ab_deploy/changelog.d/2026-09-28-script-revisions.md`
