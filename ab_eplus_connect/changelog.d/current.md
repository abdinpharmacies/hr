# B-Connect connection change log

## Current changes before commit:

- Add an opt-in read connection helper with up to three connection attempts and short backoff for temporary connectivity failures.
- Allow five seconds for read connection checks and bypass cached failed probes during retries.
- Retry only opening the connection; never replay a caller's started operation. Existing connector callers keep their default timeouts and behavior.
- Preserve existing translated error messages and restrict retries to connectivity failures.

Files changed:

- `ab_eplus_connect/changelog.d/current.md`
- `ab_eplus_connect/models/ab_eplus_connect.py`
- `ab_eplus_connect/tests/test_reconnection.py`

Validation:

- Nine connector tests passed in `/tmp/eplus_replica_recovery_validation.log`, including bounded retries, no replay after yield, and immediate failure for permission/configuration errors. External connections were mocked.
- No new user-facing text or external SQL writes.

## Recent commit

Commit: `08114664`
Author: Mohamed Fawzy
Date: 2026-11-04
Original subject: `ab_eplus_connect/FIX: reconnect closed SQL Server sessions`

User-facing changes:

- Reopen a closed SQL Server session once for supported reads.

Files changed:

- `ab_eplus_connect/changelog.d/2026-11-04-disconnected-interface-error.md`
- `ab_eplus_connect/models/ab_eplus_connect.py`
- `ab_eplus_connect/tests/__init__.py`
- `ab_eplus_connect/tests/test_reconnection.py`
