# Customer-only conversation heading

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.20.0 shows only the customer name and formatted customer phone in the Telegram/WhatsApp heading. Omit account IDs, business inbox labels and update timestamps from that heading.
- Remove header, channel-icon and conversation-chooser unread badges. Keep the existing unread calculation, customer-list badges and popup notifications.
- Supply a display-only phone for saved and verified unlinked customers; never substitute a Telegram account ID for a phone.
- Update existing browser expectations. Preserve previous contact, alert, reception and dispatch changes and both Arabic catalogs.

Files changed for this increment:
- `__manifest__.py`
- `changelog.d/2026-11-10-customer-header.md`
- `models/customer_streams.py`
- `static/src/workspace.xml`
- `static/tests/message.test.js`
- `tests/test_workspace.py`
