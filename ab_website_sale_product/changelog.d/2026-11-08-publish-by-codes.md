# Explicit website product publication

Commit: `339d5a323584e50001a3031002f3eceb04d2ca16`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_website_sale_product/IMP: restrict automatic product creation and publication`

- Make Add Many By Codes the explicit creation and publication workflow.
- Limit full, delta, and background synchronization to linked templates while preserving manual unpublication.
- Keep linked products unpublished when they are no longer eligible for sale.

Files changed:

- `models/ab_product.py`
- `models/add_many_by_codes_wizard.py`
- `models/website_product_sync_job.py`
- `tests/test_website_product_sync.py`
- `i18n/ab_website_sale_product.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`

Validation:

- Three creation/publication policy tests and five updated background/retry tests passed on the isolated `codex_legacy_inline_20261104` database after a targeted upgrade.
- Both Arabic catalogs passed `msgfmt --check-format`; runtime English and Arabic help text was checked.
- The full 36-test synchronization class had 33 passes, one category fixture failure, and two test-user creation errors caused by a required `res_partner.ab_storefront_avatar` column in the isolated clone.
