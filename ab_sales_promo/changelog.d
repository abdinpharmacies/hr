Commit: a0fccb9feb17db4b5e169396b035a2e5ce3f9787
Author: hossam elsheikh
Date: 2026-10-21T14:05:01+03:00
Subject: ab_sales_promo:fix_quantity_validation_and_translation

User-facing changes:
- Align POS promotion previews with submission quantity validation.
- Improve promotion feedback and Arabic translations.

Files changed:
- ab_sales_promo/__manifest__.py
- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/ab_sales_header_promo_inherit.py
- ab_sales_promo/models/ab_sales_pos_api_promo.py
- ab_sales_promo/models/callcenter_promo_snapshot.py
- ab_sales_promo/static/src/pos/pos_action_promo_inherit.xml
- ab_sales_promo/static/src/pos/pos_action_promo_net_patch.js
- ab_sales_promo/static/src/pos/pos_promo_panel.js
- ab_sales_promo/static/src/pos/pos_promo_panel.scss
- ab_sales_promo/static/src/pos/pos_promo_panel.xml

Commit: 5a1781ba92a9519d347def4ab2cf3ad23110eb08
Author: Hossam Elsheikh
Date: 2026-10-20T15:34:01+03:00
Subject: ab_sales_promo/feat: update promotion eligibility and freeze totals on callcenter submission

User-facing changes:
- Apply customer and contract promotion eligibility rules.
- Freeze promotion totals when callcenter invoices are submitted.

Files changed:
- ab_sales_promo/__manifest__.py
- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/__init__.py
- ab_sales_promo/models/ab_sales_header_promo_inherit.py
- ab_sales_promo/models/ab_sales_pos_api_promo.py
- ab_sales_promo/models/ab_sales_return_promo.py
- ab_sales_promo/models/callcenter_promo_snapshot.py
- ab_sales_promo/static/src/pos/pos_action_promo_net_patch.js

Current changes before commit:
- Remove the retired Excel promotion wizard menu and access rule.
- Remove approval attachment values from the specific-product promotion test fixture.
- Accept the employee session token before calculating promotion previews, preserving session and store authorization.
- Keep server-side submission validation on the internal promotion calculation path.

Files changed:
- ab_sales_promo/changelog.d
- ab_sales_promo/models/ab_sales_pos_api_promo.py
- ab_sales_promo/security/ir.model.access.csv
- ab_sales_promo/tests/test_ab_sales_specific_promo.py
- ab_sales_promo/views/menus.xml
