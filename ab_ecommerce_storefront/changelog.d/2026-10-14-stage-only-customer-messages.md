# Stage-only customer messages

## Recent relevant commit

Commit: `233501548d6502c63de985c9189052f6542f8539`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/feat: add public tracking references`

User-facing changes:

- Add customer-facing order references and the prescription review message.

Files changed:

- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/data/mail_template_data.xml`

## Current changes before commit:

- Use module-owned stage-only templates for default storefront order messages, automatic confirmations, and website-linked invoice messages.
- Show the public order reference, current tracking stage, and its short description. Remove the standard confirmation product table, totals, tax, payment, and billing/shipping address details.
- Remove amounts and customer/invoice identifiers from storefront email layout subtitles; retain the public order reference.
- Reuse existing tracking stages, including preparation, dispatch, delivery, partial dispatch, cancellation, and return receipt.
- Keep the existing prescription-review workflow and simplify its next-step wording to confirming the request.
- Preserve ordinary non-website templates and the PDF-blocking behavior documented separately.
- Add the exported message terms to the POT and append seven translated entries to each Arabic catalog without replacing existing entries.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/models/account_move.py`
- `ab_ecommerce_storefront/data/mail_template_data.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-14-stage-only-customer-messages.md`

Validation:

- Targeted module upgrade and subsequent translation upgrade passed on isolated database `codex_ecom_offers_20261013`, ports 5069/5072, with HTTP and cron disabled.
- Exported the module POT through the Odoo 19 CLI before merging new translations.
- Fourteen ORM-backed tests passed in `/tmp/storefront_stage_validation.py`: the nine PDF regressions plus template selection, email headers, bilingual stage bodies, stage subjects, and runtime translation checks.
- Bilingual body checks exercised eight stages for both order and invoice templates in English and Arabic, confirming reference/stage content and absence of product tables, product images, product names, and invoice numbers.
- Runtime template names and the call-center view differed between `en_US` and `ar_001`.
- Python and XML syntax, all changed translation entries, both `msgfmt --check-format` checks, and `git diff --check` passed.
- All test records were rolled back and sending was mocked. No customer messages were sent and no development process was restarted.
- Activate on the running database with a targeted `ab_ecommerce_storefront` upgrade and load the changed Python code. Previously sent messages retain their original content.
