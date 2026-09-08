Recent commits:

Commit: `3b024b1`
Author: Mohamed Fawzy
Date: 2026-09-03 14:24:14 +0300
Subject: ab_ecommerce_storefront/fix: refine search and account profile polish

User-facing changes:

- Refine storefront search presentation.
- Polish the account profile empty-address state.

Files changed:

- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/portal.xml`

Current changes before commit:

- Remove the duplicated light input layer from the storefront search bar while keeping the custom search container stroke and Odoo search behavior.
- Refine the no-address account empty state into a centered vertical card and send the CTA directly to the add-address form.
- Consolidate homepage, shop, category, search, wishlist, and recommendation tiles into one reusable storefront product-card template.
- Present deduplicated Abdin package levels as customer-facing pack information without exposing internal large, medium, and small unit fields.
- Enable alternate unit selection only when descriptive Abdin packaging has a verified matching native Odoo sale UoM and conversion ratio.
- Add data-driven quick-add, unavailable, configurable, discounted, quantity, loading, success, error, and wishlist states.
- Reuse Odoo's cart service and wishlist RPC routes so selected quantity, verified UoM, cart totals, and persisted wishlist state remain synchronized.
- Include the module in Odoo's frontend translation catalog so JavaScript loading, success, error, and wishlist feedback follow the active language.
- Modernize product-card density, media proportions, controls, and responsive behavior without changing product, cart, or pricing records.
- Restore the product fly-to-favorite animation after the new product-card wishlist RPC succeeds.
- Keep the custom cart toast/fly feedback connected to the redesigned quick-add button.
- Present the product-card CTA as a bottom split action with a `Buy now` label and a separate cart icon cell.
- Align the split `Buy now` CTA and cart icon colors with the Abdeen green storefront palette.
- Make product-card wishlist fly feedback target the visible header wishlist action reliably across breakpoints.
- Add a lightweight typewriter placeholder to storefront product search inputs using realistic pharmacy discovery prompts.
- Stop the animated search placeholder on focus, click, keyboard input, or entered text, and resume it only after an empty blur.
- Preserve Odoo search values, autocomplete attributes, form actions, and reduced-motion accessibility fallback.
- Replace the add-to-cart toast logo with a small animated product-into-cart motion graphic.
- Keep wishlist toast media unchanged while using the cart-specific animation only for cart additions.
- Avoid frontend loader failures from the search typewriter by resolving placeholder phrases after the page is ready.
- Keep the search placeholder prefix fixed while animating only the discovery keyword and appending trailing dots.
- Add an animated total-price display to the product detail page that follows Odoo's live unit price and selected quantity.
- Render each changed numeric character as an independent vertical roller while keeping currency symbols and separators static.
- Make increasing totals roll upward and decreasing totals roll downward with a smoother easing curve.
- Preserve RTL numeric order, reduced-motion behavior, manual quantity changes, variant changes, and existing Add to Cart behavior.
- Add a compact sticky storefront shopping header that keeps search, cart, and category navigation accessible while scrolling.
- Collapse lower-priority header controls in the sticky state while preserving the live Odoo cart badge and search form.
- Expose the existing category navigation as a compact horizontally scrollable mobile row without hardcoded categories.
- Keep the live wishlist action beside the cart in the compact sticky mobile header.
- Stabilize sticky header state changes with a measured placeholder and hysteresis to avoid flicker near the scroll boundary.
- Improve narrow mobile cart and wishlist badge placement so non-zero counters are not clipped.
- Add a floating customer support widget with WhatsApp, Messenger, and hotline actions using the requested contact destinations.
- Keep the support widget responsive, RTL-ready, keyboard closable, and offset from mobile bottom controls.
- Animate support options as sequential bubble reveals from the floating button, with RTL and reduced-motion fallbacks.
- Rotate the floating support toggle between chat and close states with a fast icon swap instead of a slow flip.
- Close floating support bubbles in reverse sequence and lock toggle colors to avoid dark icon flashes during state changes.
- Remove the extra closing spin so the support toggle rotates directly back to the chat state.
- Match desktop home and category navigation colors to the softer mobile chip style instead of white-on-green.
- Smooth the sticky header transition with a subtle drop-in motion from above when entering scroll state.
- Remove header navigation inner scrolling from 767px upward so the category dropdown opens outside the nav row instead of inside a clipped overflow area.
- Restore the desktop category toggle to its closed chip colors after closing the dropdown by separating closed, focus, and open states.
- Restore the category toggle orange underline as a hover-only affordance, with the menu opening directly below the trigger.
- Replace the hardcoded homepage carousel slides with active records from `ab_website_carousel_slide`, preserving sequence order and per-slide CTA links.
- Render homepage carousel images as contained non-clickable image layers instead of cropped clickable backgrounds.
- Use the native sliding carousel transition and remove storefront background-image classes from carousel slides so horizontal navigation does not distort the slide image layer.
- Render one visible carousel indicator per active admin slide, including the first `data-bs-slide-to="0"` indicator.
- Stabilize carousel pointer swipe and horizontal trackpad navigation with a scoped transition lock so swiping back and forth does not leave the carousel stuck.
- Make desktop mouse drag and mobile horizontal swipe navigate in the same direction as the gesture while preserving natural vertical page scrolling.
- Apply per-slide admin CTA X/Y position and width values to the frontend CTA overlay.
- Resolve each CTA position against the visible contained image and use physical centering in RTL layouts so backend placement remains identical across frontend screen sizes.
- Keep frontend carousel CTA placement coordinates left-to-right so RTL pages match the backend placement preview.
- Render the carousel CTA as a separate overlay, either a normal text button or an uploaded clickable image button.
- Scale Image Button artwork from the administrator's CTA Width while preserving its configured center position across responsive layouts.
- Render Link-style carousel slides as full-image links so a CTA drawn anywhere in the uploaded artwork leads to the configured destination.
- Preserve carousel drag handling when a gesture starts over a full-image slide link while allowing normal clicks to follow its destination.
- Scale text CTA font size responsively while keeping its center exactly aligned to the administrator's image-relative X/Y position.
- Honor the administrator's exact text CTA width, including compact widths, while wrapping long labels inside the button.
- Preserve native vertical page scrolling while keeping horizontal carousel swipe behavior.
- Add `ab_website_admin_content` as a storefront dependency so the homepage carousel model is available when the storefront renders.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/ir_http.py`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/static/src/js/animated_price.js`
- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`
- `ab_ecommerce_storefront/static/src/js/support_widget.js`
- `ab_ecommerce_storefront/static/src/js/product_card.js`
- `ab_ecommerce_storefront/static/src/js/search_typewriter.js`
- `ab_ecommerce_storefront/static/src/js/product_image_zoom.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/views/shop.xml`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/current.md`

Header refactor updates in this working tree:

- Simplify the storefront header hierarchy to logo, native Odoo search, account, and native Odoo cart in the main shopping row.
- Replace duplicated category dropdown plus horizontal category links with one dynamic category mega menu using existing Odoo website category routes.
- Add an `اطلب بالروشتة` storefront CTA that points to the existing contact route because no dedicated prescription upload/order route exists in the local addons.
- Move lower-priority location, wishlist, language, and contact controls out of the main shopping row and into the utility/account/mobile menu surfaces.
- Keep mobile on the native Odoo search snippet instead of the previous custom overlay search panel, preserving search form action and autocomplete attributes.
- Refactor sticky behavior so CSS owns sticky positioning and JavaScript only toggles compact visual state.
- Redesign the sticky state into a compact floating glass navigation surface instead of a full-width condensed bar.
- Morph the existing header controls by animating spacing, radius, transparency, shadow, search, actions, and category navigation.
- Improve the sticky fallback scroll listener with a passive requestAnimationFrame update.
- Fix the Sass native `min()` unit conflict that caused Odoo to serve fallback CSS with the red asset-error banner.
- Prevent closed category mega-menu markup from causing desktop horizontal overflow.
- Restore the desktop non-sticky header to the full storefront layout while preserving the floating glass sticky state.
- Align desktop category navigation to the start side of the active language direction, right in Arabic and left in English.
- Restore the original top announcement strip sizing, green gradient background, and desktop header utility placement from the pre-refactor layout.
- Restore the pre-refactor mobile and tablet header below 992px with the menu inside the action row, inline search/location below it, and no normal mobile category strip.
- Keep the green announcement strip visible below 992px in the normal header state, matching the pre-refactor layout.
- Change the sticky header morph so the sticky surface stays attached to the viewport top and only the lower corners become rounded.
- Reduce the storefront navigation strip to Home, Offers, and Prescription Order, removing category links from that navbar.
- Show the same Home, Offers, and Prescription Order navigation strip in the normal mobile and tablet header below 992px.
- Restore the desktop-only Shop by Category dropdown in the storefront navigation using the pre-refactor menu structure.
- Show the Shop by Category dropdown from 767px upward while keeping it hidden on narrower mobile screens.
- Normalize the Home and Shop by Category active colors to green backgrounds with white text and remove the extra search backing layer.
- Smooth the header-to-sticky transition with scoped enter and exit morph animations that preserve the top-attached sticky shape.
- Fix Shop by Category dropdown placement and state colors so the menu opens directly below the trigger and closed navigation items return to their non-active appearance.
- Restrict the Shop by Category orange underline to hover only so it does not remain visible after closing the dropdown.

Files changed for this header refactor:

- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

Admin storefront login fix in this working tree:

- Allow the storefront login form to submit username/email-style logins such as `admin` without blocking them with phone-number validation.
- Preserve username/email-style login values during submit instead of normalizing them through the phone formatter.
- Keep phone-only validation for signup and password-reset flows.
- Verified a direct `/web/login` POST with `admin` redirects to `/odoo`.

Files changed for this login fix:

- `ab_ecommerce_storefront/static/src/js/auth.js`

Prescription order feature in this working tree:

- Add a complete authenticated `Order by prescription` customer flow at `/prescription-order`.
- Reuse the redesigned header CTA and point it to the dedicated prescription-order page instead of the contact form.
- Allow customers to take a prescription photo on supported mobile devices or upload a JPG, PNG, or WebP image.
- Add client-side preview, replace/remove controls, disabled submit state, and friendly validation messages.
- Validate uploads server-side for required image, supported MIME type, image signature, and 8 MB maximum size.
- Create `ab.prescription.order` records with customer, user, private binary image attachment, filename, MIME type, customer note, internal note, status, portal token, and optional related sale order.
- Add the staff backend list/form/menu for reviewing requests, opening the prescription image, reading customer notes, adding internal notes, linking a sale order, and moving the status through the workflow.
- Add customer portal pages for listing prescription requests and tracking a request through received, review, Call Center confirmation, confirmed, preparing, out for delivery, and delivered states, with cancelled/rejected exception states.
- Keep prescription images behind authenticated portal routes and customer-owned record rules.
- Add Arabic translations and the exported module POT metadata needed by Odoo 19 to import the new website terms.

Files changed for this prescription order feature:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/data/prescription_sequence.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/prescription_order.py`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/security/record_rules.xml`
- `ab_ecommerce_storefront/static/src/js/prescription_order.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`
- `ab_ecommerce_storefront/views/prescription_order_views.xml`
