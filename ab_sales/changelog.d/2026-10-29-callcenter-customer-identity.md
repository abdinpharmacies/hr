# Preserve callcenter customer identity on branch invoices

Recent relevant commit:
- Commit: `9d873dc70a36e52eaecf3bf04ebc7dd52025367b`
- Author: Alhassan Hossny
- Date: 2026-10-29
- Original commit subject: ab_sales/feat: improve store balance popup usability
- Added branch search, keyboard fallback, responsive RTL layout and refresh feedback.

Current changes before commit:
- Preserve the selected customer ID, including an accessible inactive customer, and require a positive integer E-Plus serial for that header relation only.
- Clear stale new-customer inputs and fill missing name, phone and address snapshots before validating a new attempt. Keep explicit snapshots and the selected invoice address; do not replace them with historical suggestions in the POS.
- Prefer populated snapshots in callcenter invoice responses. Retain frozen retry payloads, tokens and revisions; confirmed rejected legacy attempts recover through the existing new-draft workflow.
- Preserve the separate new-customer workflow, contract/account behavior and unrelated relation validation. Add the customer-reference validation message to both Arabic catalogs using the exported Odoo POT.

Files changed:
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-29-callcenter-customer-identity.md

Validation:
- 39 callcenter checks, 7 submit-dialog checks and 6 shared contract/runtime-translation checks passed. Coverage includes strict serials, access denial, partial snapshots, selected addresses, stale new-customer values, immutable retries and confirmed-rejection draft recovery.
- Signed-in English/Arabic customer and submit screens passed at 375/768/1280px, including selection, mocked submission, reopening, receipts, retries and draft recovery. The unchanged native invoice form has pre-existing overflow; the changed submit dialog does not.
- Targeted ab_sales upgrade on isolated identity_callcenter_validation_20261029 used ports 5269/5272 with cron disabled. Python/JS/XML syntax, both PO format checks and runtime translations passed.
- Deploy pos19 branch customer support before callcenter normalization. No deployment, schema migration, production posting or customer-master correction is included.
- Combined verification totals 174 focused checks; counts overlap across these feature notes and must not be added together. Scripts, screenshots and limitations: `/tmp/customer_identity_validation/RESULTS.md`.
