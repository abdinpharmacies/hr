# Per-request Telegram notification preference

Commit: e7173aa1e667f45c3c2450b15b953f69b789c973
Author: emadco88
Date: 2026-09-22
Original commit subject: ab_deploy_telegram/ Add audited manual resolution and admin undo for failed deployments; update statuses, sorting, and Telegram reports

- Preserve the existing complete deployment reports, manual-resolution counts, and ordering.

Files changed in that commit:
- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/changelog.d/2026-09-22-manual-resolution.md`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/models/deployment.py`

## Current changes before commit:

Author: emadco88
Date: 2026-10-05 (UTC)
Commit: uncommitted

- Add Send Telegram Notifications beside the request title, checked by default for new and existing requests. Copies start checked.
- Allow the owner, assigned approver, assigned executor, and administrators to change this preference at every stage, including during execution. Preserve company rules and approved request settings; track changes in chatter and audit history.
- Suppress future automatic batch-completion reports when unchecked. Keep existing queued reports and manual sending available; rechecking does not trigger past events.
- Serialize the saved preference check with request changes before building automatic notifications, retaining routing and duplicate protection.
- Add four translations in both Arabic catalogs from an exported POT, document the preference, and bump the module from 19.0.1.2.0 to 19.0.1.3.0.

Files changed:
- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/views/deployment_views.xml`
- `ab_deploy_telegram/changelog.d/2026-10-05-request-notification-toggle.md`

Validation:
- Fresh isolated installation passed. Passed 87 rolled-back toggle, stage, permission, company, manual/automatic reporting, execution, copy, and form checks with Telegram enqueueing and SSH mocked; no real test notifications were sent.
- Both Arabic catalogs passed msgfmt checks; runtime verified the checkbox label and form translation differ from English.
- Backed up the idle collector and upgraded only ab_deploy_telegram to 19.0.1.3.0. All 31 existing requests default to enabled. Both collector services are active, and local/public login pages return HTTP 200; no upgrade errors or fixture metadata remain in production.
