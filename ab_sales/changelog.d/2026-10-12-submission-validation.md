# Callcenter submission, customer selection and draft removal

## Recent commit reviewed

- Commit: `d620d0cc822ed69561359c852b1a77a25dd119d3`
- Author: emadco88
- Date: 2026-10-12 14:50:52 +0300
- Original commit subject: ab_sales/ port selective draft restoration from pos19
- Introduced independent tab workspaces and confirmed draft removal.

Files changed (relevant excerpt):
- `ab_sales/models/ab_sales_pos_draft_slots.py`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`

## Current changes before commit:

- Preserve shortage reasons even when the browser snapshot shows sufficient stock; aggregate repeated product quantities using their selected units.
- Refresh displayed branch balances after a confirmed rejection.
- Reveal shortage reason fields from a captured branch rejection even when the displayed balance is sufficient, including restored drafts and legacy branch messages. Preserve normal stock validation and retry the original token.
- Show submission warnings and errors in a popup instead of an inline invoice banner. Keep a compact status button to reopen saved messages and the original shortage response inside the popup.
- Display stale inventory as «غير معروف» on product cards and invoice lines in both Arabic catalogs. Show the stale label, cached branch balance and cart icon in red while the stale flag is active; restore the regular muted balance styling after a successful refresh. Translate popup fallback titles and the message button tooltip.
- Validate readable, active references and valid sale units before preparing branch requests. Check contract branch restrictions before transport when the contract integration is installed.
- Verify customer response branch identity, respect customer read access and archival, and preserve existing customers' home branches.
- Clear selected customer results when phone or branch changes; ignore responses for an earlier selection.
- Allow removal of rejected invoices from the draft workspace by archiving the durable local header. Preserve invoice lines, submission payload, token and audit history. Protect uncertain, active and accepted submissions.
- Reject resubmission of archived tokens and prevent stale browser caches from restoring archived invoices.
- Apply authoritative unlock/removal state to existing tabs while preserving the local edit generation.
- Export Odoo POT and append translations to both Arabic catalogs. Version: `19.0.3.8.4`.

Files changed:
- `ab_sales/__manifest__.py`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/ab_sales_pos_draft_slots.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action.xml`
- `ab_sales/static/src/pos/pos_action.scss`
- `ab_sales/static/src/pos/pos_action_sales_line_balance.xml`
- `ab_sales/static/src/add_products/product_card.xml`
- `ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/changelog.d/2026-10-12-submission-validation.md`

## Diagnosis and validation evidence

- The recorded three-product shortage rejection was routed to the remote branch at `https://192.168.2.230`, not the local POS endpoint. The local code contained the same live-display/cached-submission mismatch. Remote stock at the original failure time was not independently verified.
- Earlier callcenter rejection records also reported a missing or ambiguous branch customer reference. Such data problems now have explicit customer/contract synchronization messages on the updated branch API; no customer identity is guessed or substituted.
- The callcenter checkout has no `ab_branch_api` directory; that module is uninstalled in its database. No new installation was introduced.
- Isolated copies: `codex_ccfix_callcenter19_20261012` and `codex_ccfix_pos19_20261012`. Source databases were read only. No E-Plus posting/customer creation was executed by the tests.
- Targeted callcenter upgrade completed on ports 5069/5072 with cron workers disabled. Branch API upgrade completed separately on the POS copy.
- 15 callcenter ORM checks passed: removal with archival, archived token rejection and stale-cache suppression, uncertain/accepted protection, revision conflict, active/inaccessible references, branch/customer identity checks, home-branch preservation, archived customers, contract restrictions, Arabic errors and runtime menu translation.
- 23 branch API ORM checks and 12 frontend checks passed. Detailed branch results are recorded in the POS module changelog.
- Both Arabic catalogs passed `msgfmt --check-format`. Runtime `ar_001` archived-invoice text and menu translation differed from `en_US`.
- Reproducible development harnesses and logs are retained outside the runtime addon: `/tmp/test_callcenter_regressions.py`, `/tmp/test_callcenter_frontend.cjs`, `/tmp/callcenter_regressions.log`, `/tmp/pos_regressions.log`. Test fixtures are rolled back.
- The original local branch API accepts its configured credentials and routing, but the bounded live stock read returned HTTP 422: `The selected store E-Plus endpoint is unreachable.` Live invoice/customer creation and posted contract amounts therefore remain manual integration checks.
- The isolated POS upgrade exposed 85 existing return headers without a store; this was independently confirmed read-only in the original POS database. The upgrade completed but could not add the existing required-field NOT NULL constraint. Historical return data was not modified.
- Running PyCharm servers were not stopped/restarted. Upgrades were performed on the isolated copies, not the active databases. Activation requires loading the changed Python code and upgrading the targeted modules.
- Screenshot follow-up: TELFAST 180 shows quantity 1, displayed branch balance 100 (cart icon), and total balance 121.5 (green cubes) while the captured branch message requires a shortage reason. The reason-field visibility previously compared only displayed stock; it never consumed the captured rejection. The old banner also concatenated the status and message in the action-button area. These are confirmed frontend defects; the screenshot does not prove the actual branch stock at submission time.
- The exact screenshot invoice was not identified in the active callcenter database. The earlier related rejection is header 28, with different quantities and all three medicines named. Its stock values are not evidence of the screenshot's branch stock.
- Follow-up validation: 28 frontend checks passed (the original 12 plus 16 shortage-handling cases), including the screenshot, restored drafts, legacy/current response formats, multiple products, Arabic messages, unrelated errors, protected statuses and the actual rejected-submit handler. Harness: `/tmp/test_callcenter_shortage_ui.cjs`.
- The follow-up isolated `ab_sales` upgrade succeeded. XML parsing, SCSS compilation and both PO format checks passed. Odoo runtime web translations contain all five affected strings in `ar` and `ar_001`; an Arabic action label differs from English. Browser layout and real branch posting remain manual checks.

