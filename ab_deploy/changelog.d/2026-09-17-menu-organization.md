# Deployment menu organization

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Keep Deployment Requests directly under Deployment Manager.
- Group Servers and Command Catalog under Config.
- Group Import Servers CSV and Recover Deployment Jobs under Tools.
- Group Execution Jobs and Audit Logs under Reports.
- Preserve existing actions, menu IDs and access restrictions; add Arabic labels for the three new parent menus in both translation catalogs.

## Validation

- Changed menu XML files parsed successfully for XML syntax.
- Per user instruction, no tests, module upgrades, service restarts or runtime translation checks were performed.

Files changed:

- `ab_deploy/views/menus.xml`
- `ab_deploy/views/deployment_views.xml`
- `ab_deploy/views/execution_views.xml`
- `ab_deploy/wizard/server_import_views.xml`
- `ab_deploy/wizard/recovery_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-menu-organization.md`
