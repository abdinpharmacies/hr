# Product offer presentation

Current changes before commit:
- Present the product's existing buy/free offer in a compact, softly tinted green card with a small gift icon and readable quantity equation.
- Reduce the price and offer typography, remove the orange accent and filled free-item badge, and fit the card to its content following visual feedback.
- Keep the existing automatic-gift explanation and actual promotion quantities; align the unit price with the content and remove the redundant secondary total from product pages.
- Animate only the gift glyph with a small bounce and a pause between cycles; disable the animation for reduced-motion preferences.
- Give the offer product's cart button a contrasting white label on dark brand green.
- Adapt the offer layout for narrow screens using logical spacing for Arabic and English.
- Preserve existing translations, policy destinations, promotion eligibility, prices, and cart behavior; retain the removed total's catalog entry.

Validation:
- Storefront SCSS compiled with the project's libsass; product XML parsed and `git diff --check` passed.
- Both Arabic catalogs passed `msgfmt --check-format`; no new or changed UI strings require translation.
- Development HTTP requests on port 4092 verified the new gift markup and translated explanation in Arabic and English, unchanged 1 + 2 quantities and 99.00 unit price for the supplied product, and both policy destinations.
- The served RTL frontend CSS contains the new offer rules.
- A follow-up live Arabic product request confirmed that the secondary total is absent while the 99.00 main price and gift markup remain present. Gift bounce keyframes and the equally specific reduced-motion override compile successfully.
- Measured cart label contrast is 7.75:1. The quieter offer uses existing dark-green and muted brand text colors.
- Browser visual verification remains unavailable because no browser is connected. No process restart or database upgrade was performed; the existing development server loads XML and assets from source.

Files changed:
- `views/product.xml`
- `static/src/scss/storefront.scss`
- `changelog.d/2026-10-15-product-offer-presentation.md`

Relevant commit:
- Commit: `e2f74cc90d0d2a22758b3527c18d605452c5562a`
- Author: Mohamed Fawzy
- Date: 2026-10-15
- Original subject: `ab_ecommerce_storefront/IMP: add draft terms page and product policy links`
- Added the product policy links refined by this change.
- Files changed (relevant): `views/product.xml`, `views/legal_templates.xml`, `static/src/scss/contact.scss`.
