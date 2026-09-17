# ab_branch_api: automatic bill recovery

## Recent commit

Commit: `8838ef7fb94e7951dc1d54cbbef5d585f46e6677`

Author: Hossam Elsheikh

Date: 2026-09-17T10:47:51+03:00

Original commit subject: ab_branch_api: restrict bills and returns to call-center-created orders

- Restrict branch bill browsing and returns to callcenter-created records.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-callcenter-only-bills.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/callcenter_origin.py`
- `ab_branch_api/models/callcenter_services.py`
- `ab_branch_api/views/api_views.xml`

## Current changes before commit:

- Reconcile interrupted sales and returns inside the branch API; callcenter continues to use API methods only.
- Reuse the original sale draft, lines, prices, token and payload hash after proven rollback; return confirmed transaction IDs without another stock/cash post.
- Commit API return stock/cash, replication entries and repricing atomically by deferring intermediate commits until all inherited business methods succeed on one SQL connection. Preserve ordinary branch posting outside API requests.
- Persist generated sale/return identifiers before external commit. Serialize submissions across PostgreSQL commits and SQL sessions, then roll back unfinished work and release both locks at request cleanup.
- Add an authenticated, store/user-scoped reconciliation endpoint and advertise it in capabilities. Preserve read-only operation status and existing customer safeguards.
- Recover legacy uncertain sales when committed branch-scoped evidence permits; block inconsistent facts, old active workers and legacy returns without adequate commit evidence.
- Document branch-first deployment and maintain English/Arabic pairs in both translation files; bump to 19.0.5.3.0.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-automatic-bill-recovery.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/__init__.py`
- `ab_branch_api/models/branch_api.py`
- `ab_branch_api/models/reconciliation.py`
- `ab_branch_api/models/routing.py`

Validation:

- Targeted upgrade on disposable database `codex_callcenter_origin_branch`; no live deployment or external database writes.
- Real ORM and PostgreSQL journal/lock checks with mocked external transactions: validation failure, failure before commit, rejected commit, lost commit response, failure after commit, concurrent retries, interrupted worker recovery, identical replay, payload mismatch, cross-branch isolation, archived draft recovery, partial/duplicate sale evidence, return payment/finance evidence, and failures in the later replication/repricing phases without an early external commit.
- Runtime Arabic operation labels/action; PO format, Python syntax and diff checks.
- Validation scripts and results remain outside addons in `/tmp/branch_reconciliation_validation`.
