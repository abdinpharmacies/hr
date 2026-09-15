Recent commits:

Commit: `48a14d9`
Author: Mohamed Fawzy
Date: 2026-09-13 12:46:28 +0300
Subject: ab_ecommerce_storefront/feat: organize the address page and data collected from customer

User-facing changes:

- Simplify checkout customer and address information.
- Make email and ZIP optional in the storefront address validation.

Files changed:

- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/views/layout.xml`

Commit: `d4d5023`
Author: Mohamed Fawzy
Date: 2026-09-13 12:00:51 +0300
Subject: ab_ecommerce_storefront/fix: stabilize storefront product and sticky interactions

User-facing changes:

- Stabilize product actions, price filtering, and sticky navigation.

Files changed:

- `ab_ecommerce_storefront/static/src/js/price_range_guard.js`
- `ab_ecommerce_storefront/static/src/js/product_card.js`
- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`

Current changes before commit:

- Make the original native mail.mail form the first visible Contact Us content. Remove the introductory hero, General Inquiries and Customer Support tiles, and the form-side introduction; place Business & Partnerships below the centered form, preserving validation and the branded success layout.
- Add a dedicated Business & Partnerships page with type-first progressive fields, Arabic/English content, SEO metadata, and a small footer link; do not add it to the primary shopping navigation.
- Store business submissions in ab_business_partnership, separate from general emails, with Website admin kanban/list/form/search views, responsibility, workflow stages, internal notes, chatter, and activities. CRM remains uninstalled and is not required.
- Restrict partnership management to existing Website Editor and Designer users and allowed companies. Deny public/portal direct record access; whitelist submitted fields, enforce guest CSRF, retain native CAPTCHA integration, and add a honeypot and session attempt limits.
- Reuse storefront design tokens and native website form interactions through scoped contact assets. Preserve existing unrelated header, order, checkout, payment, and invoice work.
- Consolidate the existing stashed guest tracking, prescription, confirmation, header, and delivery UI work without consuming the stashes or changing other modules.
- Keep native checkout address creation, carrier rates, payment transactions, COD confirmation, sales orders, portal access, and accounting.
- Verify guest tracking using the reference and normalized mobile number, limited to the current website/company, with session attempt limits and private responses.
- Let guests upload prescriptions without registration; never associate an unverified phone with an existing customer.
- Keep prescription submission as a request. Staff can create an idempotent native quotation after review or link an existing matching customer/company/website order.
- Protect internal notes at field level, prevent portal-created workflow records, enforce company access, and validate private image contents.
- Share one accessible vertical tracking timeline across prescription details, native order details, and confirmation.
- Derive order status from sale.order, payment status from the native transaction/provider, preparation from reserved outgoing transfers, dispatch from completed outgoing transfers, and returns from completed customer return moves.
- Preserve existing prescription-only operational delivery states for unlinked legacy requests. Linked orders use native fulfillment; no unsupported last-mile or delivery-failure state is invented.
- Show invoice view/download actions only for posted customer invoices/credit notes belonging to the order's company and billing customer; use native portal tokens.
- Restore the simplified header and delivery UI, keep existing sticky/support behavior, and prioritize tracking above the order sidebar on mobile.
- Restore the storefront header markup and sticky behavior back to the `origin/e_commerce` baseline, including the green announcement strip, location selector, wishlist, language controls, and the header Track order link requested afterward.
- Move the payment-step Back to address action out from under the Pay Now button and show it as a compact link under the order summary on desktop and mobile.
- Limit the `/shop/payment` UI change to the payment-method selection section only, keeping the surrounding checkout layout, header, stepper, address area, order summary, and native payment CTA behavior in place.
- Render native Odoo payment methods as clean selectable cards with real provider/method images, radio semantics, and preserved Odoo data attributes, inline forms, submit buttons, and transaction routes.
- Redesign the Odoo payment status page as a focused Abdin payment confirmation experience with status-aware success, pending, and failure messaging.
- Treat Cash on Delivery as its own customer-facing payment status: the order is received, no online payment has been collected, and payment is due on delivery.
- Preserve the native `/payment/status` polling container and `/shop/payment/validate` landing-route behavior while replacing the customer-facing "Skip" action with appropriate checkout CTAs.
- Add compact checkout progress, payment summary, next-step reassurance, support actions, and copy-to-clipboard feedback for payment references.
- Redesign the native Odoo sale order PDF into an Abdin-branded order confirmation with the configured website/company logo, Arabic RTL layout, customer/order/delivery sections, structured product rows, shipping treatment, totals summary, payment terms, terms link, and compact support footer.
- Add sale report presentation helpers for clean SKU, product name, description, tax-label, terms-link, and discount display without changing sale order, tax, delivery, payment, or accounting calculations.
- Bind the sale order PDF to an Abdin A4 paper format with tighter print margins so the redesigned layout prints without the default Odoo header whitespace.
- Redesign the customer-facing sale order portal page into an Abdin Pharmacy order tracking dashboard with a status hero, state-driven order journey, product cards with real Odoo product images, native totals, payment, delivery address, documents, terms, support, and redesigned chatter presentation.
- Preserve native sale order workflow, payment/sign modals, PDF detail link, invoice portal links, product quantities, prices, taxes, totals, access tokens, and portal chatter behavior while changing only presentation.
- Hide the raw Odoo breadcrumb/payment banner for storefront sale orders and keep the fallback native portal presentation for non-storefront orders.
- Add Out for delivery and Delivered as customer-facing order journey milestones while keeping the existing warehouse dispatch signal as the last confirmed backend state.
- Increase the status hero check icon responsively so the current order state is easier to read on mobile and desktop.
- Maintain English source text with Arabic translations in both PO files and merge relevant exported entries into the existing POT used by Odoo during import.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/business_partnership.py`
- `ab_ecommerce_storefront/models/prescription_order.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/security/business_partnership.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/static/src/js/business_partnership.js`
- `ab_ecommerce_storefront/static/src/js/payment_status.js`
- `ab_ecommerce_storefront/static/src/js/prescription_order.js`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/views/business_partnership_views.xml`
- `ab_ecommerce_storefront/views/contact_templates.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`
- `ab_ecommerce_storefront/views/prescription_order_views.xml`
- `ab_ecommerce_storefront/views/sale_order_report.xml`

