# Automatic deployment notifications

Commit: uncommitted (module has no committed history)
Author: emadco88
Date: 2026-09-17 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Remove the per-request notification checkbox; resolve notifications through the enabled company subscription.
- Preserve saved destinations and resolve missing destinations at submission or the next notification event, including existing approved requests.
- Record configuration failures without blocking submission, approval or execution; clear previous notes after successfully enqueueing an event.
- Keep overrides and existing event deduplication; do not replay past events or rerun deployments.
- Update help, documentation, Arabic catalogs and version 19.0.1.0.2.

Validation: targeted upgrade of ab_deploy_telegram on deploy19 exited 0 with no ERROR/CRITICAL/traceback in /tmp/automatic_telegram_upgrade.log. Rolled-back checks verified DEP-2026-00003 and a new in-memory request resolve the configured group, saved destinations remain unchanged, and the Arabic view differs from English. No Telegram calls or notifications were made. Restarted the queue runner after confirming no started/enqueued jobs. Both services are active. msgfmt is unavailable on this host.

Files changed:

- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/views/deployment_views.xml`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/changelog.d/2026-09-17-automatic-notifications.md`
