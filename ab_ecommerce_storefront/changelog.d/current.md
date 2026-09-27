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
- Limit the public company inquiry form to New Contract and Other requests, while preserving legacy partnership records in the admin views.
- Remove the redundant new-contract information card above the company contract request form.
- Remove the extra hero CTA button from the company contract request page.
- Store business submissions in ab_business_partnership, separate from general emails, with Website admin kanban/list/form/search views, responsibility, workflow stages, internal notes, chatter, and activities. CRM remains uninstalled and is not required.
- Restrict partnership management to existing Website Editor and Designer users and allowed companies. Deny public/portal direct record access; whitelist submitted fields, enforce guest CSRF, retain native CAPTCHA integration, and add a honeypot and session attempt limits.
- Reuse storefront design tokens and native website form interactions through scoped contact assets. Preserve existing unrelated header, order, checkout, payment, and invoice work.
- Consolidate the existing stashed guest tracking, prescription, confirmation, header, and delivery UI work without consuming the stashes or changing other modules.
- Keep native checkout address creation, carrier rates, payment transactions, COD confirmation, sales orders, portal access, and accounting.
- Verify guest tracking using the reference and normalized mobile number, limited to the current website/company, with session attempt limits and private responses.
- Let guests upload prescriptions without registration; never associate an unverified phone with an existing customer.
- Reorder the prescription request form so the prescription image upload comes first, followed by customer information and then delivery address.
- Place prescription notes inside the first prescription image section directly below the image selector.
- Keep prescription submission as a request. Staff can create an idempotent native quotation after review or link an existing matching customer/company/website order.
- Keep prescription-linked admin and customer timelines on the same seven-step structure and the same customer-facing milestone copy.
- Protect internal notes at field level, prevent portal-created workflow records, enforce company access, and validate private image contents.
- Share one accessible vertical tracking timeline across prescription details, native order details, and confirmation.
- Derive order status from sale.order, payment status from the native transaction/provider, preparation from reserved outgoing transfers, dispatch from completed outgoing transfers, and returns from completed customer return moves.
- Preserve existing prescription-only operational delivery states for unlinked legacy requests. Linked orders use native fulfillment; no unsupported last-mile or delivery-failure state is invented.
- Show invoice view/download actions only for posted customer invoices/credit notes belonging to the order's company and billing customer; use native portal tokens.
- Restore the simplified header and delivery UI, keep existing sticky/support behavior, and prioritize tracking above the order sidebar on mobile.
- Restore the storefront header markup and sticky behavior back to the `origin/e_commerce` baseline, including the green announcement strip, location selector, wishlist, language controls, and the header Track order link requested afterward.
- Point the footer Track Order link to the same public order tracking page used by the header, so guests can track orders without being sent to account orders.
- Move the payment-step Back to address action out from under the Pay Now button and show it as a compact link under the order summary on desktop and mobile.
- Hide the checkout delivery-method selector from the storefront while leaving the code in place and without auto-selecting or preferring a specific carrier.
- Align the cart quantity trash icon visually with the quantity controls when the minus action removes the line.
- Limit the `/shop/payment` UI change to the payment-method selection section only, keeping the surrounding checkout layout, header, stepper, address area, order summary, and native payment CTA behavior in place.
- Render native Odoo payment methods as clean selectable cards with real provider/method images, radio semantics, and preserved Odoo data attributes, inline forms, submit buttons, and transaction routes.
- Redesign the Odoo payment status page as a focused Abdin payment confirmation experience with status-aware success, pending, and failure messaging.
- Treat Cash on Delivery as its own customer-facing payment status: the order is received, no online payment has been collected, and payment is due on delivery.
- Preserve the native `/payment/status` polling container and `/shop/payment/validate` landing-route behavior while replacing the customer-facing "Skip" action with appropriate checkout CTAs.
- Add compact checkout progress, payment summary, next-step reassurance, support actions, and copy-to-clipboard feedback for payment references.
- Show the reusable storefront action toast after copying the order number or payment reference from the payment status summary.
- Update the received-order status copy to reassure customers that the team will contact them soon.
- Redesign the native Odoo sale order PDF into an Abdin-branded order confirmation with the configured website/company logo, Arabic RTL layout, customer/order/delivery sections, structured product rows, shipping treatment, totals summary, payment terms, terms link, and compact support footer.
- Add sale report presentation helpers for clean SKU, product name, description, tax-label, terms-link, and discount display without changing sale order, tax, delivery, payment, or accounting calculations.
- Bind the sale order PDF to an Abdin A4 paper format with tighter print margins so the redesigned layout prints without the default Odoo header whitespace.
- Redesign the customer-facing sale order portal page into an Abdin Pharmacy order tracking dashboard with a status hero, state-driven order journey, product cards with real Odoo product images, native totals, payment, delivery address, documents, terms, support, and redesigned chatter presentation.
- Preserve native sale order workflow, payment/sign modals, PDF detail link, invoice portal links, product quantities, prices, taxes, totals, access tokens, and portal chatter behavior while changing only presentation.
- Hide the raw Odoo breadcrumb/payment banner for storefront sale orders and keep the fallback native portal presentation for non-storefront orders.
- Replace the cancelled storefront order quotation warning with order-specific copy and a home-page `Continue browsing` link.
- Reflow storefront order details from 992px upward so the dashboard uses the full portal width, hides the duplicated native portal sidebar, keeps Delivery Destination and Order Summary as two separate cards, and gives Arabic-first labels, secondary English labels, clear totals, non-duplicated payment method text, and clean order metadata hierarchy.
- Add Out for delivery and Delivered as customer-facing order journey milestones while keeping the existing warehouse dispatch signal as the last confirmed backend state.
- Close the customer-facing order journey visually when the admin marks the order as delivered, so the Delivered step renders as completed instead of current.
- Increase the status hero check icon responsively so the current order state is easier to read on mobile and desktop.
- Add a non-sequential public tracking reference for storefront sales orders and prescription requests, using short random `NO-DDMMYY-XXXXXX` / `RO-DDMMYY-XXXXXX` style references while keeping native Odoo order and prescription numbers unchanged for internal operations.
- Let guests track orders and prescriptions by the new public reference while preserving legacy lookup by native order number, customer reference, or prescription number.
- Show the public tracking reference to staff in call-center order lists, search, forms, and the call-center workspace, and show it to customers in confirmation, payment status, account, order tracking, and prescription tracking surfaces.
- Add a new Abdin Management Website admin tab that groups eCommerce orders, Contact Us inboxes, homepage carousel ads, and Abdin/Eplus product inventory menus under dedicated sections.
- Replace the homepage offers source with active eCommerce Discount, Loyalty, Gift Card, and eWallet programs instead of Product Ribbons or seeded compare-price markers.
- Show products in Current Offers when they are matched by loyalty program rules, specific discount rewards, free-product rewards, gift-card trigger products, or eWallet trigger products.
- Add visible storefront offer programs for personal care discounts, baby-care buy-two-get-one, beauty loyalty points, gift cards, and eWallet top-ups so the offers section has real Odoo promotion data to display.
- Show `Your orders` instead of `Track order` in the storefront header and mobile menu for signed-in customers, linking them to their account orders while keeping guest tracking public.
- Let signed-in prescription customers choose the delivery governorate, city, and detailed address; store the submitted location as a native Odoo delivery address and reuse matching saved addresses where possible.
- Install and use Odoo's native `auth_oauth` support for storefront authentication, keeping `/auth_oauth/signin`, native provider records, OAuth user matching, signup creation, and session authentication under Odoo control.
- Expose native Google OAuth in the storefront login, register, and reset-password OAuth slots when the Google provider is enabled in Odoo Settings, without hard-coding client credentials or replacing email/phone password login.
- Keep the storefront OAuth display scoped to the native Google provider for public storefront auth pages and hide unrelated passkey-only auth blocks that were previously suppressed by the storefront auth CSS.
- Stop validating and shaking the storefront phone field on blur; phone errors now appear only after submitting login/signup with invalid data.
- Let admins click the prescription thumbnail in the call-center order workspace to preview the uploaded prescription image in a centered dialog, with a single dialog scrollbar and click-to-zoom focus on the hovered image area.
- Align the prescription preview zoom lens to the actual displayed image instead of the outer dialog frame, so the green focus square stays directly under the mouse.
- Stop attaching PDF files to customer messages for storefront orders and prescription requests while keeping the PDF report definitions available in Odoo for future reuse.
- Skip storefront customer PDF report rendering before opening or sending the admin mail composer, preventing confirmed prescription orders such as `S00143` from hanging while `wkhtmltopdf` builds a PDF that will not be sent.
- Use a dedicated first customer email for prescription-linked storefront orders so customers see a received-prescription message instead of a quotation/order amount message before pharmacy review.
- Make the prescription timeline staff-driven: new requests show prescription received as complete and review as current, sending the first customer message advances to waiting for call-center confirmation, and staff can advance to confirmed after the customer call.
- Update the prescription customer message copy to say the request has been reviewed and that Call Center will contact the customer for final confirmation.
- Stop exposing internal prescription request numbers such as `PR-000064` in customer-facing order details, PDFs, and call-center prescription cards; use the public `RX-...` prescription tracking reference for customer handling while keeping native `S...` sale order numbers internal to Odoo.
- Maintain English source text with Arabic translations in both PO files and merge relevant exported entries into the existing POT used by Odoo during import.
- Add a customer-facing Recently Viewed / Browsing History experience with localStorage guest history, authenticated server history, login merge, clear history, dedicated history page, search, loading/empty/error states, and product-card reuse.
- Record genuine product detail views only, deduplicate recently viewed products, keep most-recent ordering, cap history at 30 products, and avoid storing product names, prices, images, stock, or other product payloads in the browser.
- Place the Recently Viewed rail after lower-priority discovery content on the homepage, shop pages, and product detail pages without changing checkout, payment, product pricing, stock, cart, or wishlist behavior.
- Fix the browsing-history search width SCSS so Odoo's frontend asset compiler no longer evaluates mixed `%` and `px` units.
- Replace the quantity stepper in browsing-history product cards with a scoped secondary Remove action that deletes the product from local guest history or the authenticated customer's server history.
- Give Recently Viewed removal a stronger staged animation with a tactile card response, product-color vortex ribbons, dense image particles, an outward color burst, an animated success state, reduced-motion support, and a smooth card exit while keeping deletion in the full-width Remove action.
- Keep the Recently Viewed search icon separate from its placeholder in Arabic RTL and English LTR layouts by using direction-aware input spacing.
- Remove Favorites through the existing product-ID JSON-RPC endpoint in one request, replace the active heart in-place with an immediate button-anchored heart-break effect that stays on the selected product in RTL and LTR, collapse confirmed Favorites-page cards, restore failed removals, and prevent duplicate requests across product cards and product pages.
- Replace footer social placeholder links with the real Facebook, Instagram, TikTok, and LinkedIn destinations, and add a TikTok footer icon.
- Replace the static homepage testimonials with an admin-managed Social Proof section based on real social-platform comment screenshots.
- Add a Website admin social-comment manager where editors can upload screenshots, add source URLs, review the detected Facebook/Instagram/TikTok platform, customer metadata, reorder records, publish/unpublish, preview, edit, and delete comments.
- Detect the comment platform from normalized source URL hostnames for Facebook, Instagram, and TikTok, and reject unsupported source URLs with a clear validation message.
- Hide the storefront social-comment section when no published screenshots exist; show published website-scoped screenshots in a responsive desktop comment wall and mobile horizontal feed with platform-aware source links.
- Redesign the storefront presentation from generic testimonial cards into a premium social comment wall with platform badges, comment-thread styling, screenshot-first framing, subtle staggered placement, and restrained platform accents.
- Add public/portal read-only access limited to published testimonials while keeping management permissions restricted to Website Designer users.
- Add Arabic translations for the new social-comment model, admin views, validation messages, dynamic platform labels, and storefront copy in both Arabic language files.
- Let the desktop product filter sidebar scroll as normal page content by disabling the native sticky/viewport-height rail on the storefront shop page.
- Remove the native top category filmstrip from the storefront shop products header so categories appear only in the intended navigation/filter areas.
- Rename the mobile shop filter category accordion title to Categories and hide the duplicated category heading inside the expanded mobile dialog.
- Animate the mobile shop filter dialog closed with the same centered return motion used when it opens.
- Normalize storefront product-card internals so image, title, pack, price, quantity, and action areas keep matching heights across products with different content.
- Move the mobile/tablet shop sort control under the mobile search row and show the selected sort value below 992px.
- Align the mobile/tablet shop filter dialog trigger beside the sort control so both controls share one row below search.
- Prevent horizontal scrolling in the main storefront category navigation between 767px and 991px by allowing the nav items to shrink and wrap.
- Let the shop header and product grid use the tablet container width between 750px and 767px to avoid wasted side space at the breakpoint edge.
- Keep storefront product cards visually fixed on hover/press by removing the upward card translation while preserving border and shadow feedback.
- Apply the same quantity slide feedback used on product detail pages to storefront product-card quantity steppers, and center the quantity number inside the card input.
- Keep the full green favorite button state only while a product is favorited or removal feedback is running, so removed favorites no longer stay visually active on hover.
- Clear transient favorite-button focus/loading states after removal and keep product-card images from zooming on touch/hover interactions.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/auth.py`
- `ab_ecommerce_storefront/controllers/browsing_history.py`
- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/data/storefront_catalog.xml`
- `ab_ecommerce_storefront/data/storefront_loyalty_offers.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/browsing_history.py`
- `ab_ecommerce_storefront/models/business_partnership.py`
- `ab_ecommerce_storefront/models/customer_testimonial.py`
- `ab_ecommerce_storefront/models/mail_compose_message.py`
- `ab_ecommerce_storefront/models/mail_template.py`
- `ab_ecommerce_storefront/models/prescription_order.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/security/business_partnership.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/static/src/js/business_partnership.js`
- `ab_ecommerce_storefront/static/src/js/browsing_history.js`
- `ab_ecommerce_storefront/static/src/js/auth.js`
- `ab_ecommerce_storefront/static/src/js/payment_status.js`
- `ab_ecommerce_storefront/static/src/js/prescription_order.js`
- `ab_ecommerce_storefront/static/src/js/product_card.js`
- `ab_ecommerce_storefront/static/src/js/product_image_zoom.js`
- `ab_ecommerce_storefront/static/src/js/wishlist_removal.js`
- `ab_ecommerce_storefront/static/src/scss/call_center_order_workspace.scss`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/static/src/xml/call_center_order_workspace.xml`
- `ab_ecommerce_storefront/views/cart.xml`
- `ab_ecommerce_storefront/views/auth.xml`
- `ab_ecommerce_storefront/views/business_partnership_views.xml`
- `ab_ecommerce_storefront/views/browsing_history_templates.xml`
- `ab_ecommerce_storefront/views/call_center_order_views.xml`
- `ab_ecommerce_storefront/views/contact_templates.xml`
- `ab_ecommerce_storefront/views/customer_testimonial_views.xml`
- `ab_ecommerce_storefront/views/management_menus.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/views/shop.xml`
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
- Public tracking references passed Python compilation, XML parsing, OWL template parsing, Arabic PO format checks, targeted module upgrade, and Odoo shell verification that sale order references render as `NO-...` and prescription references render as `RO-...`.
- Header restore was verified with `git show origin/e_commerce`, local `git diff`, XML parsing, targeted module upgrade, service restart, and runtime `/ar/shop` rendering: the green announcement strip renders again and the header Track order link appears as `تتبع الطلب`.
- Ten transactional HTTP/browser tests passed with zero failures or errors. Coverage includes guest and portal isolation, prescription upload/review/quotation, native checkout/COD, online payment failure/retry, dispatch/returns, and native invoice view/PDF access.
- Six customer pages passed overflow and rendering checks at 375, 390, 430, 768, 820, 1024, 1280, and 1440 pixels. Upload preview/reset and Arabic runtime labels passed.
- Existing PO source entries and nonempty translations were preserved. Test sources are archived at /tmp/ab_customer_journey_validation/tests; screenshots are under /tmp/ab_journey_browser and the final runtime log is /tmp/ab_journey_tests3.log.
- Order tracking redesign passed XML well-formedness, Python compile, Arabic PO format checks, live English/Arabic portal render checks for order `S00113`, hook checks for `modalaccept`, `print_invoice_report`, and `o_portal_chatter`, and Chrome screenshot review at 390px mobile and 1366px desktop. Targeted upgrade is currently blocked by unrelated installed module `abdin_telegram` missing Python package `telebot`, so the new PO translations are validated on disk but not imported into the live database in this run.
- The added delivery milestones passed Python AST parsing, XML well-formedness, and Arabic PO/POT format checks.
- Header order-link and prescription delivery-address changes passed Python compilation, Python XML parsing fallback, and both Arabic PO format checks. `xmllint` is not installed in this environment.
- Hidden checkout delivery-method selector passed Python XML parsing; no carrier auto-selection or carrier preference was added.
- Browsing history passed Python AST checks for its model/controller, XML well-formedness checks for its templates and touched storefront views/security rules, JavaScript syntax checking, localStorage/sessionStorage source scan, and both Arabic PO format checks.
- Browsing-history SCSS asset regression was reproduced with the Odoo virtualenv libsass compiler using `width: min(100%, 520px)` and validated with the responsive `width: 100%; max-width: 520px` replacement. The live frontend asset route returned 200 and generated the normal compiled asset attachment; no database reset, manual database edit, or asset record cleanup was performed.
- Browsing-history Remove action passed Python compilation, JavaScript syntax checking, XML parsing, whitespace checks, and Arabic PO format checks. A targeted module upgrade on temporary ports is currently blocked by unrelated installed module `abdin_telegram` missing Python package `telebot`.
- Recently Viewed remove animation passed JavaScript syntax checking, XML parsing, frontend asset compilation, Arabic PO format checks, and a live headless-browser run that verified the vortex canvas, separated floating controls, animated success state, cleanup, and final card removal.
- Recently Viewed search spacing passed SCSS compilation and live 344px Arabic RTL/English LTR browser checks: the icon-side padding is 44px in both directions and horizontal overflow is zero.
- Targeted `ab_ecommerce_storefront` upgrade passed on temporary ports 4192/8174 using the configured virtual environment; no `-u base` was run. Runtime HTTP checks passed for `/` and `/my/browsing-history`, and the guest JSON-RPC card endpoint returned the existing storefront product card HTML.
- Guest browsing-history synchronization no longer hits an authenticated-only route; the public sync endpoint now returns a quiet no-op for guests and still merges history for signed-in users.
- Favorite removal passed a targeted module upgrade and live browser checks for immediate in-place heart replacement, exact source/effect center alignment on desktop and 390px Arabic RTL, one direct product-ID JSON-RPC request, duplicate-click locking, authoritative counter/state updates, forced network-failure restoration, product-page removal, reduced motion, and confirmed Favorites-card collapse. The final RTL regression check used the real Arabic asset bundle and confirmed the effect remains inside the clicked button instead of mirroring onto a neighboring product. No intermediate `GET /shop/wishlist` occurred during removal.
- Social Comments passed Python compilation, XML parsing, SCSS compilation, Arabic PO format checks, whitespace checks, and direct platform-detection checks for Facebook, Instagram, TikTok, invalid URLs, and empty URLs. A targeted module upgrade remains blocked before registry load by unrelated installed module `abdin_telegram` missing Python package `telebot`.
- Prescription preview zoom-lens alignment passed JavaScript syntax checking, OWL XML parsing, SCSS compilation with the Odoo virtualenv libsass compiler, and whitespace checks.
- Storefront customer-message PDF blocking passed Python compilation and whitespace checks.
- Prescription first-message template passed Python compilation, XML parsing, both Arabic PO format checks, and whitespace checks.
- Prescription workflow stage controls passed Python compilation, XML parsing, both Arabic PO format checks, and whitespace checks.
- Prescription reviewed-message copy passed XML parsing, both Arabic PO format checks, and whitespace checks.
- Native OAuth storefront wiring passed official Odoo 19 documentation/source review, manifest parsing, controller Python compilation, auth template XML parsing, storefront SCSS compilation, whitespace checks, targeted `ab_ecommerce_storefront` upgrades, read-only database verification that `auth_oauth`/`auth_signup`/`ab_ecommerce_storefront` are installed, and live `/web/login` + `/web/signup` HTML probes on port 4092.
- Google OAuth is intentionally not enabled in the database yet because no Google Client ID is configured; Odoo's native `auth_oauth.provider_google` record exists and will render on login/register after Settings enables it with the real Client ID.
- Phone field blur behavior passed JavaScript syntax checking, whitespace checks, and a targeted `ab_ecommerce_storefront` upgrade.
- Desktop shop filter sidebar behavior was verified on live `/shop` with headless Chrome: the sidebar and rail compute to `position: static`, the rail computes to `overflow-y: visible`, and `railHasInternalScroll` is false.
- Shop header/category cleanup passed XML parsing, SCSS compilation, live `/shop` HTTP 200, screenshot review, and HTML verification that no `o_wsale_categories_filmstrip` / `o_wsale_filmstrip` markup remains.
- Product-card quantity steppers passed SCSS compilation and live `/shop` DevTools checks: plus changes `1` to `2` with `ab-storefront-quantity-slide-next`, minus changes `3` to `2` with `ab-storefront-quantity-slide-prev`, and the input computes to centered grid layout with tabular numbers.
- Favorite-button active-state cleanup and fixed product-card imagery passed SCSS compilation, product-card JavaScript syntax checking, and live `/shop` HTTP 200.
- Live payment settlement and physical camera capture were not exercised. The existing ab_store IP login policy requires a deployment decision for public-internet portal login; no authentication policy was changed.
