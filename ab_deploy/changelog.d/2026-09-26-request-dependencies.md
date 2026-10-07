# Per-server deployment request dependencies

Recent relevant commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Report queue conflicts while preserving execution inspection and access controls.
- Provide English and Arabic conflict guidance.

Files changed (relevant to this change):
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`

## Current changes before commit:

Author: emadco88
Date: 2026-09-26 (UTC)
Commit: uncommitted

- Add draft-editable Depends On with access checks, audited changes, restricted deletion, and cycle prevention.
- Require the prerequisite's latest execution to succeed or be manually resolved on each selected server; missing servers and all other outcomes block queuing. Manual-resolution acceptance was added in 19.0.4.12.6 (see the September 29 entry).
- Preserve server selection and reject mixed selections atomically at Queue, without dependency errors during selection.
- Enforce the same dependency during failure retries, conflict confirmation, and runner launch while preserving monitoring of started executions.
- Finish idle runs when only dependency-blocked executions remain; retain Queued jobs for explicit Resume Monitoring after the prerequisite succeeds or is manually resolved.
- Hide inaccessible prerequisite details in errors without granting additional request access.
- Document the workflow, append seven POT-derived entries to both Arabic catalogs, and bump the module to 19.0.4.10.0.

Validation: fresh installation and targeted `ab_deploy` upgrade passed in isolated database `ab_deploy_dependency_validation_20260926`, without module errors. Passed 62 dependency checks, 32 existing conflict regression checks, and four Arabic/runtime checks. These cover all prerequisite statuses, missing and mixed servers, latest successful retries, selection preservation, retry and conflict bypasses, runner launch and idle behavior, monitoring, cycles and chains, approval immutability, restricted visibility, and archived prerequisites. Both catalogs passed `msgfmt --check-format`; `ar_001` field labels, form differences, and error/status translations were verified at runtime. Tests rolled back their fixtures and mocked remote SSH. Test scripts and results remain in `/tmp/ab_deploy_dependency_*`, outside the production addon. No live database upgrade or service restart was performed.

Files changed:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/models/dependencies.py`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/batch.py`
- `ab_deploy/wizard/conflict.py`
- `ab_deploy/views/dependency_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-26-request-dependencies.md`
