# B-Connect connection change log

## Current changes before commit:

- Retry timed-out SQL Server connection probes during E-Plus read operations, up to the existing three-attempt limit.
- Recognize SQL Server connection error codes 20002 and 20009 while leaving login failures non-retryable.
- Keep existing connector callers' default validation behavior and preserve translated error messages.

Files changed:

- `ab_eplus_connect/changelog.d/current.md`
- `ab_eplus_connect/models/ab_eplus_connect.py`
- `ab_eplus_connect/tests/test_reconnection.py`

Validation:

- Twelve connector tests passed in `/tmp/eplus_probe_retry_validation.log`, including probe timeouts, network errors, login rejection, bounded retries, and no replay after yield. External connections were mocked.
- No new user-facing text or external SQL writes.

## Recent commit

Commit: `a43c259e`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_eplus_connect/FIX: retry transient read connection failures`

User-facing changes:

- Retry transient failures while opening a read connection, without replaying started reads.

Files changed:

- `ab_eplus_connect/changelog.d/current.md`
- `ab_eplus_connect/models/ab_eplus_connect.py`
- `ab_eplus_connect/tests/test_reconnection.py`
