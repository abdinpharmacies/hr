# Supplier Claim Cycle

Version: 19.0.4.0.0 · Odoo 19 · Developer: Alhassan Hossny

## Installation

This release targets a fresh installation on an empty database. Install
`ab_supplier_claim_cycle` with its declared dependencies: `base`, `mail`, `web`,
and `ab_costcenter`. No demo data is provided. Do not upgrade an existing claims
database to this baseline; database cleanup is a separate operation requiring approval.

## Supplier and classifications

Each claim references `ab_costcenter` directly. Claim users can select cost centers
whose code starts with `1-`. Select an active cost center and enter invoice count,
area, claim amount, and optional Secretarial notes.

Invoice type, payment nature, tax type, and section default from the newest saved
claim for the selected cost center. Draft and archived claims are eligible sources.
If there is no previous claim, all four fields remain empty for manual entry.
Explicit values always override historical defaults. The choices stay on the claim
and are never written back to the cost-center master.

Submission uses the claim's chosen payment nature for routing. These choices cannot
be changed after submission, including when returned for correction. Supplier
brackets and business categories are not part of this module.

## Workflow

States: `draft`, `inventory`, `purchasing`, `supplier_accounts`, `bank_accounts`,
`returned_secretarial`, `ready_to_close`, `closed`.

- Bank transfer or check: Draft → Inventory → Purchasing → Supplier Accounts → Bank Accounts
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
resubmission, evidence, closure, archival, previous-claim defaults, cost-center
security, read/write security, and Odoo 19 view validation.

Follow-up dates default to today when entering or resuming a review stage and remain editable by its reviewer. Each deferral (orange) and rejection (red) stays visible as a separate timeline step after its department, including repeated decisions. Click a step label to reveal its date.
