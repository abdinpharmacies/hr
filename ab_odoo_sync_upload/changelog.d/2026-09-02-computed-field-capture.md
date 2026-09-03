# Stored Computed Field Capture

## Recent relevant commit

- Commit: `dca01d86b6c006091d7054eb49e9a28a8c42e4f4`
- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-02
- Subject: `ab_odoo_sync_upload/ Capture stored compute flushes in upload hooks`
- Added transaction-scoped capture for stored computed-field recompute scheduling and flush writes.

Files changed:

- `ab_odoo_sync_upload/changelog.d/2026-09-02-computed-field-capture.md`
- `ab_odoo_sync_upload/models/ab_odoo_sync_orm_hook.py`

## Current changes before commit

- Documented edge cases for a complete stored computed-field capture test suite.
- Covered semantic recompute scheduling, low-level stored writes, collector deduplication, transactions, unlink/archive behavior, source configuration, payload serialization, safety, and performance regressions.

Files changed:

- `ab_odoo_sync_upload/doc/stored_computed_field_capture_test_edge_cases.md`
- `ab_odoo_sync_upload/changelog.d/2026-09-02-computed-field-capture.md`
