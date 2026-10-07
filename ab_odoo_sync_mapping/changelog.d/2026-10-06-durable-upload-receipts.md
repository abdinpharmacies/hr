# Durable branch upload receipts

Recent relevant commit: `13cd8c6aad619aa4a7afabb1cf4bef8896ecf1a9`
Author: emadco88-report-server
Date: 2026-09-27
Original subject: ab_odoo_sync_mapping/ FIX accept the branch token for 15 min by default

- Preserve the deployed token authentication and sticky hardware authorization.
- Inspected this commit and the current working diff before this update.

Current changes before commit:

- Save immutable, branch-scoped original upload receipts before acknowledging delivery.
- Process mapping/application separately; retain mapping failures centrally.
- Accept and quarantine invalid metadata and protected models without applying them.
- Deduplicate exact retries; preserve old revisions and quarantine conflicting event IDs.
- Return a retryable storage error when durable receipt cannot complete.
- Add administrator receipt history and processing recovery, without automatic backlog replay.
- Add English documentation and Arabic translations for both supported language codes.

Validation:

- Fresh isolated installation and targeted upgrade passed on report-server.
- 34 receipt checks passed, including metadata quarantine, identity isolation, immutable storage, revision ordering, and terminal processing recovery.
- Seven authenticated HTTP checks passed; actual queued receipt execution and three simulated storage/commit outcomes passed.
- Exported the Odoo POT, checked both PO files with msgfmt, and verified Arabic action, field, and selection translations at runtime.
- Backed up report19 and upgraded only this module to 19.0.1.6.0; both production Odoo services are active.
- Production pilot on abdin-187: existing job 131015 completed, and its two failed outbox uploads became Sent.
- Receipt IDs 1848 and 1849 preserve those uploads; mapping ValidationError remains visible centrally without rejecting branch delivery.
- No bulk backlog recovery was performed. Validation scripts remain outside the addon in /opt/odoo19/validation/sync_receipts.

Files changed:

- `__manifest__.py`
- `README.md`
- `controllers/report.py`
- `models/__init__.py`
- `models/ab_odoo_sync_mapping_service.py`
- `models/ab_odoo_sync_upload_receipt.py`
- `security/ir.model.access.csv`
- `data/queue_jobs.xml`
- `views/receipt_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-06-durable-upload-receipts.md`
