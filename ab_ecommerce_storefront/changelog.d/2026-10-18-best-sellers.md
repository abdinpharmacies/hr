# Homepage best sellers

## Recent relevant commit

Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`

User-facing changes:

- Rename the homepage product showcase to avoid claiming sales-volume evidence.
- Simplify storefront wording in English and Arabic.

Files changed (relevant to this update):

- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`

## Current changes before commit:

- Rename the homepage product section to “Best sellers”, using the existing “الأكثر مبيعًا” translation in both Arabic catalogs.
- Rank the published catalog by all-time quantities in confirmed orders for the current website and company. Use native sales analysis to aggregate variants and normalize units of measure.
- Keep the existing four-card homepage layout and calculate prices for the ranked products.
- Exclude draft, sent, cancelled, unpublished, archived, unsaleable, and other-website/company records. Require a positive aggregate quantity and do not fill empty positions with unsold products.
- Keep elevated sales aggregation private; return product records with the caller's normal permissions without exposing sales records or quantities.

Files changed:

- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-best-sellers.md`

Validation:

- Read-only inspection of `ecom19` found 16 confirmed website orders and eight published products with positive ordered quantities. The top two were GEMCITABIN 2000MG/50ML (6) and GARNIER COLOR NATURALS 7 (2); the remaining six each had quantity 1. These are website orders, not E-Plus branch sales.
- Targeted `-u ab_ecommerce_storefront --stop-after-init --no-http --workers=0 --max-cron-threads=0 --http-port=5269 --gevent-port=5272` passed on idle development database `ecom19_home_ux_20261015` using this checkout.
- Twelve rollback-only Odoo TransactionCase tests passed: quantity ranking beyond catalog sequence, excluded order states, website isolation, company isolation, product visibility, empty results, positive totals, unit conversion, variant aggregation, public access without sales access or elevated returned records, zero limit, and English/Arabic headings.
- Odoo POT export confirmed the existing heading reference. Both unchanged Arabic catalogs passed `msgfmt --check-format`; their language headers, heading translations, and non-fuzzy entries were verified.
- Temporary HTTP validation on port 5269 returned 200 in English and Arabic. Both pages displayed the translated heading, the correct top four products, their prices, and normal purchase controls.
- Python parsing, XML parsing, and `git diff --check` passed. Logs, test harness, exported POT, and HTTP responses are under `/tmp/ab-bestsellers-validation/`.
- No production package was generated. The test harness remains outside the addon. The active server on port 4092 was not restarted or upgraded; activation there requires its normal Python reload and targeted storefront update.
