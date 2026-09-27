# Branch token reuse and configurable upload batching

Recent relevant commit: `ed9391d3cc43b06dcf20acde9cbff60c155341a9`
Author: Alhassan Hossny
Date: 2026-09-24
Original subject: ab_odoo_sync_upload: auto-discover branch disk serial \Body if you want a fuller commit:

- Preserved automatic hardware discovery and loopback-only serial overrides.
- Inspected this commit and the current working diff before this update.

Current changes before commit:

- Reuse expiring branch tokens in a restricted database record shared by workers.
- Coordinate refresh and serialize outbound uploads with nonblocking advisory locks.
- Refresh once for an expired/unknown token; reject revoked or mismatched credentials without automatic reauthentication.
- Configure batching through cached system parameter `ab_odoo_sync.upload_batch_delay_seconds`, default 5 seconds.
- Coalesce queued work per channel with a fixed deadline and collect pending events when execution starts.
- Preserve old queued-job signatures, event identities, revisions, and partial acknowledgements.
- Prefer live traffic to historical work; retry transient errors with bounded backoff and jitter and honor Retry-After.
- Retain a periodic recovery sweep for missed scheduling races; new installations enable the existing upload cron.
- Add rollback switch `ab_odoo_sync.use_branch_tokens`, Arabic translations, and restricted token ACLs.

Validation:

- Fresh installation and targeted upgrades passed.
- Model checks cover batching, parameter caching, send/refresh contention, and incomplete/partial acknowledgements.
- Real HTTP token exchange, reuse, expiration refresh, revocation, and bounded retry checks passed.
- Arabic fields and an existing action were verified at runtime with ar_001.
- Development checks are retained outside runtime addons in `/opt/odoo19/validation/sync_tokens`.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/ab_odoo_sync_client_token.py`
- `models/ab_odoo_sync_upload_service.py`
- `models/ab_odoo_sync_outbox.py`
- `data/system_parameters.xml`
- `data/crons.xml`
- `security/ir.model.access.csv`
- `views/configuration_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-09-27-token-batching.md`
