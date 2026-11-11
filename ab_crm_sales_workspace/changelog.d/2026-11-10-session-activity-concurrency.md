# Session activity concurrency

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.25.1 avoids retry delays and SQL error logs when another request commits only the optional chatter activity timestamp after the current transaction's snapshot.
- Attempt the existing nonblocking row lock inside a non-flushing savepoint. Roll back only that lock attempt on serialization failure, preserving previous request writes. Timestamp updates still use ORM in the request transaction.
- Compare the session's identity, scope, state and lifetime against a fresh read-only cursor before skipping a conflict. Concurrent logout, expiry or other session changes still propagate to Odoo's native retry and authorization checks. The helper is private and is called after staff, token, user, company, expiry and employee eligibility checks.
- The parameterized lock query uses the cursor's per-query `log_exceptions=False` because the native ORM locking helper cannot suppress an expected lock conflict. Other exceptions still propagate; no global logging changes or monkey patches are used.
- Preserve the one-minute activity interval, existing English UI strings, both Arabic catalogs, session lifetime and unrelated worktree changes.
- Extend the real PostgreSQL concurrency runner and adapt the existing session tests to the private lock helper.

Files changed for this increment:

- `__manifest__.py`
- `models/session.py`
- `tests/session_concurrency.py`
- `tests/test_workspace.py`
- `changelog.d/2026-11-10-session-activity-concurrency.md`

## Validation

- Reproduced the original serialization error before changing the implementation.
- Eight independent-transaction PostgreSQL tests passed, including activity overlap, competing commit, holder rollback, previous-write preservation, logout and expiry. The activity-only request completed in one attempt without an SQL error log.
- Targeted workspace upgrade and six session/access tests passed with zero failures/errors on `crm_session_fix_test_20261110`, cloned from the existing isolated `crm_session_fix_test_20261109` database. Ports 5069/5072, no HTTP, workers/cron disabled; logs in `/tmp/chatter-session-race-20261110/`.
- Four Python files parsed, both Arabic catalogs passed `msgfmt --check-format`, and runtime packaging excludes tests, test asset declarations and caches. No UI strings changed.
- The clone lacks historical filestore attachments and has existing configuration/manifest warnings; these did not fail the selected tests. Browser workflows and production-load performance were not tested.
- The live callcenter database and user-managed process were not changed by validation. Reload the callcenter Python process to activate this source fix; no live schema migration is needed for this increment.
