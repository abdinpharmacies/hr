# Website invoice messages without PDF attachments

## Recent relevant commit

Commit: `233501548d6502c63de985c9189052f6542f8539`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/feat: add public tracking references`

User-facing changes:

- Exclude PDF attachments from website sales-order and prescription customer messages.

Files changed:

- `ab_ecommerce_storefront/models/mail_template.py`
- `ab_ecommerce_storefront/models/mail_compose_message.py`

## Current changes before commit:

- Extend the existing no-PDF customer-message policy to invoices associated with a website, including INV/2026/00006 for S00151.
- Remove PDF placeholders and existing PDFs from the native invoice email wizard's default attachments.
- Filter PDFs immediately before the native invoice sender posts its message, including manually supplied files, cached invoice reports, fallback reports, and PDFs without a filename extension.
- Preserve non-PDF attachments and retain standard PDF report generation and download inside Odoo.
- Preserve ordinary invoice report attachments when website and non-website records share a template/composer batch.
- Filter PDF attachment creation commands even when no existing PDF attachment IDs are supplied.
- Add no user-facing strings or permission changes. Preserve existing English source and both Arabic catalogs.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/account_move_send.py`
- `ab_ecommerce_storefront/models/mail_template.py`
- `ab_ecommerce_storefront/models/mail_compose_message.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-14-invoice-messages-without-pdf.md`

Validation:

- Read-only inspection of `ecom19` confirmed INV/2026/00006 is a posted customer invoice linked to website order S00151.
- Targeted `ab_ecommerce_storefront` upgrade passed on the isolated `codex_ecom_offers_20261013` database using ports 5069/5072, no HTTP, and disabled cron. Existing unrelated manifest/view warnings remain.
- Nine ORM-backed checks passed using `/tmp/storefront_pdf_validation.py`: invoice scope, new and cached wizard attachments, final sending guard, native fallback sending pipeline, ordinary invoice behavior, mixed template and composer batches, and composer attachment values/creation commands.
- Sending was mocked; test data and each test's changes were rolled back. No customer messages were sent.
- Four changed Python files parsed successfully; both Arabic catalogs passed `msgfmt --check-format`; `git diff --check` passed.
- No UI strings changed, so no new translations or runtime language checks were needed for this change.
- The running development server was not restarted. Load the updated Python code in that process before checking the sending behavior there.
