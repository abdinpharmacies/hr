# Target server serial column

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Replace the target Server Code field and column with read-only Serial related to server_id.serial in both target lists.
- Preserve the 80-row page size and add target-field references to both Arabic translations from the exported POT.

## Validation

- XML syntax valid. Restarted Odoo and upgraded ab_deploy on deploy19.
- Initial upgrade encountered the previous saved view's server_code reference. Temporarily retaining that field allowed the view update; the field was then removed and the final upgrade succeeded.
- Final upgrade exited 0 without ERROR/CRITICAL/traceback entries. Existing duplicate Target Servers label warning remains.
- No additional functional tests performed.

Files changed:

- `ab_deploy/models/deployment.py`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-17-target-serial.md`
