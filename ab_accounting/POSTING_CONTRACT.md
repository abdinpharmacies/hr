# Automated posting contract

`env['ab_accounting_je_header'].post_journal(values)` creates a draft and posts it
through the same validations as manual entry. It returns the journal record.
The caller must have Accountant ACLs, authorization to own the header account,
permission for every line account and permission for the document type.

Accepted keys (all mapped to original first-copy fields):

- `account_id`, `costcenter_id`, `store_id`, `doctype_id`
- `posted_date` (optional; defaults to today)
- `res_header_ref`, `res_header_id` (optional original source reference fields)
- `lines`: dictionaries containing `account_id`, `store_id`, `costcenter_id`,
  `due_date`, `settlement_date`, `doc_no`, `explain`, `debit_val`, `credit_val`.

Unknown keys are rejected. There are no supplier, partner, stock or tax fields in
this interface. No schema is added for operation identity, branch or company.
Adapters own their source linkage and retry policy; the purchase adapter reuses
its existing `purchase_accounting_journal_id` link on repeated posting.

Each line uses one non-negative amount with at most two decimal places. Active
lines must balance exactly at two decimals and include the header account and
cost center. Required store, due-date and cost-center rules follow the account.
Inactive or non-final accounts, forbidden stores and invalid cost centers are
rejected. Salary deduction and permitted negative-balance rules remain enforced;
only posted balances plus the current draft count toward posting validation.

Journal status fields must be changed through workflow actions. Client context
flags cannot bypass these checks. Posted line edits use the existing allowed-field
records and revalidate the whole journal atomically.
