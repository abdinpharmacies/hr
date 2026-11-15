# Separate website order chats

Current changes before commit:

- Give every Website order a separate visible Inbox chat even when orders share a phone or reviewed contact.
- Display the submitted phone and order reference in each chat title.
- Keep each Website timeline and reply destination scoped to its own order.
- Preserve incoming order cards and Create order, while phone matching remains contact-review evidence.
- Cover separate Inbox entries, same-phone searches and rejection of cross-order channel switching.

Files changed:

- `models/adapter.py`
- `tests/test_adapter.py`
- `tests/test_pos.py`
- `changelog.d/2026-11-13-separate-order-chats.md`
