Commit: 599b58cb322653922e0f4774f6a2577dc36fa343
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T12:33:21+03:00
Subject: ab_sales_lead/fix: rename Cashier grouping to User

User-facing changes:
- Rename the former cashier grouping to User.

Files changed:
- ab_sales_lead/__manifest__.py
- ab_sales_lead/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales_lead/i18n/ar.po
- ab_sales_lead/i18n/ar_001.po
- ab_sales_lead/views/ab_sales_lead_views.xml

Current changes before commit:
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.
- Translate dynamic screen labels, component properties and notifications at runtime, including interpolated values where applicable.

Files changed:
- ab_sales_lead/__manifest__.py
- ab_sales_lead/changelog.d/2026-10-21-arabic-completion.md
- ab_sales_lead/i18n/ar.po
- ab_sales_lead/i18n/ar_001.po
- ab_sales_lead/static/src/pos/pos_lead_patch.js
- ab_sales_lead/static/src/pos/pos_lead_templates.xml
