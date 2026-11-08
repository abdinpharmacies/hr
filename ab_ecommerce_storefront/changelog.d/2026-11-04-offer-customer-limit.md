# Offer deletion and customer usage limits

Commit: `667c36d0129bb79da460d90d2db7d9238d27e1b3`
Author: Mohamed Fawzy
Date: 2026-10-15
Original subject: `ab_ecommerce_storefront/IMP: add storefront gift and price offer management`

- Introduced storefront gift and price offers, generated promotion rules, company isolation, and bilingual offer management.

Files changed in that commit:

- `__manifest__.py`, `models/__init__.py`, `models/storefront_offer.py`, `models/product_template.py`, `models/website.py`
- `security/ir.model.access.csv`, `security/record_rules.xml`, `security/storefront_pricing.xml`
- `data/storefront_pricelist.xml`, `views/storefront_offer_views.xml`
- `i18n/ar.po`, `i18n/ar_001.po`, `changelog.d/2026-10-13-offer-management.md`

## Current changes before commit:

- Allow Editor and Designer and System Administrator users to delete unused offers within their allowed companies. Other existing roles retain their previous permissions.
- Remove generated price items and archive/detach generated promotions on deletion; preserve products, pricelists, orders, and externally linked promotions. Offers referenced by price lines or usage history must be archived.
- Add optional Once per Customer to the list and form, disabled by default. Apply the restriction to one confirmed order for the customer's commercial partner, including delivery contacts, for price offers, gift offers, and linked Odoo promotions.
- Retain the first confirmed use even for repeatable offers so enabling the restriction later respects tracked history. Enabling it also recovers confirmed orders with retained price-offer or promotion references; historical uses without recoverable references cannot be reconstructed.
- Keep recorded use after cancellation. Check stale carts before payment and confirmation, exclude used offers from subsequent prices and rewards, and recalculate limited offer prices when duplicating order lines.
- Enforce a unique offer/customer usage record to reject simultaneous confirmations atomically. Usage records are read-only for administrators and inaccessible to public/portal users. Confirmation remains the point of consumption; payment-provider capture/refund behavior is unchanged.
- Translate the setting, help, model/field metadata, and errors in both Arabic catalogs without replacing unrelated translations.

Files changed:

- `models/storefront_offer.py`
- `models/website.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `views/storefront_offer_views.xml`
- `i18n/ab_ecommerce_storefront.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/__init__.py`
- `tests/test_storefront_offers.py`
- `tests/check_offer_races.py`
- `changelog.d/2026-11-04-offer-customer-limit.md`

Validation:

- Targeted upgrade and 20 tests passed with zero failures/errors on isolated database `codex_offer_once_20261104`, using this checkout first in the custom addons paths, HTTP 5169/gevent 5172, workers 0, cron threads 0, and no HTTP server. Final log: `/tmp/offer-once-validation-complete.log`.
- Two independent simultaneous-confirmation scenarios passed: price and gift offers each produced one confirmed order, one blocked order, and one usage record. Log: `/tmp/offer-once-races.log`.
- Exported the module POT from Odoo; both Arabic catalogs passed `msgfmt --check-format`. Runtime `ar_001` setting/help/action/form checks passed. Odoo has no `ar` runtime language in this database; its catalog was validated statically. Log: `/tmp/offer-once-languages.log`.
- Python AST, XML parsing, and `git diff --check` passed. The isolated database has missing copied filestore images, logged during fixture creation; they did not affect these ORM tests.
- No live database upgrade, process restart, commit, or deployment. Retain tests for development/CI and exclude them from runtime distribution packages.
