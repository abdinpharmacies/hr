# Float-only journal contract (Odoo 19)

Purchase and sales adapter owners must call `env['ab_accounting_je_header'].post_journal(request)` inside the transaction that finalizes the business document. Delegated journal inheritance is retired. This module contains no purchase or sales adapter, historical replay, automatic opening, or activation of adapters.

## Request

```python
journal = env['ab_accounting_je_header'].post_journal({
    'origin_database': env.cr.dbname,       # stable source database identifier
    'operation_identity': 'purchase:42:receipt:1',  # stable operation/event identity
    'company_id': company.id,
    'branch_id': store.id,                 # existing ab_store record
    'doctype_id': document_type.id,
    'event_type': 'receipt',
    'source_reference': 'PO/0042',
    'source_model': 'your_business_model',  # optional; provide together with source_res_id
    'source_res_id': document.id,
    'accounting_date': '2026-09-24',
    'original_event_reference': False,     # optional originating event identity
    'reference': 'Receipt of PO/0042',     # optional description
    'lines': [
        {'account_id': debit_account.id, 'partner_id': partner.id,
         'costcenter_id': costcenter.id, 'explain': 'Receipt of goods',
         'doc_no': 'PO/0042', 'due_date': '2026-10-24',
         'debit_val': 125.50, 'credit_val': 0.0},
        {'account_id': credit_account.id, 'partner_id': partner.id,
         'explain': 'Supplier liability', 'doc_no': 'PO/0042',
         'due_date': '2026-10-24', 'debit_val': 0.0, 'credit_val': 125.50},
    ],
})
```

Required top-level keys: `origin_database`, `operation_identity`, `company_id`, `branch_id`, `doctype_id`, `event_type`, `source_reference`, `accounting_date`, and `lines`. Optional keys are shown above, plus `opening_run_id` for a manually controlled opening run. Unknown keys are rejected.

Each line accepts only `account_id`, `partner_id`, `costcenter_id`, `explain`, `doc_no`, `due_date`, `debit_val`, and `credit_val`. The header supplies company, store (branch), document type and accounting date. `branch_id` is the existing `ab_store` ID; there is no accounting branch mapping. Stores are shared reference data, while journals, periods and opening runs carry their own company. Partners and cost centers are optional unless required by the account; descriptions and active posting accounts are required. Adapters resolve their own account mappings.

Amounts are Python `float` or `int`, stored as `fields.Float(digits=(16, 2))`. There is **no currency argument, configuration, conversion or monetary widget**. Non-finite values, negatives, material excess precision, both debit and credit on a line, and absolute amounts at or above `10**14` are rejected before ORM rounding. Binary representation noise such as `0.1 + 0.2` is accepted. Totals use `float_compare(..., precision_digits=2)`; a one-cent difference fails. No balancing lines or amount clamping are added.

The result is the posted journal recordset in the caller's environment. A matching authorized retry returns the same record. The canonical SHA-256 fingerprint includes source, event identity, company, branch, document type, accounting date, opening run, references, account/dimension IDs, due dates, descriptions and two-decimal amounts. Line order and omitted zero amounts do not change the meaning. Reusing an identity with different content fails. The database also enforces identity uniqueness across all branches.

## Authorization and transaction boundary

- Accountant users need explicit store assignments in Accounting Branches, account/document authorization and creator access. Manager/Admin and Auto JE bypass those restrictions, but never authorized companies or accounting integrity.
- Auto JE permits creating and posting journals, including generated business entries. It does not grant configuration management or reviewer authority.
- Do not call the service using unrestricted `sudo()` to work around a missing role. Use a dedicated integration user assigned Auto JE and the necessary company access.
- Do not commit before or inside accounting. Propagate posting failures so the caller rolls back the business operation too. The service uses savepoints to avoid leaving partial journals; it cannot undo business changes that the caller deliberately commits after swallowing an exception.
- Branch coordination rows are locked and versioned before journal mutations, posting, period closure and opening closure. Configuration used in posting is locked against concurrent edits. PostgreSQL serialization errors and Odoo `ConcurrencyError` must trigger retry of the **entire business transaction**, with the same identity. Odoo's standard RPC transaction wrapper does this; standalone workers must implement the equivalent outer retry. Never retry only the accounting fragment or reuse an aborted cursor snapshot.
- Only private implementation methods bypass public workflow field guards. No caller-provided context flag grants a posting or editing bypass.

## Manual posting and reversals

Native draft creation/import assigns a stable `manual:<UUID>` operation identity. `action_post()` uses the same financial validation and transition as generated journals; `btn_post_je()` remains a wrapper. Posted headers and items cannot be financially edited, deleted, reparented or archived, including by Admin, Auto JE or `sudo()`.

`action_reverse(date, reason)` posts a new full reversal in an open period and returns it. The original is preserved and can have only one full reversal. Reversals cannot themselves be reversed through this action. Journals with business source links or an event type other than `manual`/`opening` reject this public action.

A future adapter may use private `_reverse_from_source(source_record, date, reason)` after validating and reversing its own business workflow inside the same transaction. It requires Auto JE, write access to the exact local source, and matching source identity. It is deliberately unavailable through RPC. The adapter remains responsible for its business state and idempotent retry behavior; real adapter integration is a later acceptance gate.

Source navigation opens only a local, existing, readable record and checks represented company/branch fields. External database references never navigate to coincident local IDs.
