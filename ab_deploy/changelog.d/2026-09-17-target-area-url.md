# Target server area and Odoo URL

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Show read-only Area and Odoo URL after Server in both target lists, retaining 80 rows per page.
- Use the standard URL widget to open server links in a new tab.
- Add field references to existing Arabic translations in both catalogs using the exported POT.

## Validation

- XML syntax valid. Restarted odoo19.service and upgraded ab_deploy on deploy19.
- Final upgrade exited 0 without ERROR/CRITICAL/traceback entries; service is active.
- Existing duplicate Target Servers label warning remains. No additional functional tests run.

Files changed:

- `ab_deploy/models/deployment.py`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-target-area-url.md`
