# Secondary product policy links

Current changes before commit:
- Make Terms and Conditions and Returns and refunds links smaller and muted, with a persistent underline.
- Preserve 44 px touch targets, keyboard focus outlines, translated labels, and both policy destinations.

Validation:
- Contact SCSS compiled with the project's libsass; `git diff --check` passed.
- Live Arabic and English product HTML retained both policy links and their translated labels; the served RTL CSS includes the smaller underlined style.
- Muted text contrast against the page background measures 4.74:1.
- No source strings or translations changed. Browser-based visual verification was unavailable.

Files changed:
- `static/src/scss/contact.scss`
- `changelog.d/2026-10-15-product-policy-link-style.md`

Relevant commit:
- Commit: `e2f74cc90d0d2a22758b3527c18d605452c5562a`
- Author: Mohamed Fawzy
- Date: 2026-10-15
- Original subject: `ab_ecommerce_storefront/IMP: add draft terms page and product policy links`
- Added the product policy links refined by this change.
- Files changed (relevant): `views/product.xml`, `views/legal_templates.xml`, `static/src/scss/contact.scss`.
