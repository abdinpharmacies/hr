# Checkout notification fixes

Current changes before commit:
- Allow automatic sales/payment notifications without a Callcenter chat receipt; preserve receipt and ownership checks for customer comments. Add a regression for public checkout notifications and comment denial.

Files changed:
- models/adapter.py, tests/test_adapter.py
- changelog.d/2026-11-18-checkout-notifications.md
