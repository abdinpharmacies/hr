# Homepage customer reviews

## Recent relevant commit

Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`

User-facing changes:

- Simplify homepage and storefront wording in English and Arabic.
- Rename the homepage product showcase without claiming sales-volume evidence.

Files changed (relevant to this update):

- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

## Current changes before commit:

- Replace the fixed review grid with a responsive horizontal strip, larger screenshots, lighter framing, and a preview of the next card.
- Add previous/next controls, native touch scrolling, RTL-aware keyboard navigation, boundary states, and a translated position announcement.
- Open full-size review images in a native dialog with a source link, Escape/close controls, and focus restoration. Preserve normal image links when JavaScript or dialog support is unavailable.
- Respect reduced-motion settings and retain existing screenshots, names, source URLs, and publication rules.
- Merge eight exported review terms into the existing POT and both Arabic catalogs without replacing unrelated translations.

Files changed:

- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/static/src/js/customer_testimonials.js`
- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-13-customer-reviews.md`

Validation:

- Ten JavaScript interaction tests passed with mocked layout/dialog objects: RTL/LTR boundaries, keyboard navigation, single/empty lists, reduced motion, mobile scrolling, modal content/focus, and link fallback behavior.
- XML parsing, JavaScript syntax, full storefront SCSS compilation, both `msgfmt --check-format` checks, and `git diff --check` passed.
- Targeted module upgrades passed on idle development database `codex_ecom_offers_20261013`, using this checkout and ports 5269/5272, with cron disabled.
- The temporary server served four review cards, the new interaction in the frontend bundle, and the new RTL styles.
- English and Arabic runtime view labels differ correctly. The validation database's pre-existing website-specific homepage copy needed its seven new view terms refreshed through Odoo's translation API; no migration or hook was added.
- The fresh frontend translation response contains the Arabic JavaScript review-position string; the temporary server needed a reload after updating the POT to clear its code-translation cache.
- Test scripts, exported POT, HTTP responses, compiled assets, and logs are retained under `/tmp/ab_review_validation/`.
- Browser rendering was unavailable. Real viewport layout, touch gestures, and native dialog behavior still need browser verification. The validation filestore also has pre-existing missing attachments.
- No business models, ACLs, or record rules changed in this task. No production package was generated; the development test harness remains outside the addon.
- The active development server on port 4092 was not upgraded or restarted for this change. Applying it there requires the normal targeted module update, translation refresh for any website-specific homepage copy, and asset reload; the working tree also contains unrelated pending module changes.
