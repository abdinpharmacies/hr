Recent relevant commit:

- Commit: `caf816a`
- Author: emadco88
- Date: 2026-09-03
- Original subject: ab_transfer: clean report sync fields
- User-facing changes:
  - Cleaned transfer passive models for report-server sync fields and optional payload handling.
- Files changed:
  - ab_transfer/__manifest__.py
  - ab_transfer/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_transfer/models/ab_transfer_header.py
  - ab_transfer/models/ab_transfer_line.py
  - ab_transfer/models/ab_transfer_receive.py
  - ab_transfer/models/ab_transfer_request.py

Current changes before commit:

- User-facing changes:
  - Disabled Odoo log access on the six high-value transfer passive models so `create_uid` and `write_uid` come from the passive `ab_users` mirror fields.
  - Added unique `(db_serial, rec_id)` constraints to transfer passive models so upload apply can safely upsert by source identity.
  - Added `active` archive flags to transfer passive models so archive upload events mark rows inactive instead of failing queue jobs.
- Files changed:
  - ab_transfer/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_transfer/i18n/ar.po
  - ab_transfer/i18n/ar_001.po
  - ab_transfer/models/ab_transfer_header.py
  - ab_transfer/models/ab_transfer_line.py
  - ab_transfer/models/ab_transfer_receive.py
  - ab_transfer/models/ab_transfer_request.py
