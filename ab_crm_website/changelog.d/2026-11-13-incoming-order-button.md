# Incoming website order and POS creation

Current changes before commit:

- Render each immutable website quotation inside its incoming message, including earlier revisions.
- Add Create order to the incoming order card using the existing contact and conversation POS handoff.
- Preserve customer review, local pricing, mapped product/unit prefill and linked-draft reuse.
- Translate the new button in both Arabic catalogs and cover message history and browser navigation.

Files changed:

- `models/adapter.py`
- `static/src/order.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_pos.py`
- `tests/test_ui.py`
- `changelog.d/2026-11-13-incoming-order-button.md`
