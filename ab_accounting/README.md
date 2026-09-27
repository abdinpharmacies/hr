# Branch Accounting for Odoo 19

Clean-install accounting with native drafts/import, immutable posted journals, manual opening reconciliation and secured PDF/XLSX reports. The retained journal models are `ab_accounting_je_header` and `ab_accounting_je_line`.

## Setup

1. Install `ab_accounting`. Its dependencies are `base`, `mail`, `ab_store`, `ab_costcenter`, and `report_xlsx`. Install without demo data. No HR, purchase, sales, legacy spreadsheet/helper module, hook, migration or cron is required.
2. An administrator assigns Accountant, Reviewer, Manager, Reports or Auto JE roles. In the user Accounting tab, assign **Accounting Branches**, an **Accounting Authorization Profile**, and any **Accounting Reviewer Responsibilities**. A user with no branch assignments has no ordinary journal access. A Reports user does not inherit Accountant.
3. Select an existing store directly in the journal Branch field. All active stores are available in the selector; no Accounting Branch setup or mapping is needed. Accounting Branches on the user form assigns existing stores for journal permissions. Stores are shared reference data; select the accounting company on journals, periods and opening runs. No shared store model is changed.
4. Create the account hierarchy and optional first/second-level classifications. A group account cannot accept posting and a posting account cannot have children. Configure required partner, cost center and due date dimensions. Create company-specific document types and authorization profiles. Account grants cover descendants; Prevent Enquiry hides the whole journal if it contains a forbidden account.
5. Create explicitly dated, non-overlapping periods for each company and store. Posting requires one matching open period. Managers close periods; reopening requires a recorded reason and records the user/time in addition to chatter.
6. Enter explicit balanced lines in native draft journals, or use native Odoo import for draft headers/items. The optional counterpart account never creates a balancing line. Post using the journal button.

Financial values display as ordinary two-decimal numbers. There is no accounting currency configuration. Automatic defaults never create opening or balancing journals.

## Roles

- **Accountant:** Create/edit own drafts and post within explicit scope; read required configuration dimensions.
- **Reviewer:** Accountant access plus access to assigned creators' journals; confirm, freeze and unfreeze those journals.
- **Manager:** Manage configuration and review all journals within authorized companies and branches.
- **Reports:** Read-only access within branch, account, document and assigned-creator scope; read required dimensions.
- **Auto JE:** Create/post across branches within authorized companies; read-only configuration access; no review authority.

System Admin inherits Manager and Auto JE. Ordinary read access requires a permitted document type, creator/responsibility access (or explicit Always Show grants for every account) and authorization for **every account in the journal**, including the optional counterpart. No partial line view or hidden total is returned. Reports users may receive creator responsibility assignments without gaining Reviewer or Accountant. Account names/configuration remain company-scoped reference data; cost centers have only the required read ACL, never additional write rights.

Review confirmation and freeze/unfreeze are audited on the journal. Unfreezing never makes posted amounts editable. After posting, only `review_note` may be changed through ordinary `write()` by an authorized reviewer; review actions and native chatter handle their own metadata.

## Manual openings

A manager creates an Opening Run with company, store, accounting date and reference, then records expected signed balances by account/partner/cost center. Enter balanced journals using its Opening Journals button. Expected balances do not generate journals. Each opening journal must match the run company/store/date.

Opening Reconciliation shows expected, posted actual and difference, including unexpected posted dimensions. Closing requires all included journals to be posted and every dimension difference to compare equal to zero at two decimals. Closed runs and their expected balances cannot be changed, and accept no further opening posting. Closing a run has no effect on adapter activation.

## Reports

Financial Reports provides general ledger, account statement, trial balance and opening reconciliation. Select company, branch, dates and optional account/partner/cost-center filters. PDF and XLSX use the same secured result builder. Journal Items also provides native list/search/pivot views restricted to posted lines; financial report data includes posted lines only.

Opening balances use all posted activity before the start date within the identical company/branch/dimension scope as period movement. Closing equals opening plus debit minus credit. Accounts with prior balances remain present without current movement, including archived accounts. Ledger running balances are per account/partner/cost-center and follow accounting date, posting number and line ID. Due date is a separate Journal Items analysis dimension, never the financial period date.

There are no report commits, elevated financial reads, arbitrary row limits or silent truncation. Large exports include all matching data and therefore need proportionate worker memory/time.

## Delivery boundary

See [POSTING_CONTRACT.md](POSTING_CONTRACT.md) for the Float-only adapter contract and [VALIDATION.md](VALIDATION.md) for verification evidence. This is a clean-install port, not a migration of deployed Odoo 15 data. Targeted upgrades are verified after installation of this port; do not interpret that as support for upgrading a legacy production database.
