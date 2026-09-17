# Target server list page size

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Show up to 80 target servers per page in both draft and approved request lists.

## Validation

- XML syntax valid.
- Restarted odoo19.service and upgraded ab_deploy on deploy19 using the requested command, with a separate upgrade logfile.
- Upgrade exited 0 with no ERROR, CRITICAL or traceback entries; service is active.
- Existing duplicate Target Servers label warning remains. No functional tests run.

Files changed:

- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/changelog.d/2026-09-17-target-list-page-size.md`
