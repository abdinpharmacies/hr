# Target server code column

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Display read-only Server Code before Server in both target lists, retaining the 80-row page size.
- Read the code directly from the linked server through a related field.
- Add Arabic translations in both catalogs using the exported module POT.

## Validation

- XML syntax valid; restarted odoo19.service and upgraded ab_deploy on deploy19.
- Final upgrade exited 0 with no ERROR/CRITICAL/traceback entries. Service is active.
- Existing duplicate Target Servers label warning remains; no additional functional tests run.

Files changed:

- `ab_deploy/models/deployment.py`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-target-server-code.md`
