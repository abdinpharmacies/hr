# Save manually entered targets

Recent relevant commit: c0039f977ed4a44a465577b36fcd0567ce984b13
Author: emadco88
Date: 2026-09-17
Original commit subject: ab_deploy/ Stable
- Established protected target creation and draft-only editing.

## Current changes before commit:

Author: emadco88
Date: 2026-09-21 (UTC)
Commit: uncommitted

- Accept the false Selected default submitted with new inline target rows.
- Discard only explicitly named computed/related display fields; derive their values from server and execution records.
- Always create targets unselected, including when context supplies a different selection default.
- Preserve rejection of scripts, snapshots, execution relations, true selection and other workflow values, as well as draft-only creation and duplicate-server protection.
- Bump version to 19.0.4.1.3. No new user-facing strings; existing Arabic translations remain applicable.

Validation: reproduced default_get/onchange field payloads; rolled-back ORM checks passed for single target creation, multiple inline targets on a new request, display recomputation, workflow-field rejection, duplicate protection and non-draft rejection. No deployments, notifications or validation records were committed.

Files changed for this fix:

- `ab_deploy/models/deployment.py`
- `ab_deploy/__manifest__.py`
- `ab_deploy/changelog.d/2026-09-21-manual-target-save.md`

Earlier uncommitted selection and display-order changes remain documented in their 2026-09-20 entries.
