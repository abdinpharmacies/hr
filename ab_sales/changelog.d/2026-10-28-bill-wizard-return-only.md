## 44297ba3defa33f8144004f3930f838c9007fb91 - hossam elsheikh - 2026-10-21

Original commit subject: ab_sales:fix_rejected_bill_corrections_and_translation

Return UI change in this commit:
- Make return popup feedback translatable, including load, notes, line actions and errors.

Files changed (return UI reference):
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js

## Current changes before commit:

- Make Bill Wizard the sole return creation/submission UI. Hide the Bills Return button; make standard return header/line views read-only with no New, editing, duplication or processing buttons.
- Redirect the legacy New Return action to review history and remove the module's shared Save-to-Commit form override.
- Close the return popup and notify once only after a matching saved response with a positive posted return ID. Keep errors, unconfirmed responses and selected quantities visible; prevent duplicate submission.
- Preserve drafts after any submission attempt, including employee-access extension cleanup and lost-response cases, using a popup-local ORM facade. Employee login, permissions and posting/request-token behavior remain unchanged.
- Refresh the originating Bill Wizard on popup close without delaying closure; preserve filters/page/selection, retain context on list refresh failure and ignore destroyed-parent callbacks.
- Translate four new messages in both Arabic catalogs using an exported POT; document the workflow and bump ab_sales to 19.0.4.1.20.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-28-bill-wizard-return-only.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/pos/return_form_buttons.xml (removed)
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.xml
- ab_sales/views/ab_sales_return.xml
- ab_sales/views/ab_sales_return_line.xml
- ab_sales/views/sales_header.xml

Validation:
- Passed targeted ab_sales upgrades in isolated QA database codex_cc_eplus_balance_20261027.
- Passed 35 ORM/view/runtime checks: effective admin views hide creation/edit/delete/duplicate/processing controls, historical action redirects, removed toolbar asset, unchanged unrelated sales action, explicit return success serialization, employee-login checks, preserved Bill Wizard routing, invalid return-of-return rejection and both Arabic catalogs/runtime view translation.
- Passed 23 Chromium/OWL checks using the actual return component/template and Bill Wizard methods with mocked services: confirmed/unconfirmed/error replies, duplicates/retry, malformed records, full-return selection, in-flight destruction, close failure, parent refresh state/failure and the actual installed employee-access patch's session/logout/cleanup behavior.
- Python/XML/JavaScript syntax, both msgfmt --check-format runs and git diff --check passed. Evidence and scripts are outside the addon in /tmp/cc_returns_qa/.
- No real branch return was posted, no external data was modified, and the production callcenter service was not upgraded or restarted. QA upgrade also applied the pre-existing committed removal of local record rules; this task does not change security files.
