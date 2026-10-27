# Automatic queue control for incoming uploads

Recent relevant commit: `1a0282cbc17619acc773e996288d9e96bc0a5d53`
Author: emadco88-report-server
Date: 2026-10-07
Original subject: ab_odoo_sync_mapping/ FIX it should not refuse to receive any authnicated payload

Current changes before commit:

- Keep storing and acknowledging every authenticated upload; create receipt jobs only for active profiles with Automatically Queue Apply enabled.
- Enforce the same switch for retries, manual feeders, apply scheduling, and execution of existing queued jobs.
- Leave disabled or unconfigured receipts available for explicit processing after enabling their profile; never automatically enable generated profiles.
- Preserve partial application state when a profile is disabled, along with all receipts and sales data.
- Explain the switch and recovery behavior in English documentation and Arabic field help.
- Bump the module version to 19.0.1.6.1.

Validation:

- 34 focused checks passed against sync_receipts_test_20261006, with all test records rolled back. Script: /opt/odoo19/validation/sync_auto_queue/test_auto_queue.py.
- Targeted module upgrade passed on the isolated database.
- Both Arabic catalogs passed Babel parsing and message checks; git diff --check passed.
- Reloaded odoo19.service; preserved odoo19-queue-runner.service as inactive. No production module upgrade, configuration edits, backlog replay, or data deletion was performed.
- Verified production model eligibility read-only. Current settings disable sales headers as well as printer and employee-access models; sales lines and sales returns remain enabled.
- Recent production receipts show disabled models retained as Received and enabled sales-line receipts queued.

Files changed:

- `__manifest__.py`
- `README.md`
- `models/ab_odoo_sync_apply_profile.py`
- `models/ab_odoo_sync_mapping_service.py`
- `models/ab_odoo_sync_upload_receipt.py`
- `models/ab_odoo_sync_upload_record.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-26-automatic-queue-control.md`
