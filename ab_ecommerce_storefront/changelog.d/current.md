# Storefront change log

## Current changes before commit:

- Open Offer Drafts beside the spreadsheet import button in the Storefront Offers list as a sales manager or draft reviewer.
- Show saved review reasons and stock warnings in the reader's language, including existing drafts. Preserve product names and quantities and the original import evidence.
- All 18 offer sheet import and draft tests passed on the local Odoo 19 validation database.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/offer_draft.py`
- `ab_ecommerce_storefront/tests/test_offer_sheet_import.py`
- `ab_ecommerce_storefront/views/offer_sheet_views.xml`

## November demo verification — 2026-11-24

- Deployed `002a2b0d` on `e_commerce`, upgraded only `ab_ecommerce_storefront` on `ecom19` and verified the active service. PostgreSQL custom-format backups before the feature and employee button upgrades passed `pg_restore -l` (`ecom19_before_offer_ede87d32_z92b45.dump` and `ecom19_before_offer_employee_button_M8uXpN.dump`).
- Reapplied the original November workbook with brand linking disabled. The 56 imported programs were preserved. Eight moved to stock review and 17 products were published. All seven branch-allocation drafts stayed pending. The employee overview returned 294 entries including archived records, with 216 review drafts. The 28 active manual Alejon offers remained active.
- All 23 currently valid imported promotions were represented on the public discount listing (117 products across six pages). English and Arabic shop, offer listing and product detail routes returned HTTP 200 with visible product content.
- The post-merge test suite passed all 90 tests. The follow-up employee access test passed after correcting the group XML ID. Separate HTTP 500 responses were logged for the bath and shower category URL.
- Database backups are separate from the filestore.

## Recent commits

Commit: `002a2b0d`
Author: Mohamed Fawzy
Date: 2026-11-24
Original subject: `ab_ecommerce_storefront/FIX: show offer creation to call center staff`

User-facing changes:

- Show the New Storefront Offer action to the call center employee role. Verified the rendered Odoo list architecture as a call center employee.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/tests/test_sheet_promotion.py`
- `ab_ecommerce_storefront/views/offer_sheet_views.xml`

Commit: `ede87d32`
Author: Mohamed Fawzy
Date: 2026-11-24
Original subject: `ab_ecommerce_storefront/IMP: manage and publish stock-checked offers`

User-facing changes:

- Open manual promotions, imported promotions and pending drafts from the existing Storefront Offers menu. A stock review appears once and links back to its promotion.
- Configure group size, discounted units, percentage discounts, fixed EGP unit prices and offer priority on manual product group promotions.
- Check every eligible product and the full group quantity during import and approval. Publish eligible products on the selected website. Suspend the whole current or scheduled imported promotion for review if its stock is insufficient.
- Restore the original promotion after a manager rechecks its stock. Preserve branch allocation drafts and manual product removals when reimporting.
- The targeted Odoo 19 run after integrating `be6c6b4a` passed all 90 tests on `codex_offer_worksheet_20261124_1400`.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/offer_draft.py`
- `ab_ecommerce_storefront/models/offer_overview.py`
- `ab_ecommerce_storefront/models/sheet_promotion.py`
- `ab_ecommerce_storefront/models/stock_availability.py`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/tests/test_offer_sheet_import.py`
- `ab_ecommerce_storefront/tests/test_sheet_promotion.py`
- `ab_ecommerce_storefront/views/offer_sheet_views.xml`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`
- `ab_ecommerce_storefront/wizard/offer_sheet.py`

Commit: `ceb2ca9f`
Author: Mohamed Fawzy
Date: 2026-11-24
Original subject: `ab_ecommerce_storefront/IMP: support sheet imports and group offer rates`

User-facing changes:

- Leave brand linking off by default and make the unchecked option skip brand creation and updates during offer import.
- Allow 70% and 100% second-item discounts in Storefront Offers, including a free item chosen from a mixed collection.
- Cover the brand opt-out and both discount rates with focused Odoo tests. Three new tests and all 13 offer-sheet tests passed on an isolated Odoo 19 database.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/tests/test_offer_sheet_import.py`
- `ab_ecommerce_storefront/tests/test_storefront_offers.py`
- `ab_ecommerce_storefront/wizard/offer_sheet.py`

