# Manual incoming Telegram updates

Commit: uncommitted (new module; no previous module commits)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Add Fetch Updates beside Check Connection, an Incoming Updates inbox and a bot history smart button.
- Receive one batch of up to 100 updates per click, with immutable raw history, duplicate protection and a transactional offset.
- Reject webhook conflicts and duplicate local consumers without changing webhook configuration.
- Discover clients/groups, track private /start commands separately from observed group activity, and retain historical visibility after bot removal.
- Retry failed local processing without fetching or sending messages; prevent older retries from regressing newer profile/membership metadata.
- Add scoped permissions, English/Arabic labels and manual-fetch documentation; bump version to 19.0.1.1.0.

## Validation

- Restarted odoo19.service and upgraded only ab_telegram_bot on deploy19 with --no-http --stop-after-init.
- Final upgrade exited 0; /tmp/telegram_updates_final.log contains no ERROR, CRITICAL or traceback entries.
- Exported the installed module POT and merged new entries into both Arabic catalogs.
- Verified the Incoming Updates action displays Arabic with ar_001 in a rolled-back transaction; retained the database language configuration. Fixed missing Odoo module comments in newly merged translation entries.
- Restarted the queue runner after confirming no started/enqueued jobs; both Odoo services are active.
- No real Telegram calls or deployment executions were made for validation.
- msgfmt is not installed on this host; its format check could not run.

Files changed:

- `ab_telegram_bot/__manifest__.py`
- `ab_telegram_bot/models/__init__.py`
- `ab_telegram_bot/models/update.py`
- `ab_telegram_bot/security/ir.model.access.csv`
- `ab_telegram_bot/security/record_rules.xml`
- `ab_telegram_bot/views/telegram_views.xml`
- `ab_telegram_bot/views/update_views.xml`
- `ab_telegram_bot/i18n/ar.po`
- `ab_telegram_bot/i18n/ar_001.po`
- `ab_telegram_bot/README.md`
- `ab_telegram_bot/changelog.d/2026-09-17-manual-updates.md`
