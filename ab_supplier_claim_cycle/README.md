# Supplier Claim Cycle

Version: 19.0.3.0.0 · Odoo 19 · Developer: Alhassan Hossny

## Installation

This release targets a fresh installation on an empty database. Install
`ab_supplier_claim_cycle` with its declared dependencies: `base`, `mail`, `web`,
and `ab_supplier`. No demo data is provided. Do not upgrade an existing claims
database to this baseline; database cleanup is a separate operation requiring approval.

## Supplier and classifications

Each claim references `ab_supplier` directly. Select an active supplier and enter
invoice count, area, claim amount, invoice type, and optional Secretarial notes.
Payment nature, tax type, and section are read-only supplier values on the claim.
The first submission reads the current supplier values and freezes payment nature,
business category, tax type, section, and any selected bracket terms. Changes to
supplier data afterward do not alter a submitted claim or its resubmission route.
Empty optional tax type or section remains empty. Claims never save preferences
back to the supplier.

Supplier Bracket is optional. Its ownership is validated through the supplier's
`costcenter_id`, because brackets belong to cost centers in `ab_supplier`.
Bracket terms do not calculate or change the entered claim amount.

## Workflow

States: `draft`, `inventory`, `purchasing`, `supplier_accounts`, `bank_accounts`,
`returned_secretarial`, `ready_to_close`, `closed`.

- Non-cash: Draft → Inventory → Purchasing → Supplier Accounts → Bank Accounts
  → Ready to Close → Closed.
- Cash: Draft → Supplier Accounts → Ready to Close → Closed.
- Each department approves, rejects, or defers its current review.
- Rejection requires a reason and returns the claim to Secretarial. Resubmission
  resumes the rejected stage; completed earlier approvals stay intact.
- Deferral requires a reason and a follow-up date today or later. The claim stays
  at the current department until it decides again.
- Supplier Accounts and Bank Accounts can upload their own optional cheque
  attachments while their review is pending or deferred.
- Secretarial closes claims only when ready to close and can archive/restore
  claims. Closed or archived claims cannot otherwise be edited. Claims, suppliers,
  and history are not physically deleted through the workflow.

## Permissions and history

Assign Secretarial, Inventory, Purchasing, Supplier Accounts, Bank Accounts,
Reviewer, or Administrator from user settings. Department users see their current
reviews and records they already reviewed; they may edit only the notes,
follow-up date, and evidence permitted at their current stage. Reviewer is
read-only. Administrators can perform department actions, but must follow the same
state transitions. Direct state/decision writes and forged context values are rejected.

The shared Claims menu uses record rules for visibility. Stage History records
notes, department decisions, resubmission, closure, archival, and restoration,
including actor, time, and classification snapshots. History is immutable.

## Verification

Use an isolated empty database with the required addons paths configured:

```bash
odoo-bin -c /path/to/test.conf -d supplier_cycle_test \
  -i ab_supplier_claim_cycle --without-demo=all \
  --test-enable --test-tags=/ab_supplier_claim_cycle \
  --stop-after-init --no-http --max-cron-threads=0
```

The suite covers both routes, every department, rejection and deferral,
resubmission, evidence, closure, archival, supplier snapshots, bracket ownership,
read/write security, and Odoo 19 view validation.

Validated on an empty Odoo 19 test database: 33 tests passed, zero failures or
errors. Python, XML, and Arabic translation syntax checks also passed.
