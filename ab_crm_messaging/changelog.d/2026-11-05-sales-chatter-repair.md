# Shared queue eligibility — 2026-11-05

Current changes before commit:

- Expose a private, side-effect-free queue eligibility result with stable reason codes for account and destination restrictions.
- Use the same result in outgoing approval; retain content validation, existing fields and gateway/provider separation.

Files changed:

- `ab_crm_messaging/__manifest__.py`
- `ab_crm_messaging/models/messaging.py`
- `ab_crm_messaging/changelog.d/2026-11-05-sales-chatter-repair.md`
