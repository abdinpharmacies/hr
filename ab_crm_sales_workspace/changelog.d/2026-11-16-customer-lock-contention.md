# Contact linking and refresh lock contention

Current changes before commit:

- Check explicit inactive/conflicting identities before automatic linking takes a branch lock, so refresh does not repeatedly lock identities deliberately unlinked by staff.
- Roll back and skip busy automatic-link attempts without failing inbox, conversation or notification refresh.
- Mark manual link/unlink lock conflicts for Odoo's bounded request retries. Keep branch/company authorization, group conflict review and fresh preview fingerprints; rejected unlink attempts roll back atomically.
- Cover busy branch/account locks, refresh rollback, denied callers, explicit unlink retention and manual retries with focused tests and deterministic PostgreSQL overlap tests.

Files changed:

- `__manifest__.py`
- `models/customer_streams.py`
- `tests/__init__.py`
- `tests/test_customer_locking.py`
- `tests/customer_lock_concurrency.py`
- `changelog.d/2026-11-16-customer-lock-contention.md`
