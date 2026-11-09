# Storefront change log

## Current changes before commit:

- Let administrators choose an image folder or ZIP file from their device, with upload progress and a visible file count.
- Offer only device folder and ZIP file sources, make scanning the first action, and show synchronization after a preview.
- Load the upload widget's Arabic text through Odoo's frontend translation catalog.
- Remove the redundant Configuration heading and divider from image sync, and tighten spacing around the picker.
- Preserve the existing image matching, replacement confirmation, and report while checking upload paths and limits.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/image_sync_upload.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/image_sync_wizard.py`
- `ab_ecommerce_storefront/static/src/js/image_sync_upload.js`
- `ab_ecommerce_storefront/static/src/scss/image_sync_wizard.scss`
- `ab_ecommerce_storefront/static/src/xml/image_sync_upload.xml`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_image_sync_upload.py`
- `ab_ecommerce_storefront/views/image_sync_wizard_views.xml`

## Recent commits

Commit: `075948bec2f1db6a7a77d672a2d933dec5ea216c`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_ecommerce_storefront/I18N: refresh model metadata translation references`

- Refresh existing model metadata references in both Arabic catalogs.

Files changed:

- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `1219b678fc1f7e731244c405bf7d295b37c4892f`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_ecommerce_storefront/IMP: simplify customer order tracking summaries`

- Group the order reference, status, total, and payment method without repeating details.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/portal.xml`

Commit: `f899339aa0d6558cacc882b5c03700ae1c41c75a`
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: `ab_ecommerce_storefront/FIX: keep add-to-cart text readable on hover`

- Keep Add to cart text white on its green normal, hover, and focus backgrounds.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

Commit: `a28adac1`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/FIX: allow admin deletion of staff users`

User-facing changes:

- Let administrators delete staff users and their linked tracking records together.

Files changed:

- `ab_ecommerce_storefront/models/staff_account.py`

Commit: `59f0968c`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/FIX: show published site images to staff`

User-facing changes:

- Show published homepage banners and testimonials to signed-in employees without exposing unpublished records.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/customer_testimonial.py`
- `ab_ecommerce_storefront/models/website_carousel_slide.py`

Commit: `c96161b2`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/FIX: label staff password on creation`

User-facing changes:

- Show Password instead of New Password when creating a staff user, with the Arabic label «كلمة السر».

Files changed:

- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `24b3fa7e`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: expose full staff access rights`

User-facing changes:

- Show Odoo's full application access rights, including Settings administrator access, when Website editors add or edit their own staff users.
- Keep Login From Anywhere visible but read-only in the staff form and preserve an administrator's changes to it.

Files changed:

- `ab_ecommerce_storefront/models/staff_account.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/views/staff_user_views.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `42421e75`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/FIX: enable remote sign-in for created staff`

User-facing changes:

- Let Website editors save staff users and accept Odoo's native password rules.
- Enable Login From Anywhere for new staff users while preserving an administrator's later removal.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/models/staff_account.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `ee47b4df`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: place category and staff menus in Abdin Management`

User-facing changes:

- Place eCommerce Categories under Abdin Management Products and Add Staff User directly under Abdin Management.

Files changed:

- `ab_ecommerce_storefront/views/management_menus.xml`
- `ab_ecommerce_storefront/views/staff_user_views.xml`

Commit: `a41b471b`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: let website editors set staff passwords`

User-facing changes:

- Let Website editors set temporary staff passwords and see when an invitation email was not sent.

Files changed:

- `ab_ecommerce_storefront/models/staff_account.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/views/staff_user_views.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `2ff4e9b1`
Author: Mohamed Fawzy
Date: 2026-11-02
Original subject: `ab_ecommerce_storefront/IMP: manage website staff users by creator`

User-facing changes:

- Show Website editors the staff users they created and let them update account details and Website roles.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/staff_account.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`
- `ab_ecommerce_storefront/views/staff_user_views.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `41bf67a4`
Author: Mohamed Fawzy
Date: 2026-11-01
Original subject: `ab_ecommerce_storefront/FIX: show staff user action under Site`

User-facing changes:

- Put the staff-user action under the visible Website Site menu.

Files changed:

- `ab_ecommerce_storefront/views/staff_user_views.xml`

Commit: `bae1940f`
Author: Mohamed Fawzy
Date: 2026-11-01
Original subject: `ab_ecommerce_storefront/I18N: register staff user terms in POT`

User-facing changes:

- Load the staff-user form, menu, and messages in Arabic after the module upgrade.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`

Commit: `a72f4e5f`
Author: Mohamed Fawzy
Date: 2026-11-01
Original subject: `ab_ecommerce_storefront/I18N: load staff user Arabic labels`

User-facing changes:

- Keep new staff-user translations before obsolete catalog entries in both Arabic locales.

Files changed:

- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `1630bfdd`
Author: Mohamed Fawzy
Date: 2026-11-01
Original subject: `ab_ecommerce_storefront/IMP: let website editors create staff users`

User-facing changes:

- Let Website editors add internal employee accounts for their active company from the Website menu.
- Restrict new accounts to the employee role and send Odoo's invitation when email delivery is available.

Files changed:

- `ab_ecommerce_storefront/__init__.py`
- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/views/staff_user_views.xml`
- `ab_ecommerce_storefront/wizard/__init__.py`
- `ab_ecommerce_storefront/wizard/staff_user.py`

