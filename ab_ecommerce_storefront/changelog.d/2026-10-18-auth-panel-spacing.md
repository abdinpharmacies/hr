# Authentication panel spacing

## Recent relevant commit

Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`

User-facing changes relevant to this fix:

- Simplify the authentication panel heading and description in English and Arabic.

Files changed relevant to this fix:

- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

## Current changes before commit:

- Keep the login panel badges in normal flow so wrapped headings and descriptions cannot overlap them.
- Let the panel grow with its content and keep at least 1.5rem between the description and badges.
- Preserve the existing mobile behavior and English/Arabic text.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-auth-panel-spacing.md`

Validation:

- Compile the complete storefront SCSS with the project's libsass successfully.
- Fetch English and Arabic login pages on port 4092 at HTTP 200 and verify their translated panel text.
- Fetch Odoo's LTR and RTL debug frontend CSS at HTTP 200 and verify the updated panel rules.
- Validate both Arabic catalogs with `msgfmt --check-format`; no user-facing strings changed.
- No database upgrade or server restart is needed for this stylesheet-only change.
- Browser rendering and responsive visual checks remain unverified because no browser is connected to this session.
