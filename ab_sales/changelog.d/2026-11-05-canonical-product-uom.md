Current changes before commit:

- Remove unused legacy unit selection guidance from sale lines.

Files changed:

- ab_sales/changelog.d/2026-11-05-canonical-product-uom.md
- ab_sales/models/ab_sales_line.py

commit aadda16401838bb1768e9f295d6a8ab1788fb1ac
Author: hossam elsheikh <hossam.m.elsheikh@gmail.com>
Date:   2026-11-01T12:25:10+02:00

    ab_sales/fix: preserve branch store guard after POS sync

- ab_sales/fix: preserve branch store guard after POS sync.

Files changed:

- ab_sales/changelog.d/2026-10-18-empty-sales-store-access.md
- ab_sales/models/ab_sales_pos_balance_refresh.py
