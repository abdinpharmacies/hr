# Deployment details in batch notifications

Commit: uncommitted (module has no committed history)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Put the deployment request name, title and multiline description above queued/completed batch details.
- Display “Not provided” for an empty description; preserve approval messages and existing outcome details, routing and deduplication.
- Bump version to 19.0.1.0.1 and merge new labels into both Arabic catalogs using an Odoo-exported POT.

Validation: targeted ab_deploy_telegram upgrade on deploy19 exited 0 with no ERROR/CRITICAL/traceback in /tmp/telegram_batch_header_upgrade.log. Arabic view translation verified in a rolled-back transaction. Restarted the main service and the idle queue runner. No Telegram notifications sent. msgfmt is unavailable on this host.

Files changed:

- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/changelog.d/2026-09-17-batch-header.md`
