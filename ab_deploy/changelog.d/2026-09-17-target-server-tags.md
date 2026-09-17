# Target server tags and bulk selection

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Replace the request's target list with a many2many_tags selector through an inherited XML view.
- Add separate buttons to append all active development or production servers outside maintenance, preserving selected servers and preventing duplicates.
- Remove request-level Environment and its matching restriction so one request can include mixed server environments. Server environments and CSV import environments remain available.
- Compute tags from existing target records and synchronize edits through a draft-only inverse, preserving unchanged target IDs, snapshots and execution history. Archived selections remain visible but cannot be newly saved as valid targets.
- Enforce Developer access and unqueued draft state on both tag edits and bulk actions; retain target availability checks at submission and queueing.
- Add both Arabic translations from the exported POT, update usage documentation and bump the module to 19.0.3.2.0.

## Validation

- Targeted upgrade passed on disposable database `ab_deploy_queue_validation_20260917`.
- 21 ORM/view checks passed: mixed bulk selection, repeated clicks, availability exclusions, manual edits, creation/copy/multi-record inverse, target ID preservation, frozen scripts, correct execution targets, and role/state restrictions.
- Both button labels and the tag selector were verified in the combined Arabic request form using a Developer user.
- Both Arabic catalogs passed format checks; Python/XML syntax and diff whitespace checks passed.
- Fixtures rolled back. No branch SSH/tmux activity, live database upgrade or service restart performed.

Files changed:

- `ab_deploy/__manifest__.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/runner/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-target-server-tags.md`
