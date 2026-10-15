# Homepage category images

Commit: `029614192448464f1f4b08a6b464962d202f631e`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/ux: refine storefront product and portal experience`

- Added the Abdin Management menu structure, including Style / Ads.

Files changed relevant to this change:

- `ab_ecommerce_storefront/views/management_menus.xml`

## Current changes before commit:

- Add Abdin Management → Style / Ads → Category Images for top-level categories with published products.
- Add image previews and a dedicated upload form using the existing category cover image already displayed by the homepage Shop by Category section.
- Prefill the editable image and list preview from the saved cover, existing category image, or the same published product selected by the homepage. Saving a replacement writes the cover; viewing or reordering does not copy fallback images into stored covers. Icon-only categories prefill an editable PNG preview of their existing Font Awesome icon; products without image data prefill their native product placeholder.
- Add nine PNG previews rendered from the existing category icon glyphs and theme colors. These previews do not replace saved covers merely by opening the screen.
- Share the homepage category/product mapping with backend previews. Read fallback products using website public permissions and website/company scope.
- Expose category sequence for ordering. Keep category identity read-only and disable creation, duplication, and deletion in this screen.
- Use primary inherited views so the standard category editor remains separate. Retain native category access permissions without additional ACLs or elevated writes.
- Translate the three new UI terms in both Arabic catalogs using exported Odoo references, preserving unrelated translations.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/views/category_image_views.xml`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/product_public_category.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-child-blue.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-flask-orange.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-heart-orange.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-heartbeat-orange.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-leaf-blue.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-leaf-green.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-medkit-green.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-plus-square-orange.png`
- `ab_ecommerce_storefront/static/src/img/category_fallbacks/fa-stethoscope-blue.png`
- `ab_ecommerce_storefront/changelog.d/2026-10-14-category-images.md`

Validation:

- Targeted module upgrade passed on the isolated `codex_ecom_offers_20261013` database with HTTP and cron disabled. Existing unrelated dependency warnings remain in the log.
- Nine rollback-only checks passed: editor form upload, denied internal/public ORM writes, public homepage cover rendering and fallback, English/Arabic labels and form controls, and isolation from the native category form, category-image autofill without cover writes, and product-image autofill matching public homepage selection while excluding unpublished products, replaceable icon previews, and native placeholder images for products without image files.
- Exported and merged the new Section Image field reference in both Arabic catalogs and the module POT. Autofill upgrade evidence: `/tmp/ab_category_image_validation/autofill-upgrade.log`; rollback validation script: `check_images.py`.
- No additional UI strings were introduced by the fallback completion. Both Arabic catalogs passed `msgfmt --check-format`; XML parsing, manifest load order, and `git diff --check` passed.
- Evidence: `/tmp/ab_category_image_validation/upgrade.log`, `check_images.py`, `check.log`, and `storefront.pot`. All nine PNG assets were verified and the stethoscope preview was visually inspected. No browser visual check was performed.
- The live database was not changed. Load the new Python code and activate the screen with a targeted `ab_ecommerce_storefront` upgrade.
