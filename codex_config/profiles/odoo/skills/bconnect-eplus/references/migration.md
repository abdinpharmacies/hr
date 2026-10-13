# E-Plus to Odoo Migration

Preserve `itm_id`, `itm_code`, `sto_id`, `sto_code` and source transaction IDs.
Map `eplus_serial` through verified local connector/model code; do not infer its
meaning from the field name alone. Keep branch/store in composite transaction
keys where identifiers can repeat. Barcode coverage is historically incomplete.

Use queued snapshots/imports, validation, idempotency and audit trails. Verify
name decryption, manufacturer/group/usage lookups, active state, unit factors,
batch/expiry/cost/price semantics and return quantities before bulk migration.
Reconcile by branch and unit, not only catalog-wide totals. Reject/quarantine
unmapped stores, ambiguous products and invalid conversions instead of guessing.

Keep external sources read-only by default. A requested production cutover needs
an explicit bounded scope, backup, reconciliation, rollback and responsible owner.
Use Odoo stock moves/receipts/adjustments for approved operational changes rather
than direct system quantity writes. Record source IDs on resulting business
operations and logs so retries and reversals can be traced.

Do not ship migrations/hooks solely to repair disposable development data or
XML-ID ownership. A lifecycle hook requires an explicitly requested, identified
deployed-production transformation. Keep the external schema repo as a reference,
never a vendored addon dependency.
