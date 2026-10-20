Commit: b0f519ef0be53ddeaec9b6157e513615d502cef5
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:31:48+03:00
Subject: ab_sales/feat: port draft concurrency, search filters, stock freshness and annotations to API-only callcente

User-facing changes relevant to this correction:
- Added stock freshness timestamps to product search results.

Files changed (relevant source):
- ab_sales/models/ab_sales_ui_api.py

Current changes before commit:
- Fix product search crashing because the callcenter POS has no `_get_store_record` helper from the E-Plus refresh module.
- Resolve an authorized active sales branch and reuse its cached branch API stock timestamps, without contacting an external system during search.
- Preserve the existing Arabic access-denied message in both catalogs and update references from the Odoo POT export.
- Verify code/name search, stock/medicine/price filters, separate branch timestamps, empty inputs and denied branch scope in an isolated Odoo database.
- Verify a targeted ab_sales upgrade in the isolated database; existing application databases and PyCharm processes remain untouched.

Files changed:
- ab_sales/changelog.d/2026-10-20-product-search-cache-fix.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_ui_api.py
