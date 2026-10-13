# Immutable failed bills and original request retries

## Recent relevant commit

- Commit: `44779a919ab62a4fd9d233931c40153dda0352f7`
- Author: Hossam Elsheikh
- Date: 2026-10-12 16:44:28 +0300
- Original commit subject: Current-connection bills now refresh even when older bills target another database. Skipped bills are identified by ID.
- Kept status refresh tied to each bill's original destination while allowing current-connection bills to refresh.

Files changed:
- `ab_sales/models/local_bills.py`
- `ab_sales/changelog.d/2026-10-12-status-refresh-destinations.md`

## Current changes before commit:

- Remove the rejected-state exception from submitted bill header and line mutation guards, price recomputation, and the editable response flag.
- Replay the stored submission and wire payload for retries, including rejected bills. Preserve request token, revision, prescription flags, and original destination; ignore replacement browser business data.
- Remove the rejected-bill payload rebuilder and automatic revision increments. Keep first-attempt preparation separate from retry replay.
- Lock persisted or attempted POS bills, including rejected bills. Route Retry directly to submission without opening the editable confirmation dialog; keep unsent drafts editable.
- Make the callcenter bill form read-only and hide Add Products while preserving Retry Submission.
- Reuse existing English messages and their Arabic translations; no user-facing strings were added or changed.

Files changed:
- `ab_sales/models/local_bills.py`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/views/local_bill_views.xml`
- `ab_sales/changelog.d/2026-10-13-immutable-failed-bills.md`

Validation:
- `/tmp/test_callcenter_f1.py`: Odoo shell checks on `callcenter19` passed rejected-header edits, line update/add/delete rejection, form retry payload preservation, modified-browser retry replay, token/revision preservation, and inherited view compilation. Included a prescription flag in a rollback-only fixture. Mocked remote posting and commits; rolled back all test changes.
- `/tmp/test_callcenter_f1_ui.js`: extracted POS methods passed locked-state cases, direct retry routing for rejected/unknown/attempted bills, and normal submission routing for fresh drafts.
- Both Arabic catalogs passed `msgfmt --check-format`; the reused lock message has a translation in both catalogs.
- Targeted `ab_sales` upgrade completed on `callcenter19`; callcenter workers reloaded. No branch module upgrade or external sale/refund posting was performed.
- `/tmp/test_callcenter_f1_browser.js`: authenticated live Playwright check passed on rejected bill 17608: read-only form, zero writable fields, Retry visible, Add Products hidden.
