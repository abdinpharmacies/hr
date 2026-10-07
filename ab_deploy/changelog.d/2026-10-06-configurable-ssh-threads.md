# Configure deployment SSH threads

Commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Preserve durable queue execution and administrator conflict recovery.

Files changed in that commit relevant to this feature:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/batch.py`

## Current changes before commit:

Author: emadco88
Date: 2026-10-06 (UTC)
Commit: uncommitted

- Add administrator-editable system parameter ab_deploy.ssh_threads with value 10 through noupdate XML data; module upgrades preserve edited values.
- Replace SSH_WORKERS with a per-batch ssh_threads value. Read it once before worker startup, use it for thread-pool size and claim capacity, and apply parameter changes only to subsequent batches without restarting services.
- Accept integers from 1 to 16; missing settings default to 10 and invalid settings fail before executions are claimed. Apply the setting to normal deployments and health collections.
- Retain prestarted worker pools and interruption recovery. Update operator instructions and both Arabic catalogs from the exported POT; bump ab_deploy from 19.0.4.14.2 to 19.0.4.14.3.
- Preserve the existing uncommitted features documented in earlier changelogs.

Files changed:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/data/config_parameters.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/batch.py`
- `ab_deploy/changelog.d/2026-10-06-configurable-ssh-threads.md`

Validation and rollout:
- Passed eight concurrency/startup/submission/recovery scenarios, including a 59-server simulation using ten threads, in-flight parameter changes, and rejection before claiming. Passed 16 parameter/default/XML checks, administrator-override preservation across an isolated upgrade, and Arabic validation at runtime.
- Both translation catalogs passed msgfmt; modified Python/XML and git diff checks passed.
- Backed up the idle collector, upgraded only ab_deploy to 19.0.4.14.3, and restarted both services. Runtime confirms the persisted and effective value is 10. Both services are active, the public login returns HTTP 200, and no deployment was launched.
