# Manually resolve failed executions

Recent relevant commit: 6738bd61911388479f9a549f2fc7ed90152366af
Author: emadco88
Date: 2026-09-22
Original commit subject: ab_deploy/ MAJOR UPDs
- Added selected SSH retries, report-aligned sorting and safe manual target entry.

## Current changes before commit:

Author: emadco88
Date: 2026-09-22 (UTC)
Commit: uncommitted

- Add Manually Resolved as a distinct terminal job/target status with resolver, time and required note.
- Allow executors/admins to resolve failed jobs on approved requests, and admins to undo with a reason. Check permissions and active runs under locks.
- Preserve original failure evidence and execution timestamps; retain both transitions in audit history.
- Exclude resolved jobs from retry, selection, monitoring and recovery; ignore stale worker observations. Do not send notifications or schedule execution on resolve/undo.
- Add actions, a confirmation wizard, filter, distinct list decoration, documentation and both Arabic translations; sort immediately before Succeeded.
- Bump version to 19.0.4.2.0.

Validation: corrected an initial view inheritance anchor; final targeted upgrade exited 0 without ERROR/CRITICAL/traceback. Rolled-back checks passed for required notes, wrong states, busy rejection, evidence preservation, late updates, monitoring exclusion, audit actor/history, admin undo and executor/viewer permissions. Arabic view and separate report count verified. No deployments, messages or validation data committed. msgfmt unavailable.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/models/jobs.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/models/display_order.py`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/wizard/__init__.py`
- `ab_deploy/wizard/manual_resolution.py`
- `ab_deploy/wizard/manual_resolution_views.xml`
- `ab_deploy/wizard/recovery.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-22-manual-resolution.md`
