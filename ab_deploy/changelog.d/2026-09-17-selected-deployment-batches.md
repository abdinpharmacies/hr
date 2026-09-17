# Selected deployment batches

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Replace target tags with existing target rows, with delayed status and executor-controlled Deploy selection after approval.
- Keep production bulk-add without duplicates and remove the development bulk-add button.
- Add Select All for Deployment and Clear Deployment Selection across all eligible targets.
- Queue only selected targets, preserve approval for later batches, clear queued selections and prevent reselecting existing executions.
- Restrict conflicts to selected servers and reconfirm when the selection or conflicting executions change.
- Add executor target-write access with backend guards limiting approved edits to selection only.
- Add Arabic translations from the exported module POT, update workflow documentation and bump version to 19.0.4.1.0.

## Validation

- Ran the user-requested service restart and targeted upgrade on deploy19.
- Initial upgrade exposed validation of the previous inherited view's development button; retaining its existing backend action while removing the visible button resolved the error.
- Final upgrade exited 0; its process log recorded Modules loaded and Registry loaded with no ERROR/CRITICAL entries.
- Existing duplicate Target Servers field-label warning remains.
- No additional functional tests or branch deployments were run.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/security/ir.model.access.csv`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/wizard/conflict_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/runner/README.md`
- `ab_deploy/changelog.d/2026-09-17-selected-deployment-batches.md`
