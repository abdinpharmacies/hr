# Report manually resolved servers

Recent relevant commit: 9e29ff88b3ce372bfb73d95529b72ddbbef7a738
Author: emadco88
Date: 2026-09-22
Original commit subject: ab_deploy_telegram/ UPD - UI and buttons and fetching i think
- Updated report status order and Arabic labels.

## Current changes before commit:

Author: emadco88
Date: 2026-09-22 (UTC)
Commit: uncommitted

- Count Manually Resolved separately from automatic successes in shared manual/automatic reports.
- Display تمت المعالجة يدويًا in Arabic Markdown tables and sort immediately before Succeeded.
- Document that resolution and undo do not automatically send messages; bump version to 19.0.1.2.0.

Validation: targeted upgrade passed; rolled-back report validation confirmed the distinct count and Arabic label, with no messages sent. Catalogs merged from exported POT files; msgfmt unavailable.

Files changed:

- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/changelog.d/2026-09-22-manual-resolution.md`