Operational verification:

- The ecommerce server backup `/opt/odoo19/backups/ecom19_before_november_offers_20261124_103522.dump` passed `pg_restore -l` before the import.
- The November workbook import applied 56 website promotions and saved 208 review drafts. Thirty imported promotions were within their date range on 2026-11-24. The 28 existing Alejon offers remained active while the Alejon workbook rows stayed in review for missing catalog codes and name differences.
- The English and Arabic shop and an imported-offer product page returned HTTP 200 with the offer label visible.

### November offer import handoff — 2026-11-24

- The local storefront module was upgraded and the Arabic draft field «تفاصيل سبب المراجعة» was verified. After resetting the previous upload of `عروض شهر نوفمبر 2026 - Copy.xlsx`, previewing the workbook returned **36 ready offers and 228 for review**. That verification stopped at preview.
- The reset removed 228 drafts and 37 promotions (36 applied on import and one approved later), cleared 1,519 imported brand links and removed 79 unused brands created by the upload. Odoo archived the 37 discount service products. The pre-reset database backup was saved locally at `/tmp/ecom19_before_offer_retry_39yj4n4f/ecom19.dump`.
- Across 2,305 workbook codes, each code that matched an active saleable product in the website and company scope matched only one. Where both the internal reference and linked product-card code were present, they agreed.
- In Glovive’s `white friday #25` offer, roll-on codes `115474`, `115475` and `115476` each appeared under both G-Doux and GLOVIVE. For `115475`, Offer Codes row 683 lists `60 M` at 30% under G-Doux, and row 823 lists `60 ML` at 25% under GLOVIVE. Each code matched one store product.
- One workbook name appeared under two codes after normalizing spacing and case. For `LOREAL EXCELLENCE CREME NO 6`, row 2203 lists `11048`, which matched the store, and row 2196 lists `66923`, which had no eligible match. Whether the codes identify the same physical pack remains unconfirmed.

Commit: `4dfc3871`
Author: Mohamed Fawzy
Date: 2026-11-24
Original subject: `ab_ecommerce_storefront/IMP: import spreadsheet offers with draft review`

User-facing changes:

- Add the “Add Offers from a Spreadsheet” button (“اضافة العروض من شيت”) to the Discount & Loyalty list. Sales managers can choose an Excel workbook from their computer, preview its offers and apply every ready row in one action. Preserve reviewed November mappings for matching source data.
- Save uncertain rows as persistent offer drafts at import. Reviewers can correct dates, quantities, discounts and eligible products per row. Sales managers approve a website promotion or set it aside.
- Show the source of each review issue on the draft form. Reviewers see the affected product codes and names, conflicting groups or discounts, and the specific missing, unreadable or reversed dates. Earlier drafts use their saved details and identify matching November reference evidence.
- Preserve draft corrections across repeat imports. Conflicting percentages and ambiguous product selections require explicit input. Branch allocations, specific gifts and changes to existing programs remain available for separate setup.
- Remove the website selector from the spreadsheet upload dialog. The wizard assigns the current company’s default storefront automatically.
- Keep Preview Offers disabled until an Excel file is attached and disable it again if the file is cleared.
- Match codes against saleable website variants in the selected company. Show missing codes, alternate product names, ambiguous brands, overlapping dates and conflicting workbook terms before import.
- Link storefront brands to verified catalog products independently of campaign activation. Reuse brands and keep an existing catalog brand when it differs from the sheet.
- Create website promotions for approved rows, apply quantity benefits to the cheapest qualifying units and allow staff to prioritize overlapping sheet promotions. Keep fixed EGP unit prices and the customer’s loyalty balance separate.
- Reconcile newly matched codes on subsequent imports while retaining manual priority and product removals.
- Translate the preview and promotion settings into both Arabic catalogs and cover the wizard, sales permissions, pricing, company scope and repeat imports with focused tests.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/data/november_2026_offers.json`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/offer_draft.py`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/models/sheet_promotion.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/security/security_groups.xml`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_offer_sheet_import.py`
- `ab_ecommerce_storefront/tests/test_sheet_promotion.py`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/offer_sheet_views.xml`
- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`
- `ab_ecommerce_storefront/wizard/__init__.py`
- `ab_ecommerce_storefront/wizard/offer_sheet.py`
- `ab_ecommerce_storefront/wizard/offer_workbook.py`

