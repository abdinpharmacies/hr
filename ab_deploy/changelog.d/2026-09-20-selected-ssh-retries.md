# Select servers for SSH retry

Recent relevant commit: c0039f977ed4a44a465577b36fcd0567ce984b13
Author: emadco88
Date: 2026-09-17
Original commit subject: ab_deploy/ Stable
- Established deployment target selection and SSH retry execution.

## Current changes before commit:

Author: emadco88
Date: 2026-09-20 (UTC)
Commit: uncommitted

- Reuse deploy as Selected; enable selection for delayed servers and latest SSH failures without adding a stored selection field or wizard.
- Retry only selected SSH failures. Reject mixed/ineligible and empty selections before scheduling; retain existing job locks and busy-execution checks.
- Select All for Deployment and Select All SSH Failures replace the current selection; Clear Selection also clears stale selections.
- Clear processed selections after request-level retry scheduling. Keep per-job retry behavior and same-server concurrency protection.
- Add Arabic translations and bump version to 19.0.4.1.1.

Validation: targeted ab_deploy upgrades on deploy19; rolled-back checks with the retry executor mocked verified subset forwarding, unchanged unselected failures, category selection, clearing, and stale/incompatible/empty rejection. Arabic view verification passed. No real deployment or notification was scheduled. msgfmt unavailable on host.

Files changed:

- `ab_deploy/models/deployment.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/views/batch_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-20-selected-ssh-retries.md`
