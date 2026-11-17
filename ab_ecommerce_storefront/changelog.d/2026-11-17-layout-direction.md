# Storefront language direction

Relevant commits:

- Commit: `5148d5a65f7bb021c9679a99522f64a79b13eaab`
- Author: Mohamed Fawzy
- Date: 2026-09-15
- Original subject: `ab_ecommerce_storefront/style: refine checkout delivery and payment experience`
- Refined checkout and account layouts; the account dashboard's fixed RTL direction originated here.
- Files changed: `static/src/scss/storefront.scss`, `views/cart.xml`.

- Commit: `855b7dd32e7f201c8329368296e800edde2ce24c`
- Author: Mohamed Fawzy
- Date: 2026-10-05
- Original subject: `ab_ecommerce_storefront/feat: add verified email and Telegram account recovery`
- Added verified recovery methods and account security screens. Relevant files changed: `static/src/scss/auth_fields.scss`, `static/src/scss/auth_security_bundle.scss`, `views/auth.xml`, `views/portal.xml`, `views/auth_security_templates.xml`.

Current changes before commit:

- Set the storefront HTML direction from the request language, enabling existing Arabic rules for navigation, breadcrumbs, and branch results.
- Let profile, orders, authentication, security, and order-detail layouts inherit the page direction. Previously hardcoded RTL became LTR in Arabic assets through Odoo's RTL conversion.
- Position the orders selection indicator from the logical start edge so it follows the selected tab in either language.
- Keep phone numbers, email/login identifiers, passwords, profile contact values, prices, and price-range controls LTR through RTL asset conversion.
- Preserve source UI strings and both Arabic catalogs. Existing unrelated livechat changes are recorded separately.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/auth_fields.scss`
- `ab_ecommerce_storefront/static/src/scss/auth_security_bundle.scss`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/changelog.d/2026-11-17-layout-direction.md`

Validation:

- Reproduced Arabic profile direction `ltr` before the fix. After asset rebuild, Arabic profile/sidebar direction is `rtl` with the sidebar at the right; English is `ltr` with the sidebar at the left.
- Verified profile, orders, login, branches, and contact in English and Arabic on the running development storefront at port 4102. Verified Arabic branch results and contact phone/email fields. Order tabs follow the page direction; the prescription selection indicator reaches two-thirds of the track from the logical start in both languages.
- No desktop horizontal overflow on orders, login, branches, or contact. A requested viewport override did not change the observed profile viewport; mobile geometry remains unverified.
- Compiled all four changed SCSS files with the project's libsass and converted with Odoo's RTL configuration. A temporary validation script passed 39 assertions covering both compiled directions, numeric isolation, logical order-tab positions, and parsing all three changed XML files.
- Both Arabic catalogs passed `msgfmt --check-format`; no changed user-facing strings require translation entries. `git diff --check` passed.
- Security and recovery routes returned HTTP 403 for the available browser session, so their visual layout remains unverified; their CSS direction was checked in both compiled variants. No authentication protections were changed.
- Shop browser navigation exceeded the tool timeout; a separate HTTP read returned 200 in 13.7 seconds. Live price-control geometry and order-detail pages with actual order data remain unverified.
- The development server loaded XML changes through its existing XML development mode and rebuilt frontend assets. No module upgrade, database mutation command, service restart, or temporary Odoo server was needed.