Commit: `c41e59e5`
Author: Mohamed Fawzy
Date: 2026-10-27
Original subject: `ab_ecommerce_storefront/FIX: reserve synced Eplus stock at checkout`

User-facing changes:

- Reserve synced E-Plus stock at checkout and keep failed online payment attempts from reserving stock.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-10-27-eplus-checkout-inventory.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/payment_status.py`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/cart_hold.py`
- `ab_ecommerce_storefront/models/eplus_sync_guard.py`
- `ab_ecommerce_storefront/models/payment_transaction.py`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`
- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/views/portal.xml`

Commit: `35fe9683`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/FIX: show correct account contact details`

User-facing changes:

- Keep Google OAuth login identifiers out of the account phone field.
- Show a clear missing-value message when no phone is saved and add the customer email to personal information.
- Cover Google account contact rendering with an HTTP regression test.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/res_users.py`
- `ab_ecommerce_storefront/tests/test_auth_http.py`
- `ab_ecommerce_storefront/views/portal.xml`

Commit: `72e79437`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/FIX: keep storefront Google sign-ins portal-only`

User-facing changes:

- Mark Google OAuth requests started from the storefront as customer sign-ins.
- Create or reuse a portal-only OAuth account with a stable login even when the verified Google email matches an internal employee account.
- Reject storefront OAuth links that resolve to internal, administrator, inactive, conflicting, or unverified identities.
- Preserve the native backend OAuth flow for explicitly requested backend destinations.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/models/res_users.py`

Commit: `3a69b7d0`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/FIX: sync header location with nearest branches`

User-facing changes:

- Use the header location control to detect the visitor's area and sort the branch directory by the same coordinates.
- Explain the HTTPS requirement when browser location access is unavailable on an HTTP LAN address.

Files changed:

- `ab_ecommerce_storefront/static/src/js/current_location.js`
- `ab_ecommerce_storefront/static/src/js/branches.js`
- `ab_ecommerce_storefront/changelog.d/current.md`

Commit: `b7d91bc1`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/I18N: translate product breadcrumb fragment`

User-facing changes:

- Show the product breadcrumb's All products link in Arabic on Arabic pages.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `8122017d`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/FIX: use valid product breadcrumb selector`

User-facing changes:

- Allow the Arabic product breadcrumb translation to load on Odoo 19.

Files changed:

- `ab_ecommerce_storefront/views/product.xml`

Commit: `f688467e`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/I18N: translate product breadcrumb in Arabic`

User-facing changes:

- Translate the product breadcrumb's All products link for Arabic visitors.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/views/product.xml`

Commit: `71fa2aee`
Author: Mohamed Fawzy
Date: 2026-10-21
Original subject: `ab_ecommerce_storefront/FIX: limit shop navigation to approved categories`

User-facing changes:

- Show approved, published categories in shop and header navigation without deleting imported catalog records.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/models/catalog_cache.py`
- `ab_ecommerce_storefront/tests/test_catalog_cache.py`

Commit: `4ef5ea41`
Author: Mohamed Fawzy
Date: 2026-10-20
Original subject: `ab_ecommerce_storefront/PERF: cache catalog navigation and page fragments`

User-facing changes:

- Cache category navigation and catalog page fragments to speed up storefront browsing.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-catalog-cache.md`
- `ab_ecommerce_storefront/changelog.d/2026-10-19-catalog-loading-lifecycle.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/catalog.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/catalog_cache.py`
- `ab_ecommerce_storefront/static/src/js/catalog_cache.js`
- `ab_ecommerce_storefront/static/src/js/catalog_navigation.js`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_catalog_cache.py`
- `ab_ecommerce_storefront/views/catalog.xml`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/shop.xml`

Commit: `deea566`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: retire seeded storefront products`

User-facing changes:

- Unpublish and disable sales for the 16 original seed products while retaining product records and stock data.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/data/storefront_catalog_cleanup.xml`

Commit: `94abdb9`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: align account password mask in RTL layout`

User-facing changes:

- Align the account password mask with the RTL layout.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

Commit: `1d33b31`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: add return policy page`

User-facing changes:

- Add the public return-policy page and Arabic translations for its content.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/views/legal_templates.xml`

Commit: `a4310ef`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/ux: add customer orders center`

User-facing changes:

- Combine regular orders and prescription requests in a filterable customer order center.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/2026-09-29-customer-orders-center.md`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/js/portal_orders.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

Commit: `04fc6d3`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: reuse saved prescription delivery address`

User-facing changes:

- Reuse a complete saved delivery address for signed-in prescription customers.

Files changed:

- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

Commit: `a6f2b99`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: build category menu from published catalog`

User-facing changes:

- Build the header category menu from published catalog categories.

Files changed:

- `ab_ecommerce_storefront/models/website.py`

Commit: `b639838`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: limit purchase options to supported units`

User-facing changes:

- Limit product-card purchase options to the supported largest unit.

Files changed:

- `ab_ecommerce_storefront/models/product_template.py`


## Commits reviewed on 2026-10-05

See [the commit review](2026-10-05-commit-review.md) for commit hashes, authors, subjects, affected files, and validation. Detailed feature records remain in this folder.
