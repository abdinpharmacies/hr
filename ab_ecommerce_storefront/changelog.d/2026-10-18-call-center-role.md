# Call Center access

## Recent relevant commit

Commit: `f32413527ebe6a5dbce219de10d70d29cc953b7d`
Author: Mohamed Fawzy
Date: 2026-09-20
Original subject: `ab_ecommerce_storefront/feat: add call center order workspace`

User-facing changes:

- Add the call center order workspace with payment, prescription, and delivery information.
- Add operational order filters and delivery coordination actions.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/static/src/js/call_center_order_workspace.js`
- `ab_ecommerce_storefront/static/src/scss/call_center_order_workspace.scss`
- `ab_ecommerce_storefront/static/src/xml/call_center_order_workspace.xml`
- `ab_ecommerce_storefront/views/call_center_order_views.xml`

## Current changes before commit:

- Add an assignable `eCommerce Storefront / Call Center` role in the standard user Access Rights screen, with English and Arabic labels.
- Give the role access to all active Abdin Management menus: orders, contact requests, business partnerships, homepage slides, category images, product ribbons, social comments, offers, and product/stock listings.
- Allow staff to coordinate website orders assigned to other employees and their order lines, while retaining native company rules and ordinary salesperson restrictions for other orders.
- Allow contact and partnership follow-up, including internal notes, and storefront content/offer management through explicit model permissions. New ACLs do not grant deletion.
- Limit website-specific carousel slides, social comments, and category images to allowed companies; keep shared content available.
- Allow Call Center staff to mark website orders delivered after the existing delivery validation, retaining the Sales Administrator path and the recorded delivery actor/date.
- Reuse the ordinary salesperson role without granting Sales Administrator, Website Designer, system administration, or inventory administration. Existing technical integration restrictions remain in place.
- Preserve unrelated storefront changes already present in the working tree.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/security/security_groups.xml`
- `ab_ecommerce_storefront/security/call_center_rules.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/models/business_partnership.py`
- `ab_ecommerce_storefront/models/contact_message.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/views/business_partnership_views.xml`
- `ab_ecommerce_storefront/views/call_center_order_views.xml`
- `ab_ecommerce_storefront/views/category_image_views.xml`
- `ab_ecommerce_storefront/views/contact_message_views.xml`
- `ab_ecommerce_storefront/views/customer_testimonial_views.xml`
- `ab_ecommerce_storefront/views/management_menus.xml`
- `ab_ecommerce_storefront/views/storefront_offer_views.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-call-center-role.md`

Validation:

- Targeted module upgrade passed on idle development database `ecom19_home_ux_20261015`, using this checkout, ports 5369/5372, no HTTP, no workers, and no cron threads.
- Eleven rollback-only TransactionCase tests passed with zero failures/errors, covering all 21 active management menus and their list/form views, role inheritance, operational ACLs, forbidden deletion, contact/partnership internal notes, content edits, price/gift offers, prescription coordination, delivery guards, website order headers/lines, company isolation, authentication-record denial, and runtime English/Arabic role labels.
- Delivery completion was tested with mocked completed warehouse operations; no physical stock movement or external integration was executed.
- Exported the module POT with Odoo 19 and appended only the three new terms to the existing POT and both Arabic catalogs. Both catalogs passed `msgfmt --check-format`.
- Changed Python and all manifest XML parsed successfully; manifest paths/load order and `git diff --check` passed.
- Reproducible test harness, exported POT, configuration, and logs are under `/tmp/ab-call-center-validation/`; development tests are outside the runtime addon.
- The active `ecom19` database/server was not upgraded or restarted. Activation requires the normal Python reload and targeted storefront module upgrade.
- No production package, commit, or live user assignment was created.
