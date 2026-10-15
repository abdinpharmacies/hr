# Delivery celebration

Recent relevant commit:

- Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
- Author: Mohamed Fawzy
- Date: 2026-10-13
- Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`
- Simplified customer-facing portal and storefront wording in English and Arabic.
- Files changed (tracking context): `ab_ecommerce_storefront/views/portal.xml`

Current changes before commit:

- Add a warm delivery confirmation above the tracking timeline for delivered prescription and regular orders.
- Animate a checkmark, halo and brief brand-color confetti burst on the first visible visit per order in the same browser. Linked prescription and sales-order pages share the acknowledgement key.
- Keep the confirmation readable on repeat visits, without JavaScript, when browser storage is blocked, and with reduced motion enabled. Animation stops on page exit, backgrounding or a motion-preference change.
- Exclude dispatch, partial delivery, cancellation, rejection and returned orders. Reuse existing tracking state and access checks without adding routes, permissions or business-record writes.
- Add a customer-help link and four translated terms in both Arabic catalogs, merged from an Odoo POT export.
- Preserve unrelated existing storefront work; this entry describes the delivery-celebration portion of the current module changes.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/static/src/js/order_delivered.js`
- `ab_ecommerce_storefront/static/src/scss/order_delivered.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-14-delivery-celebration.md`

Validation:

- Targeted storefront upgrades passed on isolated database `codex_ecom_offers_20261013`, ports 5069/5072, HTTP and cron disabled.
- Nine JavaScript lifecycle checks passed using `/tmp/validate_delivery_animation.cjs`; these use a simulated DOM and observer, not a browser engine.
- Eleven Odoo checks passed using `/tmp/validate_delivery_qweb.py`: runtime QWeb delivery guards, linked-order acknowledgement keys, actual ORM delivery/dispatch classification and English/Arabic rendered content. Records used for classification were in memory and the transaction was rolled back.
- Both Arabic catalogs passed `msgfmt --check-format`. XML parsing, JavaScript syntax, standalone SCSS compilation and `git diff --check` passed.
- Read-only inspection confirmed the sales order linked to `RX-141026-H49K2K` has last-mile status `delivered`.
- Browser providers were unavailable; visual timing, mobile/RTL layout and full frontend asset rendering remain unverified in a browser.
- Existing registry warnings about unavailable accounting EDI models remain outside this change. The targeted upgrades exited successfully.
- No running development server was restarted and no active-database upgrade was performed. Activation requires the storefront assets/template and translations to be reloaded through the normal targeted module upgrade workflow.
