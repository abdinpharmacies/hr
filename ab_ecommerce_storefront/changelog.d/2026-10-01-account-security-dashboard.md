# Account security dashboard redesign

## Recent relevant commit

Commit: `94abdb9`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: align account password mask in RTL layout`

User-facing changes:

- Align the masked password value correctly in the existing RTL customer account interface.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Replace the plain Account Security definition list and Bootstrap form with a premium RTL healthcare dashboard containing a security summary, three method cards, a current-password card, and a clear account-action group.
- Derive the visual security count from the existing verified email, phone, and Telegram identity values without adding backend state or changing verification logic.
- Preserve the existing CSRF token, `/my/authentication` form action, field names, required constraints, routes, conditional Telegram action, and dynamic identity values.
- Add responsive desktop, tablet, and mobile styling with consistent verified, pending, linked, Telegram, focus, and reduced-motion treatments.
- Add the new English source strings and matching Arabic translations for both `ar` and `ar_001`.
- Prevent the Account Security progress indicator from producing an invalid QWeb format expression after XML loading.
- Keep `/my/authentication` canonical while accepting `/authentication` as a compatibility alias for the same secured controller.
- Reuse the customer account navigation on the Account Security page and highlight its security entry as the active destination.
- Preserve the Arabic labels for every shared account-navigation entry in both supported Arabic locales.
- Position the Account Security navigation on the left while preserving RTL direction inside the navigation and page content.
- Remove the redundant portal breadcrumb and header Home controls from the Account Security page.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/views/auth_security_templates.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/static/src/scss/auth_security_bundle.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-01-account-security-dashboard.md`

Validation:

- Targeted `ab_ecommerce_storefront` upgrades completed successfully on `ecom19`; Odoo accepted the QWeb template and manifest asset changes.
- The Odoo 19 POT export was inspected before merging the new Account Security strings, and both Arabic catalogs pass `msgfmt --check-format`.
- Runtime `ar_001` view verification confirms the Account Security architecture differs from `en_US` and contains the translated security-status and account-actions headings.
- The live debug frontend bundle compiles without a Sass error and contains the new security-dashboard selectors.
- Desktop `1680x1200` and mobile `390x1200` RTL previews were visually inspected; cards reflow without horizontal overflow and LTR email and phone values remain readable.
- `git diff --check` passes for the focused template, stylesheet, manifest, catalog, and changelog changes.
- The installed Arabic portal template renders successfully for an existing portal-user context after the focused module upgrade.
- The shared account navigation renders all seven Arabic labels, marks Account Security active, and preserves the localized security form action and current-password field.
- The compiled RTL frontend bundle keeps the Account Security navigation in the physical left column while retaining RTL direction inside the menu and page content.
- The focused module upgrade succeeds after removing both Account Security Home controls, and the rebuilt RTL bundle no longer contains their selector.
