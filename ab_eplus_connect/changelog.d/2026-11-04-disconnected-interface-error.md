# Reconnect a closed SQL Server session

## Current changes before commit:

- Recognize the exact `Not connected to any MS SQL server` interface error as a disconnected session. The existing connection proxy can then reopen the connection and retry once instead of reusing the dead session.
- Keep the existing retry limit and error propagation. Other query errors do not trigger reconnection.
- No new user-facing strings, SQL writes, schema changes, or permission changes.

Files changed:

- `ab_eplus_connect/models/ab_eplus_connect.py`
- `ab_eplus_connect/tests/__init__.py`
- `ab_eplus_connect/tests/test_reconnection.py`
- `ab_eplus_connect/changelog.d/2026-11-04-disconnected-interface-error.md`

Validation:

- Targeted `ab_eplus_connect` upgrade on isolated `codex_eplus_sync_20261104` succeeded; 5 tests passed, 0 failures/errors.
- Covered string/bytes classification, reopening for cursor creation and execution, propagation after one failed retry, and no retry for unrelated query errors. External connections were mocked; no external writes were made.
- No English/Arabic UI strings changed. Python test imports and whitespace checks passed.
- No operational database update or Odoo process restart. Existing workers must reload the code to use the correction.
- Development tests remain outside runtime deployment packages.

## Relevant prior commit

Commit: `e91f6412dc0f3ebcce931927ba57703dbe46d271`
Author: emadco88
Date: 2026-03-30
Original commit subject: `Initial commit`

- Introduced the connection proxy and its bounded reconnect behavior.

Files changed relevant to this correction:

- `ab_eplus_connect/models/ab_eplus_connect.py`
