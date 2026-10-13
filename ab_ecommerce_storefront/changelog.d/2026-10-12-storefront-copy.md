# Storefront copy and Arabic coverage

Current changes before commit:
- Replace generic homepage, product, account and payment slogans with concise, practical English and Arabic copy. Remove repeated homepage headings.
- Use light Egyptian Arabic for friendly marketing and simple Arabic for checkout, addresses, validation and order tracking.
- Rename the homepage's Best sellers heading to Browse our products: its existing query sorts by website sequence and ID, not sales volume. Rename the accessory section without claiming purchase-frequency evidence.
- Make location labels describe the existing governorate search and local address-detail input. The popup does not manage saved account addresses, so it no longer claims the customer has no saved addresses.
- Add missing translations for QWeb fragments, purchase units, category/navigation fallbacks, account pages, OTP flows, prescriptions, support and mobile controls in both Arabic catalogs.
- Translate JavaScript search/stock fallbacks, wishlist accessibility labels, carousel labels and login progress attributes through Odoo's translation mechanisms. Preserve English product names and technical file formats.
- Preserve XML IDs, routes, business logic, contact details, pricing, offer terms and medical content. Preserve prior working-tree changes and existing catalog message IDs.

Representative changes:
- Pharmacy-first eCommerce you can trust → Why choose Abdin Pharmacies? / ليه تختار صيدليات عابدين؟
- Explore → View products / عرض المنتجات
- Your payment is on its way → Waiting for payment confirmation / في انتظار تأكيد الدفع
- Search for an area, city, or governorate → Search for a governorate / ابحث عن محافظة
- CTA / Hotline → Contact us / تواصل معنا
- Arabic cart wording consistently uses السلة.

Files changed:
- `views/homepage.xml`, `views/layout.xml`: homepage, navigation, location, support and footer wording.
- `views/product.xml`, `views/shop.xml`, `views/browsing_history_templates.xml`: product browsing and actionable labels.
- `views/cart.xml`, `views/portal.xml`: checkout, payment and tracking language; replace hardcoded Arabic branches with translated English source.
- `views/auth.xml`, `controllers/auth.py`: account copy, translatable loading labels and actionable secure-link error.
- `views/contact_templates.xml`, `views/sale_order_report.xml`: contact and report footer wording.
- `static/src/js/auth.js`, `static/src/js/prescription_order.js`: customer-readable errors.
- `static/src/js/cart_selection.js`, `static/src/js/stock_warning.js`, `static/src/js/search_typewriter.js`: localized fallback and quantity messages.
- `i18n/ar.po`, `i18n/ar_001.po`: revised copy, missing translations and exact source references.
- `changelog.d/2026-10-12-storefront-copy.md`: scope and validation record.

Validation:
- Odoo 19's native XML translation extractor and XML translation renderer checked 954 current terms from templates, frontend scripts, controllers and relevant storefront models against both catalogs. No missing translations for meaningful text in this extracted scope; numeric-only fragments, example addresses and intentional brand names excluded.
- Both catalogs passed `msgfmt --check-format`, duplicate/message-ID preservation and placeholder checks.
- All 27 JavaScript files passed Node syntax checks; applicable modules also passed Odoo 19 asset transpilation and compiled syntax checks.
- 12 temporary English/Arabic JavaScript behavior checks passed for search fallback, stock alerts, quantity-limit messages with/without product names and prescription camera feedback.
- XML IDs, routes, actions, product field bindings and verified contact strings matched the pre-task snapshot across all 10 changed template files. Python syntax and `git diff --check` passed.
- No database records or product data were changed. No module upgrade, database-backed authentication/checkout suite, full asset bundle build or live desktop/mobile browser check was run. Offline XML translation rendering is not a live QWeb/browser test.

Remaining content boundaries:
- Stored carousel text/images, uploaded social-review screenshots, user-maintained category names, product names/descriptions and payment-provider display names remain unchanged. Their live Arabic content needs separate review against the running website.
- Telegram, TikTok, Panadol, email examples and JPG/PNG/WebP remain intentional Latin text. Old catalog terms are retained for compatibility, even when the current templates no longer use them.
- Native inherited Odoo content depends on the installed Arabic language and live module translations. Production rendering, RTL wrapping and runtime language behavior remain unverified until the changes are loaded into a validation environment.
