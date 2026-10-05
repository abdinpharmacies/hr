# Commit review — 2026-10-05

Commit: `324d441efc083d53b31a7057ca2683699ea05250`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `fix(storefront): stabilize responsive header and navigation scrolling`

User-facing changes:

- Correct responsive header direction, sticky transitions, and mouse/touch navigation scrolling.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-09-30-header-direction.md`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-mobile-navigation-scroll.md`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-navigation-row-scroll.md`
- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

Commit: `2126d74ebf04d49e05ad21d404c3df67d280359d`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `feat(storefront): filter the catalog by mapped shopping needs`

User-facing changes:

- Browse mapped shopping needs and preserve the selected filter through pagination.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-04-taxonomy-shop-needs.md`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/views/shop.xml`

Commit: `8ce08b911829b93a7dcd931091fd32cbf6e322ae`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `feat(storefront): add paginated offers and accurate promotion badges`

User-facing changes:

- Browse paginated offers with eligible promotion badges and before/after prices.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-01-offers.md`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/static/src/js/product_image_zoom.js`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/product.xml`

Commit: `c32e8d72ba9018cf21689e719128ea866d82e21a`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `fix(storefront): keep search suggestions visible and simplify filtered pages`

User-facing changes:

- Keep suggestions below the search field and hide the assurance strip on filtered pages.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-09-30-shop-search-suggestions.md`
- `ab_ecommerce_storefront/changelog.d/2026-10-04-shop-search-assurance.md`
- `ab_ecommerce_storefront/static/src/js/search_autocomplete_clear.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/shop.xml`

Commit: `089f47d6e6ecf53c059d4422736daf7950345c68`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `fix(storefront): reveal adjacent feedback cards on narrow phones`

User-facing changes:

- Expose the next feedback card on narrow phones.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-01-mobile-feedback-cards.md`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

Commit: `73504adabe4a5f91e8934db8f10825b0491e5b52`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `feat(prescriptions): capture photos from a live camera preview`

User-facing changes:

- Capture prescription photos through a live camera preview with retry guidance.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-05-prescription-camera.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/js/prescription_order.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

Commit: `71aa0f041c7eedf963ed157b3025a0a1eee4ce31`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `fix(portal): align order cards and use consistent progress links`

User-facing changes:

- Align customer order statuses and use consistent View progress links.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-05-order-cards.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/portal.xml`

Commit: `9ac7093252e50a33fc7594acfb59a4dcca69cac9`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `feat(auth): add verified email and Telegram account recovery`

User-facing changes:

- Verify email and Telegram identities, recover accounts, and manage recovery methods from the account dashboard.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-authentication.md`
- `ab_ecommerce_storefront/changelog.d/2026-10-01-account-security-dashboard.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/controllers/auth_security.py`
- `ab_ecommerce_storefront/data/auth_queue.xml`
- `ab_ecommerce_storefront/docs/authentication.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/auth_channels.py`
- `ab_ecommerce_storefront/models/auth_identity.py`
- `ab_ecommerce_storefront/models/auth_service.py`
- `ab_ecommerce_storefront/models/auth_settings.py`
- `ab_ecommerce_storefront/models/res_users.py`
- `ab_ecommerce_storefront/security/auth_security.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/static/src/js/auth.js`
- `ab_ecommerce_storefront/static/src/js/auth_phone_verification.js`
- `ab_ecommerce_storefront/static/src/js/auth_proof.js`
- `ab_ecommerce_storefront/static/src/scss/auth_security_bundle.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/tests/test_authentication.py`
- `ab_ecommerce_storefront/tools/provision_auth_secrets.py`
- `ab_ecommerce_storefront/tools/telegram_development_poll.py`
- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/views/auth_security_templates.xml`
- `ab_ecommerce_storefront/views/auth_settings.xml`
- `ab_ecommerce_storefront/views/portal.xml`

## Validation during commit review

- Python, XML and JavaScript syntax checks passed; changed SCSS files compiled.
- Arabic catalogs passed `msgfmt --check-format`; no newly untranslated entries were found.
- Odoo database upgrades and browser suites were not rerun for this Git organization task. Earlier validation results remain in the feature records.
- Preserved the existing View order and View prescription details translation entries in both Arabic catalogs.

## Current changes before commit:

- Record the reviewed commits and distinguish current checks from earlier implementation validation.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-05-commit-review.md`
- `ab_ecommerce_storefront/changelog.d/current.md`