Validation:

- All 82 targeted offer tests passed after the review-detail change. Verified all 264 November rows on a scratch catalog, including the Arabic and English draft form, the three conflicting Glovive roll-on codes on new and previously saved drafts, and reversed dates.
- All 79 targeted offer tests passed after a module upgrade on a fresh Odoo 19 database, including reviewer permissions, company isolation, individual approval and repeat imports.
- Exercised all 264 November campaigns on an isolated catalog seeded with one eligible product. One promotion was applied and 263 drafts were saved. Repeating the import preserved the counts. Verified the new import button and draft action in English and Arabic.

- Fresh installation with Arabic loaded and targeted module upgrade passed in an isolated database. The offer suites ran 75 tests, with zero failures and zero errors.
- Verified the list button and wizard footer in English and Arabic at runtime, and checked both Arabic catalogs with gettext.
- Following the Excel upload change, all 76 targeted tests passed. A browser test opened the Arabic list button, chose the original workbook using the native file picker and reached the import preview. The source file reproduced all 264 campaign entries and 2,305 codes.
- Read-only catalog reconciliation found 1,740 unique store matches for 2,305 workbook codes. Of 264 consolidated campaign entries, 104 need review of the source conditions and 153 have both clear conditions and at least one matching store product.

Commit: `f2623708`
Author: Mohamed Fawzy
Date: 2026-11-24
Original subject: `ab_ecommerce_storefront/IMP: add collection discounts and linked carousel routing`

User-facing changes:

- Add a Mix & Match Quantity Discount offer type to the Storefront Offers list and form.
- Treat the main product and additional collection products as one qualifying collection.
- Let customers combine different products or repeat the same product, then discount the cheapest configured quantity for every complete offer cycle.
- Add an independent lifetime unit allocation for the main product and every additional collection product, with zero represented as No limit.
- Add the configured purchase quantity from the selected product and automatically add the cheapest other eligible collection product as the discounted quantity.
- Skip exhausted collection products and continue with the next cheapest eligible product while enforcing allocations again during order confirmation.
- Show the collection offer on every eligible product card and product page.
- Show the other eligible collection products as responsive image links on each product page.
- Let offer managers associate any storefront offer with a same-website or shared homepage carousel slide and preview its image.
- Make the selected carousel action type (entire banner, text button, or image button) open the primary product page of the currently active offer automatically.
- Keep unpublished or archived primary products from creating broken carousel product links.
- Keep each carousel slide unambiguous by rejecting overlapping active offer links while preserving its manual CTA URL as the fallback.
- Restrict carousel choices for sales managers to slides from their allowed companies while preserving administrator access.
- Prevent overlapping active offers across every product in the collection.
- Translate the new configuration and customer-facing text in both Arabic catalogs.
- Cover repeated products, mixed products, multiple offer cycles, invalid empty collections, automatic carousel targets, overlap rejection, and carousel access isolation with focused tests.
- Protect collection-product configuration with company-scoped access rules and prevent customers from forging the internal discounted-line marker.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/second_item_offer.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/static/src/js/second_item_offer.js`
- `ab_ecommerce_storefront/tests/test_storefront_offers.py`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`

Validation:

