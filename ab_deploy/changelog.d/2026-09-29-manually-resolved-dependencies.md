# Accept manually resolved prerequisite deployments

Recent relevant commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Preserve deployment conflict controls and localized execution guidance.

Files changed (relevant to this update):
- `ab_deploy/models/batch.py`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`

## Current changes before commit:

Author: emadco88
Date: 2026-09-29 (UTC)
Commit: uncommitted

- Accept Succeeded or Manually Resolved as a satisfied dependency for the same server, using the latest attempt by ID.
- Share the condition across queueing, retries, conflict confirmation and worker launch. Keep missing servers and other statuses blocked; preserve restricted prerequisite visibility.
- Preserve the separate manual-resolution status and audit history. Newer failures override older resolutions. Undoing resolution blocks pending launch/retry while already-started monitoring continues.
- Keep downstream execution manual; resolving a prerequisite does not create or launch a dependent job.
- Update help and queue/worker errors in English and both Arabic catalogs using an exported POT. Preserve old translation entries. Update README and the earlier dependency changelog; bump to 19.0.4.12.6.
- Earlier uncommitted changes remain documented in their existing module changelog entries.

Validation:
- Targeted isolated database upgrade passed without module errors.
- 105 checks passed: 13 manual resolution/undo/worker/retry/Arabic checks, 60 updated dependency regressions and 32 conflict regressions.
- Fixtures rolled back in `ab_deploy_dependency_validation_20260926`, with SSH mocked and no live data changes or live restart/upgrade. Scripts/results remain under `/tmp/ab_deploy_manual_dep_*` and `/tmp/ab_deploy_dependency_conflict_regression*`.
- Both catalogs pass msgfmt format validation; git diff whitespace check passes.

Files changed (this portion of the current working tree):
- `ab_deploy/models/dependencies.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-26-request-dependencies.md`
- `ab_deploy/changelog.d/2026-09-29-manually-resolved-dependencies.md`