## Activation and final manual tests

Load the updated callcenter `ab_sales` and POS `ab_branch_api` code through the normal server restart procedure, upgrade only those modules, and hard-refresh the callcenter browser. The remote branch that rejected the original invoice needs the same branch API release. Restore E-Plus connectivity before testing a real submission. Use approved test transactions for posting/customer creation.

| Case | Expected result |
| --- | --- |
| Original three products, sufficient live stock but zero/stale Odoo cache | Submission is not rejected because of cached zero stock. |
| Actual stock shortage, no reason | Reject with requested/available quantities and base unit. |
| Other selected with blank or spaces-only details | Reject until details are entered. |
| Valid reason, including Other with details | Shortage check passes; normal price, contract and posting checks still apply. |
| Same product on two lines whose combined quantity exceeds balance | Each affected line requires a reason. |
| Box/strip/unit and fractional quantities | Compare quantities in the product's balance unit. Check tolerance around 0.025. |
| Stock changes after product selection | Submission uses current branch stock; rejection refreshes the screen. |
| Rejected retry after stock is replenished | Retry reads stock again using the same invoice token. |
| Missing/inactive product or unavailable branch stock service | Show a data/connectivity error; do not treat unknown stock as zero or submit. |
| Valid contract allowed for the branch | Submit once; compare customer/company amounts, discount and printed invoice against branch rules. |
| Inactive/missing/duplicated contract or disallowed branch | Reject before posting with an actionable message. |
| Contract with zero customer contribution, fixed contribution, percentage contribution and invoice discount | Verify preview, posted totals and printout agree; pricing formulas were not changed. |
| Existing customer found by phone at the selected branch | Select the branch-confirmed identity; preserve the callcenter customer's original home branch. |
| Customer exists only in the callcenter cache or branch Odoo cache | Do not substitute a different identity. Missing branch replication produces a synchronization error. |
| Archived or duplicated customer reference | Reject without reactivating or merging customer records. |
| Change phone/branch while lookup is in flight | The old response cannot reselect the previous customer. |
| Customer lookup without a branch | Request branch selection. |
| Create customer; simulate timeout and retry | Verify existing operation-token recovery creates/returns one customer; no duplicate creation. |
| Delete empty or unsent draft, then refresh another tab | Draft stays removed. |
| Delete rejected draft with products | Remove from workspace; archived local invoice, lines and audit history remain. |
| Retry an archived invoice token through direct RPC | Reject; do not recreate/post it. |
| Delete while submission is active or outcome is Unknown | Retain invoice and draft; resolve the original submission. |
| Pending/Saved invoice | Preserve durable invoice; workspace cleanup must not archive it. |
| Delete All with mixed eligible, rejected and uncertain drafts | Remove only eligible drafts; archive rejected local invoices; retain uncertain submissions. |
| Stale tab requests deletion using an older revision | Reject with reload instruction; no lost newer edits. |
| Two tabs receive rejection/refresh in different orders | Rejected invoice unlocks; old asynchronous edits cannot overwrite later state. |
| Repeat accepted submission or recover a timeout | Preserve the same token and invoice identity; no duplicate E-Plus invoice. |
| Unauthorized user, employee or branch via direct RPC | Deny access; no invoice/customer data from another authorized scope. |
| English and Arabic UI | New validation messages are readable and correctly translated in both catalog languages. |
| Screenshot case: TELFAST 180 quantity 1, displayed branch balance 100, total balance 121.5, captured shortage rejection | Reason selector appears under TELFAST despite the positive display; unrelated products remain unchanged. A correction dialog explains the next step. |
| Restore/reload that rejected invoice | TELFAST reason selector remains visible without another submission. |
| Select Other on the rejected invoice | Details input appears; blank details are rejected by the branch; completed details are preserved on retry with the same token. |
| Arabic narrow/maximized POS window | Submission warning opens as a popup; no warning banner remains in the invoice header. The compact status button reopens the popup, including the original shortage response. |
| Branch product label cannot be matched to a local product | Reveal reason controls for all invoice lines for review; never bypass branch validation or invent a stock balance. |

