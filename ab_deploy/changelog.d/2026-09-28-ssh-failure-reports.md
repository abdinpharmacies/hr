# Formatted SSH failure reports

Recent relevant commit: 2c0f1e76ef63ecebddc857f62081dd887a060a5f
Author: emadco88
Date: 2026-09-26
Original commit subject: ab_deploy/ Implemented and deployed ab_deploy 19.0.4.9.0.

- Retain deployment conflict controls and English/Arabic queue guidance.

Files changed (relevant module packaging and translations):
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`

## Current changes before commit:

Author: emadco88
Date: 2026-09-28 (UTC)
Commit: uncommitted

- Share one failure report between Test Selected SSH and individual Test SSH: tested/successful/failed counts and numerically sorted configured serials with server names.
- Post one internal request chatter note per test action containing failures. Show each server in bold red on its own line, followed by its translated reason. Omit the serial prefix when no serial is configured.
- Render the same layout in a sticky warning using a module-specific client action and XML template. Keep serials before server names in RTL layouts; allow scrolling for long popup reports.
- Escape all server names, serials and reasons. Keep existing authorization, threaded SSH checks, selections and deployment states. Successful tests and empty selections create no chatter note.
- Register frontend assets, bump to 19.0.4.12.2, document behavior, export POT and append the title translation to both Arabic catalogs without replacing existing entries.
- Earlier uncommitted dependency and command-update changes remain documented in `2026-09-26-request-dependencies.md` and `2026-09-28-script-revisions.md`.

Validation:
- Targeted upgrade passed in isolated `ab_deploy_dependency_validation_20260926` with no module errors.
- 22 mocked ORM checks passed: mixed/all-failed/success/empty results, single-server reports, missing serial, numeric sorting, chatter note count and sanitized styles, injection escaping, preserved state/selection, Arabic title/reasons and unauthorized access.
- 15 Chromium checks passed using the real Odoo OWL library and module XML template: separate lines, bold red styles in popup and persisted chatter HTML, escaped names, Arabic names, action registration, sticky warning and explicit serial direction.
- Both Arabic catalogs pass msgfmt format validation. Python/XML parsing and git diff whitespace checks pass.
- Tests live under `/tmp/ab_deploy_ssh_report_*` and `/tmp/ab_deploy_editor_browser/ssh_report_test.cjs`; ORM fixtures roll back and SSH is mocked. No real deployment or SSH test ran, and no live upgrade/restart was performed.

Files changed (SSH-report portion of the current working tree):
- `ab_deploy/models/deployment.py`
- `ab_deploy/static/src/js/ssh_failure_notification.js`
- `ab_deploy/static/src/xml/ssh_failure_notification.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/README.md`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-28-ssh-failure-reports.md`
