# Storefront offer management

Commit: `1bcd5f4c4ea14ec503933c7856e933346285db25`
Author: Mohamed Fawzy
Date: 2026-10-05
Original subject: `ab_ecommerce_storefront/feat: add paginated offers and accurate promotion badges`

- Added the paginated offers page, native promotion badges and comparison prices reused by this change.

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

## Current changes before commit:

- Add Abdin Management → Offers → Storefront Offers, with product, website, validity dates and archival controls.
- Add same-product gift offers with paid/free quantities and native Odoo rewards applied automatically in the cart.
- Add original/reduced prices using a native fixed-price rule for the selected website pricelist. Retain exact decimal prices and display the original price crossed out; product master prices remain unchanged.
- Autofill Price Before from the selected product's original sales price, converted to the selected pricelist currency. Keep the saved value as a snapshot rather than changing existing offers when the product's master price changes.
- Add Discount (%) with two-way updates between the percentage and Price After in the form and ORM. Round the resulting price to the currency precision and preserve explicitly entered final prices.
- Prefill Website when the current company has exactly one website, and select its first active compatible pricelist by sequence. Keep both fields visible and editable; website changes select the corresponding pricelist.
- Add the module-owned Website Standard Pricelist (EGP) for the default website. It uses catalog prices without discount rules, leaves the archived test pricelist untouched, and preserves subsequent administrator configuration through `noupdate`.
- Expose Sequence in the offer form and list. Show eligible configured offers in ascending sequence, with stable ties and pagination, ahead of other automatic offers. Keep website/company, publication and date checks.
- Enable the native Pricelists feature through module security XML so fresh visitors select the active website pricelist and see/apply configured price offers. Use an additive XML ORM update because the existing catalog data protects the base group XML ID with `noupdate`.
- Give active storefront price rules priority for their selected product and pricelist. Exclude them from other websites and non-website sales.
- Allow linking an existing automatic Odoo same-product gift promotion or an uncapped product-specific percentage discount valid from one unit. Linked programs retain their own eligibility, dates and archival controls; no duplicate program or price rule is created.
- Prevent invalid quantities, invalid prices and overlapping configured storefront offers for the same product and website. Only single-variant sale products are supported.
- Limit management to Sales Administrators and System Administrators, enforce allowed companies, and retain price changes with old/new values, actor and timestamp in chatter.
- Translate all 70 affected terms/references in both Arabic catalogs while preserving existing translations and unrelated working-tree changes.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/data/storefront_pricelist.xml`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/security/storefront_pricing.xml`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-13-offer-management.md`

Validation:

- Targeted module upgrade passed on neutralized database `codex_ecom_offers_20261013`, cloned from the existing translation validation database, using ports 5169/5172 with workers and cron disabled.
- 28 rollback-only ORM/form/rendering tests passed: gifts and thresholds, expiry, exact price precedence, taxed card/product/cart prices, existing cart repricing after archive, linked discounts, both offer-card languages, manager/admin and denied-user access, company/website isolation, shared-pricelist rejection, invalid values, overlaps, price audit history, original-price autofill, two-way percentage edits, rounding, currency conversion, form/ORM defaults, explicit pricelist selection, website changes, archived-list exclusion standard catalog pricing, native pricelist selection for a fresh public visitor and cart, sequence changes/ties across pages, and ordered-offer eligibility.
- Exported the Odoo POT, checked all 70 offer terms in both catalogs, and passed `msgfmt --check-format`. Scoped imports replaced English fallback values created by the validation upgrades; runtime `ar_001` action, form and field labels, including Discount (%), passed.
- Python/XML parsing, manifest load order and `git diff --check` passed. Existing unrelated dependency warnings remain in the upgrade log.
- No browser surface was available; QWeb rendering and ORM view checks passed, but visual browser layout was not checked.
- Development evidence: `/tmp/ab_offer_validation/test_offers.py`, `/tmp/ab_offer_validation/autofill-test-results.txt`, and `/tmp/ab_offer_validation/autofill-upgrade.log`. Tests are outside the runtime addon.
- Default-selection validation: targeted upgrade in `/tmp/ab_offer_validation/defaults-upgrade.log`; the default-selection test script passed 25 tests before the sequence expansion. The new pricelist is created only when the module data is loaded.
- Sequence and visibility validation: targeted upgrade in `/tmp/ab_offer_validation/sequence-upgrade.log`; 28-test results in `/tmp/ab_offer_validation/sequence-test-results.txt`. Exported `/tmp/ab_offer_validation/storefront-sequence.pot` confirms the existing Sequence translation reference in both Arabic catalogs; runtime `ar_001` Sequence is `التسلسل`.
- Read-only diagnostics of `ecom19` confirmed its saved price offer was valid and published, but native pricelist selection returned empty because the Pricelists feature was disabled.
- The running `ecom19` service and database were not changed. Activation requires loading the new Python code and a targeted `ab_ecommerce_storefront` upgrade.
