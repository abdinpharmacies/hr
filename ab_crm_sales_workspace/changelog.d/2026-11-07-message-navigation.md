# Message bubbles and channel navigation — 2026-11-07

Previous module commit: `590971e4`, Alhassan Hossny, 2026-11-05,
`ab_crm_sales_workspace/feat: add shared PIN-agent Chatter, persistent alerts and contact management`.

Current changes before commit:

- Center labeled customer channel/account navigation above the conversation header; authorize destinations by customer record, employee session, branch and company. Preserve independent drafts and attachments.
- Replace refresh-time activity with recorded incoming activity and latest outgoing status; retain contact search and remove conversation search.
- Add compact incoming/outgoing bubbles, localized UTC timestamps, date separators and vector receipts. Keep provider receipts separate from employee reading and retain existing Telegram and deferred-channel restrictions.
- Use Odoo dropdowns for reply, supported reaction selection, copy, preview and download. Explain disabled customer-visible Edit/Delete without changing immutable history or standalone WhatsApp behavior.
- Resolve bounded quoted summaries across history, show image thumbnails, and load/focus originals while retaining intervening history. Provide an unavailable fallback for denied or missing originals.
- Add explicit monotonic visible-message acknowledgement. Fetching and alert focus no longer write employee read positions; hidden tabs, inactive workspaces and dialogs suppress browser acknowledgement.
- Add image/audio/PDF viewing and release preview URLs. Preserve pending/failed media states and report clipboard/download errors.
- Update both Arabic catalogs, increment to 19.0.1.8.0, and register frontend tests exclusively in test assets.

Files changed:

- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/static/src/workspace.js`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/static/src/workspace.scss`
- `ab_crm_sales_workspace/static/src/message.js`
- `ab_crm_sales_workspace/static/src/message.xml`
- `ab_crm_sales_workspace/static/tests/message.test.js`
- `ab_crm_sales_workspace/tests/test_workspace.py`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/VALIDATION.md`
- `ab_crm_sales_workspace/changelog.d/2026-11-07-message-navigation.md`
