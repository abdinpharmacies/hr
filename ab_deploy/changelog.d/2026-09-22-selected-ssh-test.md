# Test selected servers through SSH

Recent relevant commit: f314539ceb829c0844e30d6070ef11aae5720715
Author: emadco88
Date: 2026-09-22
Original commit subject: ab_deploy/ UPD - Add audited manual resolution and admin undo for failed deployments; update statuses, sorting, and Telegram reports
- Added protected manual resolution and reporting.

## Current changes before commit:

Author: emadco88
Date: 2026-09-22 (UTC)
Commit: uncommitted

- Add Test Selected SSH alongside target selection controls, restricted to executors/admins.
- Check only selected targets concurrently using at most 70 threads and the existing SSH helper with true, alias configuration, bounded timeouts and existing host-key policy.
- Share plain result-code classification with the row-level SSH test; materialize records before threading and translate/report on the Odoo request thread.
- Return one notification with totals and failed server names/reasons; warn for empty selection and preserve selections/statuses.
- No wizard, model, queue jobs or stored connection results. Add Arabic translations and version 19.0.4.2.2.
- Row-level Test SSH changes remain documented in 2026-09-22-test-ssh.md.

Validation: mocked concurrent checks passed for partial/empty selections, timeout isolation, mixed/all-success results, unchanged record values, unauthorized access and row-level reuse. Arabic view verification passed in a rolled-back transaction. No real SSH or Telegram calls, deployments or committed validation data. msgfmt unavailable.

Files changed:

- `ab_deploy/models/deployment.py`
- `ab_deploy/runner/engine.py`
- `ab_deploy/views/request_targets_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-22-selected-ssh-test.md`
