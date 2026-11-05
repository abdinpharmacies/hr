# Sales Chatter order popup and messaging — 2026-11-05

Current changes before commit:

- Preserve optional Telegram profile data separately from customer identity.
- Deduplicate automatic and employee-requested contact prompts; preserve immutable contact-button snapshots.
- Gate new outgoing operations and send authorization on the explicit outgoing switch while reception remains independent.

- Update both Arabic catalogs and focused regression coverage.

Files changed:

- `ab_crm_telegram/__manifest__.py`
- `ab_crm_telegram/changelog.d/2026-11-05-order-popup-messaging.md`
- `ab_crm_telegram/i18n/ar.po`
- `ab_crm_telegram/i18n/ar_001.po`
- `ab_crm_telegram/models/account.py`
