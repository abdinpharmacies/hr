# Preserve configured Live Chat operators

## f89fbaf81f159393444c89b0e5c9757c3c5025a4

Author: Mohamed Fawzy
Date: 2026-11-17
Original commit subject: ab_ecommerce_storefront/IMP: let shoppers choose gift quantities

- Let shoppers select quantities for eligible gift offers.

## Current changes before commit:

- Preserve configured Live Chat operators when storefront default data is reapplied, including the dedicated Callcenter bridge operator.
- Retain the channel XML ID, administrator assignment, greeting and appearance.
- Bump the storefront patch version to 19.0.1.0.1.

Files changed:
- __manifest__.py
- data/livechat.xml
- changelog.d/2026-11-18-preserve-livechat-operators.md