- Python compilation, XML parsing, and `git diff --check` passed.
- The Storefront Offers test class passed 57 tests with zero failures and zero errors, including selected-action carousel routing, unpublished/archived product fallback, and overlapping-link rejection, on `scratch_ab_ecommerce_storefront_carousel_link_20261123`.
- The focused Storefront Offers test run passed 62 tests with zero failures and zero test errors on `scratch_ab_ecommerce_storefront_deploy_20261123_1`, including automatic cheapest-other selection, exhausted-product fallback, per-product confirmation limits, collection-line access control, carousel routing, and company-scoped carousel access.
- The targeted local `ecom19` upgrade completed without errors, the Arabic homepage returned HTTP 200, and runtime HTML preserved text-button, full-banner, and image-button click targets.
- The targeted module upgrade passed, and the frontend CSS bundle compiled and returned successfully with the new collection-offer selectors.
- Both Arabic catalogs passed `msgfmt --check-format`.
- The updated POT and both Arabic catalogs passed `msgfmt --check-format` after adding the per-product allocation and automatic-selection strings.
- Runtime verification returned `Carousel Slide` in English, `شريحة الكاروسيل` in `ar_001`, and the translated carousel banner label in the form view.
- Fresh installation initially hit an existing `ab_website` setup dependency on the unloaded `ar_001` language; loading that language in the scratch database allowed the targeted installation and tests to complete.
- The first test command used the system interpreter and stopped before module loading because the existing `ijson` dependency was unavailable there; rerunning with the project virtual environment completed successfully.

Commit: `90048532`
Author: Mohamed Fawzy
Date: 2026-11-22
Original subject: `ab_ecommerce_storefront/DOCS: record recent storefront changes`

User-facing changes:

- Record recent storefront changes in the module change log.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`

Commit: `0f6aaddc68297127ce1a7cc85d48bc223921c09a`
Author: Mohamed Fawzy
Date: 2026-11-22
Original subject: `ab_ecommerce_storefront/IMP: publish approved storefront terms`

- Publish the approved general and order and delivery terms in English and Arabic.
- Link the correct terms from the footer and order pages.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/2026-11-22-legal-documents.md`
- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/legal_templates.xml`
- `ab_ecommerce_storefront/views/portal.xml`

Commit: `d0e957e245c0a73071f091321deb78995aec45fc`
Author: Mohamed Fawzy
Date: 2026-11-22
Original subject: `ab_ecommerce_storefront/IMP: filter products by storefront image`

- Add a backend filter for products with a real storefront image.
- Keep placeholder images out of the filter and cover image changes and Arabic labeling.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_image_filter.py`
- `ab_ecommerce_storefront/views/ab_product_views.xml`

Commit: `ee06934a816fede8666f444a79aedff483447d5f`
Author: Mohamed Fawzy
Date: 2026-11-22
Original subject: `ab_ecommerce_storefront/IMP: improve storefront deal filters`

- Keep deal selections visible and include active price offers in Today's Deals.
- Send Offers links to the discount-filtered shop and cover the behavior with focused tests.

Files changed:

- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/static/src/js/shop_filter_draft.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/tests/test_catalog_cache.py`
- `ab_ecommerce_storefront/views/seo.xml`
- `ab_ecommerce_storefront/views/shop.xml`

Commit: `29084e7a`
Author: Mohamed Fawzy
Date: 2026-11-17
Original subject: `ab_ecommerce_storefront/I18N: translate order reference on tracking page`

- Show the existing Arabic order reference translation on the order tracking page.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `36d862ab`
Author: Mohamed Fawzy
Date: 2026-11-17
Original subject: `ab_ecommerce_storefront/FIX: keep fixed discount above one egp`

- Reject fixed discounts that leave less than EGP 1 while preserving the entered amount in the form.
- Stop a fixed-discount offer from applying after a later product price drop breaks that minimum.
- Translate the validation message in both Arabic catalogs.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/tests/test_storefront_offers.py`

Commit: `70e6da77`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_ecommerce_storefront/IMP: allow custom fixed discounts`

- Allow a custom positive EGP discount and validate it against the original product price.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/tests/test_storefront_offers.py`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`

Commit: `a6eb21e9`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_ecommerce_storefront/IMP: explain fixed offer pricing`

