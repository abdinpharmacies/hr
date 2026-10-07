# Bound SSH workers and recover interrupted claims

Commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Retain durable execution keys, queue conflicts, and administrator resolution from the existing runner.

Files changed in that commit relevant to this repair:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/models/batch.py`

## Current changes before commit:

Author: emadco88
Date: 2026-10-06 (UTC)
Commit: uncommitted

- Reduce SSH concurrency and claim capacity from 70 to eight. Warm every worker before claiming durable executions; clean up partially started pools on startup failure.
- Track every committed claim, including submissions that throw before a future is returned. Stop and join workers, drain received output without granting new launch intent, and reconcile every interrupted attempt.
- Restore confirmed unlaunched claims to queued. Preserve unknown status for launched executions, with an accurate worker-failure diagnostic instead of a misleading timeout.
- Clarify that cancelling failed Job Queue records does not resolve Deployment Execution Jobs; retain waiting-only cancellation and Check and Resolve.
- Add three translations to both Arabic catalogs from the exported POT, document recovery, and bump ab_deploy from 19.0.4.14.1 to 19.0.4.14.2. Preserve all pre-existing uncommitted features.

Files changed:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/batch.py`
- `ab_deploy/runner/threaded.py`
- `ab_deploy/wizard/conflict_views.xml`
- `ab_deploy/changelog.d/2026-10-06-runner-thread-recovery.md`

Validation and collector recovery:
- Passed five injected-failure/concurrency scenarios, 48 repeat-health workflow checks, 46 report ORM/security checks, and 26 parser/renderer checks. Temporary tests remain outside the addon and perform no remote test launches.
- Isolated targeted upgrade and both Arabic msgfmt checks passed. Collector runtime verified the translated conflict guidance and version 19.0.4.14.2.
- Backed up deploy19 before the targeted upgrade and bounded recovery. Both services are active and the public login returns HTTP 200.
- Read-only original-key probes confirmed 58 unlaunched execution directories absent. Cancelled those superseded executions with ORM audit notes, preserving all 59 prior successes and their reports. Request 66 was already cancelled and remained unchanged.
- Request 68 queued 57 distinct health jobs/reports. Branch abdin-78 remained unreachable; its earlier execution remains Unknown and its target is excluded until verified. No branch configuration or business data was changed.
- Live request 68 completed all 57 selected executions successfully with 57 complete reports; its queue run finished without a thread error. The active worker stayed below the configured memory limits with eight SSH workers.
