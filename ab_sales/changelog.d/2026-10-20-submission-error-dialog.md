Commit: b0f519ef0be53ddeaec9b6157e513615d502cef5
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:31:48+03:00
Subject: ab_sales/feat: port draft concurrency, search filters, stock freshness and annotations to API-only callcente

User-facing changes relevant to this correction:
- Ported POS behavior while retaining callcenter submission feedback; the JavaScript validation dialog component was inadvertently omitted.

Files changed (relevant source):
- ab_sales/static/src/pos/pos_action.js

Current changes before commit:
- Restore the missing AbSalesPosValidationDialog component for the existing module-owned template.
- Show validation, rejected-submission and connection-error messages without a ReferenceError; support closing and expanding the original branch response.
- Verify all three failure paths in the combined Odoo browser assets using mocked submissions: busy flags clear, the request token remains unchanged, and uncertain/rejected submissions remain attempted.
- Verify JavaScript syntax and module-local component references. Existing user-facing strings and Arabic translations are unchanged.
- No live bill submission or application database upgrade was performed.

Files changed:
- ab_sales/changelog.d/2026-10-20-submission-error-dialog.md
- ab_sales/static/src/pos/pos_action.js
