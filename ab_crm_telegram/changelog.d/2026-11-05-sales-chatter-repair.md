# Telegram queue eligibility reasons — 2026-11-05

Current changes before commit:

- Extend shared queue eligibility with outgoing-switch and private-chat restrictions so workspace disabled reasons match server enforcement.
- Preserve outgoing switches, provider acceptance handling and contact event validation.

Files changed:

- `ab_crm_telegram/__manifest__.py`
- `ab_crm_telegram/models/account.py`
- `ab_crm_telegram/changelog.d/2026-11-05-sales-chatter-repair.md`