## Popup follow-up — 2026-10-13

Recent commit reviewed:
- Commit: `44779a919ab62a4fd9d233931c40153dda0352f7`
- Author: Hossam Elsheikh
- Date: 2026-10-12 16:44:28 +0300
- Original commit subject: Current-connection bills now refresh even when older bills target another database. Skipped bills are identified by ID.
- Keeps current-destination status refresh independent of older requests. Preserved by this UI change.

Files changed in that commit:
- `ab_sales/models/local_bills.py`
- `ab_sales/changelog.d/2026-10-12-status-refresh-destinations.md`

Validation of current popup changes:
- 28 existing frontend checks passed, including shortage correction, preserved reasons and rejected-submit popup behavior.
- Rejected and Unknown non-shortage responses each opened a popup without a warning toast; the status action reopened each saved message.
- XML parsing, SCSS compilation, `git diff --check`, and both Arabic PO format checks passed.
- Exported `/tmp/ab_sales_popups.pot`; Odoo runtime exposed all eight affected/reused messages correctly in both `ar` and `ar_001`. An Arabic action name differed from English.
- Targeted `ab_sales` upgrades completed on the isolated copy and the local `callcenter` database, with alternate ports and cron disabled. Neither PyCharm server was stopped or restarted. No invoice or external stock transaction was submitted.
- The running callcenter translation endpoint returned «غير معروف» for Stale and «عرض رسالة الإرسال» for the popup tooltip.
- Automatic approval review blocked reloading the active invoice and opening a live draft slot to protect draft state. A separate verification tab loaded successfully; popup rendering on the live invoice was not exercised. The original tab was left untouched.
- Manual check after safely saving the current workspace: reload the POS, open the status button on a rejected draft, confirm the popup and absence of the old banner, and verify «غير معروف» on stale product/line balances. Close the popup and confirm invoice values and the retry token remain unchanged.

Stock color follow-up — 2026-10-13:
- Changed the existing stock components in `static/src/pos/pos_action_sales_line_balance.xml` and `static/src/add_products/product_card.xml` to apply red styling to the stale label and its branch balance while `pos_balance_stale` is true. Fresh balances retain their normal styling; quantities and validation are unchanged.
- XML parsing and `git diff --check` passed; both Arabic catalogs retain «غير معروف». No user-facing source strings changed.
- Targeted `ab_sales` upgrades completed successfully on the isolated copy and local `callcenter` database, version `19.0.3.8.4`. No running server was restarted and no invoice was submitted. Logs: `/tmp/ab_sales_stock_color_upgrade.log`, `/tmp/ab_sales_stock_color_live_upgrade.log`.
- Manual check: after saving the workspace and refreshing the POS, confirm stale stock labels and adjacent balances are red in product cards and invoice lines, then confirm a successful stock refresh removes the stale label and restores the balance's regular color.
