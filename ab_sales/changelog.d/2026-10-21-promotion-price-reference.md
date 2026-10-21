Commit: f0be9d74c19a0147b6f957b6c35dbcca35bed92a
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T14:14:36+03:00
Subject: ab_sales/fix translation

User-facing changes:
- Correct the Arabic Sales Details label on the home screen, menu and action.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-21-sales-details-translation.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po

Current changes before commit:
- Restore the local price-reference helper required by cheapest-product promotion previews, matching the branch's selected-unit price conversion.
- Keep price calculations local without adding an external database dependency.
- No user-facing strings were added or changed.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/models/ab_sales_header.py
- ab_sales/changelog.d/2026-10-21-promotion-price-reference.md
