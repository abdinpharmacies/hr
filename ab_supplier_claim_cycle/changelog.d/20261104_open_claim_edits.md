Current changes before commit:

- Allow Secretary and existing Administrator entry access to edit Section and the main attachment throughout active, open claims.
- Allow Tax Type edits until both Taxes and Supplier Accounts decisions are approved; enforce the lock in normal writes and private workflow writes used by administrator document replacement.
- Tax Type-only edits preserve every approval, the current stage, review/document revisions, and payment documents, including returned claims. No reviews reset because Tax Type changes are explicitly independent of workflow transitions.
- Administrator document replacement no longer resets financial reviews merely because Tax Type is supplied; its existing document-replacement safeguards and amount-change behavior remain unchanged.
- Keep Review Details and the Secretary attachment controls accessible throughout open stages. Apply the Tax Type lock to the administrator replacement dialog too.
- Preserve other roles' permissions, company rules, and closed/archived claim protection.
- Add role, form, upload, approval, multi-record atomicity, and closed/archived regression coverage.
- Translate the lock message and corrected default-value help in both Arabic catalogs.

Files changed:
- models/ab_supplier_claim_cycle.py
- views/supplier_terms.xml
- views/parallel_workflow.xml
- wizard/claim_decision.py
- wizard/claim_decision_views.xml
- tests/test_claim_cycle.py
- i18n/ar.po
- i18n/ar_001.po
- changelog.d/20261104_open_claim_edits.md

Validation of the final no-reset behavior:
- Targeted upgrade on isolated database supplier_claim_edit_20261104: 52 tests passed, zero failures/errors (/tmp/claim-no-reset.log), using this checkout, no HTTP, ports 5069/5072, workers=0, and cron=0.
- New regression cases cover Secretary/Administrator Tax Type changes across all seven open stages with either financial approval already granted, preserving every decision, current/resume stage, revisions, discount decision, and attached payment evidence.
- Existing tests still verify the combined approval lock, direct-write denial, administrator replacement dialog, and multi-record atomicity. Administrator document replacement with a Tax Type change preserves financial approvals.
- One unrelated stale test, test_tax_requirements_and_financial_parallelism, remains excluded because it expects the mandatory tax attachment removed in commit 3b456d1e.
- Python syntax, git diff whitespace checks, and both Arabic catalog format checks passed. No UI strings changed in this correction; earlier English/Arabic runtime checks still apply.
- No live database or running Odoo process was changed. Browser interaction remains unverified.

Validation of the initial implementation (superseded reset behavior):
- Fresh installation and targeted upgrade used isolated database supplier_claim_edit_20261104, this checkout's addons path, no HTTP, ports 5069/5072, workers=0, cron=0, and /tmp/claim-edit-data.
- The initial 51-test run found a corrected new assertion error and an existing failure in test_tax_requirements_and_financial_parallelism: it still expects mandatory tax attachments, removed by commit 3b456d1e. That unrelated test remains unchanged.
- Targeted upgrade rerun excluding that stale test: 50 tests, zero failures/errors (/tmp/claim-edit-upgrade.log).
- Final administrator replacement dialog upgrade/test: 1 test, zero failures/errors (/tmp/claim-edit-wizard.log).
- English and ar_001 runtime checks verified the lock message and field help; temporary validation records and language activation were rolled back. Both ar.po and ar_001.po passed gettext format checks; references were checked against an exported POT.
- Browser interaction was not exercised; Odoo Form tests cover field modifiers and role-specific views.

Manual test steps:
1. As Secretary, create a cash claim with Tax Type Tax Payment, submit it, then save changes to Section, Tax Type, and the main attachment in Review Details. Reload and verify persistence.
2. Approve Stores and Purchases on a non-cash claim, then Taxes only. As Secretary, change Tax Type and reload: confirm all approvals, the current stage, and payment documents remain unchanged. Repeat as Administrator and on a returned claim.
3. Approve Supplier Accounts as well. As Secretary, confirm Tax Type is read-only and Section/main attachment still save successfully without removing either approval.
4. As Taxes (without Secretary/Administrator membership), inspect the claim before and after approvals: Section and Tax Type remain read-only, and the Secretary upload controls are unavailable. Direct writes to those fields must be rejected.
5. As Administrator, confirm Tax Type is editable before both approvals and locked afterward, including in Replace Supplier Document. Section and main attachment remain editable on an open claim.
6. Complete payment preparation and close the claim. Verify Secretary and Administrator cannot change any of the three fields. Repeat on an archived claim.
