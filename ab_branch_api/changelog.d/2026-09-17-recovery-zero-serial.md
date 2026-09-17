# ab_branch_api: prevent false recovery conflicts

## Recent commit

Commit: `b0fa3849ed753d365d442f7dd4d83c696e84103e`

Author: Hossam Elsheikh

Date: 2026-09-17T15:31:04+03:00

Original commit subject: ab_branch_api: automatically reconcile interrupted bill submissions

- Added branch-owned recovery, durable transaction evidence and serialized retries.

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

## Current changes before commit:

- Exclude zero/negative invoice IDs from the serial fallback when recovering a sale. An unrelated invoice zero must not block an unposted draft.
- Preserve marker/positive-serial, duplicate and transaction-completeness safeguards; report the operation reference and specific conflict reason.
- Log bounded recovery diagnostics and translate all new messages in both Arabic files.
- Document the correction and bump to 19.0.5.3.1.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-recovery-zero-serial.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/reconciliation.py`

Validation:

- Reproduced the exact prior conflict on a disposable Odoo database by evaluating the real SQL predicate with an unrelated zero-ID row in SQLite; the same case succeeds with the corrected predicate.
- Recovery suite passes for precommit failure, lost commit response, concurrent requests, interrupted workers, duplicate/incomplete records, positive serial with a wrong marker, branch isolation and atomic return replication/repricing.
- External SQL writes mocked; targeted disposable module upgrade, PO format validation and Arabic runtime diagnostics/action checks. No live records or stock were changed.
- Scripts and results: `/tmp/branch_recovery_diagnosis`.
