# Complete deployment reports

Commit: uncommitted (module has no committed history)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Add Send Deployment Report to request forms for executors and deployment administrators, with server-side access enforcement.
- Use one report builder for manual reports and automatic batch completion; stop approval and queued-batch notifications.
- Summarize every target's current status, including successes from earlier batches, and attach a UTF-8 Arabic Markdown table using actual server serial, name, area and status.
- Sort succeeded, failed, delayed, cancelled and unfinished targets; right-align columns, escape cell delimiters and preserve full descriptions through existing text splitting.
- Queue text and document atomically and in order; deduplicate automatic completion reports and allow deliberate fresh manual reports.
- Update documentation, both Arabic catalogs and version 19.0.1.1.0.

Validation:

- Targeted module upgrade on deploy19 passed; no real Telegram calls were made.
- Rolled-back validation with scheduling disabled confirmed the manual button, summary/document order, Arabic attachment contents, automatic deduplication and suppression of approval/queued events.
- Current request report covered all 57 targets (5 succeeded, 52 delayed), including earlier successes.
- Verified Arabic view translation in a rolled-back transaction. msgfmt is unavailable on this host.
- No messages or test attachments were committed. Deployment runs were not executed or replayed.

Files changed:

- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/views/deployment_views.xml`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/changelog.d/2026-09-17-complete-reports.md`
