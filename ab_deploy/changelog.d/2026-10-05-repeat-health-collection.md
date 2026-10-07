# Repeat approved health collections

Commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Retain the existing execution, permission, and conflict workflows when collecting health reports again.

Files changed in that commit relevant to this feature:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/jobs.py`

## Current changes before commit:

Author: emadco88
Date: 2026-10-05 (UTC)
Commit: uncommitted

- Add Run Selected Health Checks and Select All for Health Collection to approved health requests. Reselect completed idle servers and collect again without copying the request or obtaining another request approval.
- Allocate a fresh execution key, job, and report per selected server per run. Preserve earlier execution settings and reports; keep the originally approved server list and assigned executor restrictions.
- Block overlapping health executions, unknown executions, incomplete output collection, and active monitoring queue runs. Preserve maintenance, dependency, conflict, and ordinary deployment behavior.
- Reuse the existing red Update Commands button for idle completed health targets. Require the existing administrator preview/reason confirmation when scripts or resolved parameters change; keep prior snapshots and avoid a second request approval.
- Refresh command-update availability when default parameter values or names change.
- Add English source labels and translations in both Arabic catalogs, document repeated collection, and bump the module from 19.0.4.14.0 to 19.0.4.14.1.
- Preserve the pre-existing uncommitted health-collection and deployment features documented in their own changelogs. This entry describes only repeat-collection changes.

Files changed:
- `ab_deploy/README.md`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/models/deployment.py`
- `ab_deploy/models/health_report.py`
- `ab_deploy/models/jobs.py`
- `ab_deploy/models/script_revisions.py`
- `ab_deploy/views/health_report_views.xml`
- `ab_deploy/changelog.d/2026-10-05-repeat-health-collection.md`

Validation:
- Passed 48 repeat-execution, permission, revision, queue, maintenance, parameter, and view checks in the isolated database, plus 46 health-report ORM/security and 26 parser/renderer regression checks. Temporary tests remain outside the addon and execute no SSH commands.
- Exported the module POT, merged seven new translations into each Arabic catalog, validated both with msgfmt, and verified English/Arabic button labels at runtime.
- Backed up the idle collector, upgraded only ab_deploy in deploy19, and restarted its Odoo and queue-runner services. Both services are active; local and public support login pages return HTTP 200. Runtime confirms version 19.0.4.14.1; no pilot collection was executed.
