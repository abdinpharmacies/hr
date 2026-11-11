Current changes before commit:

- Allow audited native invoice cancellations through enrollment without removing invoice history or changing submitted/posted flags.
- Continue blocking unresolved active sales, local stock allocations, payments and posted returns.
- Document evidence-based recovery of missing synchronization history and native cancellation workflows.

Files changed:

- ab_branch_sync/models/operation.py
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-11-enrollment-reconciliation.md

Verification and bounded development recovery:

- Five rollback-only Odoo checks passed on abdin_replica_branch19: pending invoices block, non-admin cancellation denied, 12 cancellations preserve audit, audited cancellations pass enrollment, and missing cancellation reason still blocks.
- Private full branch backup created and pg_restore listing verified before recovery.
- Compared remote central candidates against branch headers, ordered lines, units, prices, discounts, totals, stock quantities, chronology and existing journal mappings.
- Cancelled two matching unpaid central invoices through the public native cancellation action; verified exact reversal coverage for both original allocations.
- Cancelled 12 abandoned branch invoices through the native sales cancellation business method in a bounded recovery script. The branch enqueue wrapper was omitted only for these verified missing-journal records; no new transport operation was fabricated or replayed. All local financial, stock and approval checks ran.
- Normal Connect to Central succeeded: authorized=True, ready=True, connection_status=connected. One previously restored rejected invoice still requires employee/profile replication; it is not an enrollment blocker.
- No user-facing strings or translations changed. No database schema upgrade or server restart required for the recovery; running workers need the normal Python reload to pick up the persistent guard change.
- Development scripts and private backup/evidence remain outside the addon under /tmp.

Recent relevant commit:

- Commit: 41f1427058e7060e2faac22ca97632bf835ea4d6
- Author: Hossam Elsheikh
- Date: 2026-11-09
- Original subject: ab_branch_sync/before delivering an operation, it checks whether that operation’s store belongs to the branch’s currently configured replica. If it does not, delivery stops and the historical journal entry remains intact.
- User-facing change: preserve historical operations while preventing delivery for stores outside the current branch assignment.

Files changed:

- ab_branch_sync/models/operation.py
