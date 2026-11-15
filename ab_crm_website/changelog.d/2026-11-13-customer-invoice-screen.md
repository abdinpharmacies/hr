# Customer order screen and invoice presentation

Current changes before commit:

- Show all authorized Website order messages for the same submitted phone in one staff conversation screen.
- Keep source order conversations and reply routing separate; route each Create order button to its own handoff.
- Aggregate pagination, message search and read acknowledgement within the authorized phone group.
- Center Website Order headings and provide View invoice / Hide invoice with labelled customer details.
- Remove generated terms from presentation, preserve customer notes, and constrain the product table to the chat width.
- Display verified payment methods without inferring COD from generic custom-provider evidence.
- Preserve immutable order/payment snapshots and add protected display metadata for verified older payment methods.
- Cover grouped messages, unrelated-phone isolation, read state, presentation and Arabic/narrow layouts.

Files changed:

- `models/adapter.py`
- `static/src/order.xml`
- `static/src/order.scss`
- `static/src/workspace.js`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_adapter.py`
- `tests/test_pos.py`
- `tests/test_ui.py`
- `changelog.d/2026-11-13-customer-invoice-screen.md`
