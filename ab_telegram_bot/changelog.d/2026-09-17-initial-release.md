# Multi-bot Telegram messaging

Commit: uncommitted (new module; no previous commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Manage company-scoped bots, manually registered clients/groups, authorized users and disabled-by-default module subscriptions.
- Provide text/media/document/caption/edit/delete/forward/copy/reaction/chat-action APIs and bounded file downloads.
- Queue outgoing deliveries on root.telegram, snapshot uploads, preserve ordering, rate-limit and retry transient failures with durable send intent and explicit uncertain delivery handling.
- Protect tokens with administrator-only fields, masked inputs and export restrictions; omit secrets from queue arguments and transport error output.
- Add English UI and both Arabic catalogs exported from Odoo, setup/API documentation, and module-owned permissions.

## Validation

- Installed both modules on deploy19 and ran targeted upgrades using --no-http --stop-after-init.
- Corrected an initial Odoo 19 ir.module.module ondelete constraint; final upgrade exited 0 without ERROR/CRITICAL/traceback entries.
- Exported POT catalogs from the installed modules and populated ar.po and ar_001.po.
- No extra functional tests, real Telegram sends, bot credentials or group configuration were used.
- Existing duplicate Target Servers label warning in ab_deploy remains.

Files changed:

- `ab_telegram_bot/README.md`
- `ab_telegram_bot/__init__.py`
- `ab_telegram_bot/__manifest__.py`
- `ab_telegram_bot/data/queue_jobs.xml`
- `ab_telegram_bot/i18n/ar.po`
- `ab_telegram_bot/i18n/ar_001.po`
- `ab_telegram_bot/models/__init__.py`
- `ab_telegram_bot/models/bot.py`
- `ab_telegram_bot/models/message.py`
- `ab_telegram_bot/models/transport.py`
- `ab_telegram_bot/security/ir.model.access.csv`
- `ab_telegram_bot/security/record_rules.xml`
- `ab_telegram_bot/security/security_groups.xml`
- `ab_telegram_bot/static/description/icon.png`
- `ab_telegram_bot/views/telegram_views.xml`
- `ab_telegram_bot/changelog.d/2026-09-17-initial-release.md`
