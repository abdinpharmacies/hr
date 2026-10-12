# Bill status refresh after a branch connection change

## Recent relevant commit (local bill handling excerpt)

- Commit: `ae0860f51f7a7121d055e50a1d3ea902405d5c25`
- Author: emadco88
- Date: 2026-10-12 13:48:22 +0300
- Original commit subject: ab_sales/ UPD add configurable draft slots and fix submission recovery
- Improved guarded bill updates, submission recovery, and POS session validation.

Files changed (relevant excerpt):
- `ab_sales/models/local_bills.py`

## Current changes before commit:

- Partition unfinished bills by their stored branch URL, database, database serial, and store serial before status refresh.
- Refresh bills matching the active connection even when older bills for the same store target a different destination.
- Skip mismatched bills and report their IDs using the existing translated branch-database-changed message. Preserve their original destination, token, revision, and status.
- Retain the unavailable warning for connection/response failures and all branch identity, token, and revision checks.
- Reuse the English source message already translated in both Arabic catalogs; no new user-facing wording or translation changes.

Files changed:
- `ab_sales/models/local_bills.py`
- `ab_sales/changelog.d/2026-10-12-status-refresh-destinations.md`

Validation:
- Odoo shell checks on `callcenter19` used existing mixed-destination bills with mocked remote RPC, locking, and final state writes; real recordset filtering and response validation executed.
- Passed mixed destinations, all matching, all mismatched (zero RPC), connection failure, incorrect branch identity, unrequested tokens, and stale revisions.
- Verified bill statuses, stored payloads, tokens, revisions, and branch invoice references remained unchanged; rolled back the shell transaction. No external requests or bill resubmissions.
- Both Arabic catalogs passed `msgfmt --check-format`; Python parsing and `git diff --check` passed.
- Validation script: `/tmp/test_callcenter_status_destination.py`; Odoo diagnostic log: `/tmp/callcenter-status-destination-test.log`.
- Restart the call-center Odoo workers to activate the Python change. No schema change or module upgrade is required; no live service restart performed.
