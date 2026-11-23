# Notification-only order conversations

Current changes before commit:
- Suppress the reply-disabled notice for website order notifications without customer chat, while preserving server-side reply restrictions and native chat eligibility.
- Verify notification-only details and browser expectations in English and Arabic.

Files changed:
- models/adapter.py
- tests/test_contact_groups.py
- changelog.d/2026-11-18-order-notifications.md
