# Staff sign-in and Website menu placement

Commit: `a41b471b`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: let website editors set staff passwords`

User-facing changes:

- Let Website editors set and confirm a temporary password for staff accounts they created.
- Add a password-link action and show a warning when Odoo could not send the initial invitation.
- Keep passwords masked and clear the temporary wizard after saving.

Files changed:

- `ab_ecommerce_storefront/models/staff_account.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/views/staff_user_views.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `ee47b4df`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: place category and staff menus in Abdin Management`

User-facing changes:

- Put eCommerce Categories in Abdin Management → Products.
- Put Add Staff User directly in Abdin Management.
- Keep category and staff actions and their access controls intact.

Files changed:

- `ab_ecommerce_storefront/views/management_menus.xml`
- `ab_ecommerce_storefront/views/staff_user_views.xml`

Validation: The targeted `ab_ecommerce_storefront` upgrade passed on `codex_ecom_translation_20261012`. Normal-user checks confirmed the menu paths, Website editor visibility, creator-only password-link action, warning for a missing invitation, and password authentication after setting a temporary password. The Arabic button and password-field labels loaded at runtime, and both Arabic catalogs passed `msgfmt --check-format`.
