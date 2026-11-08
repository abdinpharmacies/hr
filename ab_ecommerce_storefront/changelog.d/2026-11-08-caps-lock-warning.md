# Caps Lock warning color

Commit: `48383f8333c91ebaf9c19b54ee3f6eb67b6fe11c`
Author: Mohamed Fawzy
Date: 2026-09-03
Original subject: `ab_ecommerce_storefront/fix: polish auth flow and avatar completion`

- Added storefront-specific authentication field styling, including password fields that use Odoo's Caps Lock notice.

Files changed relevant to this update:

- `static/src/scss/auth_fields.scss`
- `views/auth.xml`

## Current changes before commit:

- Show Odoo's existing Caps Lock notice with an amber warning color on storefront login and signup forms, instead of its default red error color.
- Preserve the notice's detection and visibility behavior and all existing Arabic and English text.

Files changed:

- `static/src/scss/auth_fields.scss`
- `changelog.d/2026-11-08-caps-lock-warning.md`

Validation:

- Compiled `auth_fields.scss` with the Odoo virtual environment's Sass compiler and confirmed the scoped selector and amber color.
- Both Arabic catalogs passed `msgfmt --check-format`; no user-facing string changed.
- `git diff --check` passed. No database records or shared Odoo frontend files changed.
- Targeted upgrade of `ab_ecommerce_storefront` on isolated `codex_legacy_inline_20261104` completed with exit 0 using ports 5069/5072 and cron disabled. Log: `/tmp/caps-lock-warning-validation.log`.
