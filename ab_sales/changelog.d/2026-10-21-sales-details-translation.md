Commit: 44297ba3defa33f8144004f3930f838c9007fb91
Author: hossam elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T14:05:01+03:00
Subject: ab_sales:fix_rejected_bill_corrections_and_translation

User-facing changes:
- Allow correction of rejected bills and improve promotion validation feedback.
- Complete Arabic labels and messages across the sales screens.

Files changed (relevant to this follow-up):
- ab_sales/__manifest__.py
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po

Current changes before commit:
- Correct the Sales Details Arabic translation from the technical model name to تفاصيل المبيعات on the Sales home card, report menu and action title.
- Preserve the English source and update both Arabic language catalogs using the exported Odoo terms.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-21-sales-details-translation.md