Validation:

- The form-first Contact Us revision passed all seven transactional tests again, including first-section ordering, removed introductory tiles, the partnership CTA below the form, native submission behavior, and Arabic/English responsive checks. Final result: zero failures/errors in /tmp/ab_contact_form_first_tests.log; desktop/mobile screenshots reviewed.
- Contact and partnership validation passed seven transactional tests with zero failures or errors, including real browser submission, Arabic field errors/success, native mail dispatch interception, input validation/abuse checks, role/company isolation, and admin kanban/form rendering.
- Contact, partnership, and shared success layouts passed Arabic RTL and English LTR rendering, alignment, progressive-field, and overflow checks at 375, 390, 430, 768, 820, 1024, 1280, and 1440 pixels. Targeted upgrade, Python/XML parsing, and both Arabic PO format checks passed.
- Contact test sources are archived outside the production addon at /tmp/ab_contact_validation/tests; screenshots are in /tmp/ab_contact_browser, and the final passing run is PID 543299 in /tmp/ab_contact_tests.log. External SMTP delivery and third-party CAPTCHA challenges were not exercised.
- Python AST, XML parsing, and both msgfmt format checks passed.
- Payment back-address layout change passed XML parsing and both Arabic PO format checks.
- Payment status redesign passed XML parsing, JavaScript syntax checking, POT/Arabic PO format checks, targeted module upgrade, runtime Arabic/English rendering checks, and desktop/tablet/mobile screenshot review.
- Cash on Delivery payment status was verified against transaction `S00113`: it renders the COD-specific Arabic title, amount label, method, and status, and no longer shows payment review wording or a payment reference.
- Payment-method selector redesign passed XML parsing, POT/Arabic PO format checks, targeted `ab_ecommerce_storefront` upgrade, runtime Arabic rendering checks, Odoo payment DOM-contract checks, COD radio-selection verification, and Chrome screenshot QA at 1366, 1440, 390, and 430 pixels with no horizontal overflow.
- Sale order PDF redesign passed Python compilation, XML parsing, POT/Arabic PO format checks, targeted module upgrades with Arabic language reload, and real `sale.action_report_saleorder` PDF rendering for Arabic website order `S00111` to `/tmp/ab_sale_order_S00111.pdf`.
- The rendered sample is A4, one page, uses the real configured Abdin website logo, and was visually reviewed from `/tmp/ab_sale_order_S00111_page-1.png`; local dynamic page totals are limited by the installed unpatched wkhtmltopdf build.
- Targeted module upgrade passed with the configured virtual environment. telebot is available; the previously reported abdin_telegram import failure did not recur.
- Header restore was verified with `git show origin/e_commerce`, local `git diff`, XML parsing, targeted module upgrade, service restart, and runtime `/ar/shop` rendering: the green announcement strip renders again and the header Track order link appears as `تتبع الطلب`.
- Ten transactional HTTP/browser tests passed with zero failures or errors. Coverage includes guest and portal isolation, prescription upload/review/quotation, native checkout/COD, online payment failure/retry, dispatch/returns, and native invoice view/PDF access.
- Six customer pages passed overflow and rendering checks at 375, 390, 430, 768, 820, 1024, 1280, and 1440 pixels. Upload preview/reset and Arabic runtime labels passed.
- Existing PO source entries and nonempty translations were preserved. Test sources are archived at /tmp/ab_customer_journey_validation/tests; screenshots are under /tmp/ab_journey_browser and the final runtime log is /tmp/ab_journey_tests3.log.
- Order tracking redesign passed XML well-formedness, Python compile, Arabic PO format checks, live English/Arabic portal render checks for order `S00113`, hook checks for `modalaccept`, `print_invoice_report`, and `o_portal_chatter`, and Chrome screenshot review at 390px mobile and 1366px desktop. Targeted upgrade is currently blocked by unrelated installed module `abdin_telegram` missing Python package `telebot`, so the new PO translations are validated on disk but not imported into the live database in this run.
- The added delivery milestones passed Python AST parsing, XML well-formedness, and Arabic PO/POT format checks.
- Live payment settlement and physical camera capture were not exercised. The existing ab_store IP login policy requires a deployment decision for public-internet portal login; no authentication policy was changed.