- Explain that a Before / After offer keeps its reduced price when the original price rises.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`

Commit: `1525c72f`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_ecommerce_storefront/IMP: add integrated customer live chat`

- Add a branded Odoo Live Chat option to the existing support menu with English and Arabic text.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/data/livechat.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/img/abdin_pharmacy_bot_avatar.jpg`
- `ab_ecommerce_storefront/static/src/js/livechat_bridge.js`
- `ab_ecommerce_storefront/static/src/js/support_widget.js`
- `ab_ecommerce_storefront/static/src/scss/livechat_theme.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/layout.xml`

Commit: `41bda170`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_ecommerce_storefront/IMP: show selectable offer benefits`

- Show eligible benefit products as selectable images on product cards and pages.

Files changed:

- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/static/src/js/second_item_offer.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/product.xml`

Commit: `1ad51b61`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_ecommerce_storefront/IMP: show cart savings before total`

- Show the original cart price and savings above the final total when an offer discounts the order.

Files changed:

- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/cart.xml`

Commit: `7bed53e8`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_ecommerce_storefront/IMP: show ordered items in customer details`

- Show ordered products, quantities, prices and total in the customer order details card.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/portal.xml`

Commit: `0ac9fffe`
Author: Mohamed Fawzy
Date: 2026-11-15
Original subject: `ab_ecommerce_storefront/IMP: support flexible storefront offers`

- Add configurable percentage, amount, second-item, and gift offers to the storefront.
- Validate offer eligibility, cart changes, and bilingual presentation.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/second_item_offer.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/storefront_offer.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/static/src/js/product_card.js`
- `ab_ecommerce_storefront/static/src/js/second_item_offer.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/tests/test_storefront_offers.py`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`

Commit: `97648978`
Author: Mohamed Fawzy
Date: 2026-11-15
Original subject: `ab_ecommerce_storefront/IMP: explain pending delivery fees`

- Show a bilingual delivery fee notice when the current charge is zero; retain nonzero charges.
- Verified checkout totals in English and Arabic on the isolated validation database.

Files changed:

- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `346bc9bd`
Author: Mohamed Fawzy
Date: 2026-11-15
Original subject: `ab_ecommerce_storefront/IMP: show shopping bag for order tracking`

- Use the shopping bag icon for desktop and mobile order tracking.

Files changed:

- `ab_ecommerce_storefront/views/layout.xml`

Commit: `420c25d9`
Author: Mohamed Fawzy
Date: 2026-11-15
Original subject: `ab_ecommerce_storefront/IMP: include sold-out products in search`

- Include matching sold-out products in text search and show full category navigation.
- Preserve the explicit availability filter and purchase restrictions.

Files changed:

- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/views/shop.xml`
- `ab_ecommerce_storefront/static/src/js/shop_filter_draft.js`
- `ab_ecommerce_storefront/tests/test_catalog_cache.py`

Commit: `653fc7c4`
Author: Mohamed Fawzy
Date: 2026-11-15
Original subject: `ab_ecommerce_storefront/FIX: advance orders when picking starts`

- Keep reserved orders in New Orders until warehouse picking begins.
- Align call center filters and tracking stages; the focused order transition test passed on the isolated validation database.

Files changed:

- `ab_ecommerce_storefront/models/order_overview.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/views/call_center_order_views.xml`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`

Commit: `f1eed94a`
Author: Mohamed Fawzy
Date: 2026-11-12
Original subject: `ab_ecommerce_storefront/IMP: publish products from uploaded image sync`

- Route uploaded folder/ZIP image synchronization through E-Plus refresh, priced product linking and publication; keep preview read-only.
- Add coverage for publication after image synchronization.

Files changed:

- `ab_ecommerce_storefront/models/image_sync_wizard.py`
- `ab_ecommerce_storefront/tests/test_image_sync_upload.py`
- `ab_ecommerce_storefront/changelog.d/current.md`

Commit: `b7f3694f`
Author: Mohamed Fawzy
Date: 2026-11-12
Original subject: `ab_ecommerce_storefront/FIX: allow full-banner carousel clicks`

- Allow carousel navigation by clicking the full banner.

Files changed:

- `ab_ecommerce_storefront/static/src/js/hero_carousel.js`

Commit: `12185093`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/DOCS: record order overview validation`

