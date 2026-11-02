# Website staff management

Commit: `2ff4e9b1`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: manage website staff users by creator`

User-facing changes:

- Open a staff-user list from the Website menu, with a New action and account details.
- Let Website editors update only employees they created and choose bounded Website roles.
- Show active status and prevent cross-creator, cross-company, or elevated-account edits.
- Translate the new screen and roles into both Arabic locales.

Validation: Targeted `ab_ecommerce_storefront` upgrade on `codex_ecom_translation_20261012` passed. Normal-user checks covered creating and editing an owned employee, rejecting another creator, rejecting direct user and tracking-record writes, and rejecting an account elevated by an administrator. The action and role labels loaded in `ar_001`; both Arabic catalogs passed `msgfmt --check-format`.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/staff_account.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/views/staff_user_views.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