- Record the order overview's targeted validation and Arabic runtime evidence.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`

Commit: `bf8ab5c0`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/IMP: add bilingual order overview`

- Add an order overview with six operational cards, an abandoned-cart link, and a recent-orders table.
- Match the eCommerce Editor's blue/violet theme and support Arabic RTL without changing the Editor module.
- Scope counts and drilldowns to accessible website orders and companies, with direct method access checks.
- Translate the page in both Arabic catalogs using Odoo 19 POT code references and frontend markers.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/models/__init__.py`, `ab_ecommerce_storefront/models/order_overview.py`
- `ab_ecommerce_storefront/views/order_overview_views.xml`
- `ab_ecommerce_storefront/static/src/js/order_overview.js`, `ab_ecommerce_storefront/static/src/xml/order_overview.xml`, `ab_ecommerce_storefront/static/src/scss/order_overview.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`, `ab_ecommerce_storefront/i18n/ar.po`, `ab_ecommerce_storefront/i18n/ar_001.po`

Validation:

- Odoo's `PoFileReader` parsed both Arabic catalogs after correcting eleven reused code references in each file.
- Targeted `ab_ecommerce_storefront` upgrade on `ecom19` completed with exit status 0 using alternate ports 5069/5072; no upgrade errors appeared in `/tmp/ab_order_overview_upgrade.log`.
- The upgraded action and menu show `Order Overview` in `en_US` and `نظرة عامة على الطلبات` in `ar_001`; the running service responded on port 4092.
- A fresh Odoo 19 POT export verified 38 overview terms. After a targeted upgrade and graceful worker reload, the live `/web/webclient/translations` endpoint returned Arabic values for the overview heading, cards, links, and table labels.

Commit: `e1c5c126`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/DOCS: record recent storefront changes`

- Record recent storefront changes in the module changelog.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`

Commit: `e078deb7`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/FIX: center product card quantities in Firefox`

- Center product card quantity values in Firefox in Arabic and English layouts.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/homepage.xml`

Commit: `5d1d9601`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/IMP: localize Egyptian governorates across address forms`

- Show Egyptian governorates in Arabic on checkout, portal, and prescription forms and in the location picker.
- Preserve English names and state IDs while using the active page language for refreshed address options.

Files changed:

- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/res_country_state.py`
- `ab_ecommerce_storefront/models/res_partner.py`
- `ab_ecommerce_storefront/static/src/js/current_location.js`
- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

Commit: `fa0353ef`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/IMP: upload product images from device`

- Choose an image folder or ZIP file from the device, preview image matches, and synchronize after review.
- Translate the upload flow and remove the redundant Configuration heading.

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

Commit: `4bf39702`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/IMP: mark checkout email as optional`

- Show a small Optional label beside the checkout email field in English and Arabic.

Files changed:

- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Commit: `5535c659`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/FIX: stop calculating taxes on website orders`

- Use product prices without added taxes on storefront listings and checkout orders while preserving backend sales taxes.
- Clear taxes on draft website carts when opened and remove the tax line from checkout totals.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/models/sale_order_line.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_storefront_tax_free.py`
- `ab_ecommerce_storefront/views/cart.xml`

Commit: `3f8f3920`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/FIX: render order preview total in supported element`

- Fix the sales order preview error when displaying its monetary total.

Files changed:

- `ab_ecommerce_storefront/views/portal.xml`

Commit: `aa150ead`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_ecommerce_storefront/IMP: clarify checkout labels and guest details`

- Clarify cart and checkout labels, remove the guest sign-in prompt, and shorten the name field.
- Translate the new labels in both Arabic catalogs.

Files changed:

- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

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
