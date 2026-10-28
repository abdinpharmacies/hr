Commit: 4c1bddda3d71deceb66953a182261b2c783bcb01
Author: emadco88
Date: 2026-10-28T16:28:51+03:00
Subject: ab_promo_program/ UPD from replica19

User-facing changes:
- Update the promotion program and Excel wizard from the replica branch.
- Add attachment handling and focused wizard tests.

Files changed:
- ab_promo_program/__manifest__.py
- ab_promo_program/changelog.d
- ab_promo_program/i18n/ar.po
- ab_promo_program/models/ab_promo_program.py
- ab_promo_program/models/ab_promo_program_wiz.py
- ab_promo_program/tests/__init__.py
- ab_promo_program/tests/test_promo_program_wizard_attachments.py
- ab_promo_program/views/ab_promo_program.xml
- ab_promo_program/views/ab_promo_program_wizard.xml

Commit: 01870995fbdd8bcd8cfe097bedac4a4e279f2d2e
Author: hossam elsheikh
Date: 2026-10-21T14:05:01+03:00
Subject: ab_promo_program:fix_translation

User-facing changes:
- Add Arabic translations for the promotion module.

Files changed:
- ab_promo_program/__manifest__.py
- ab_promo_program/changelog.d
- ab_promo_program/i18n/ar.po

Current changes before commit:
- Remove supplier, budget, ownership, compensation, and approval attachment fields from promotion programs.
- Remove their form controls and retire the Excel import wizard and its access rule and tests.

Files changed:
- ab_promo_program/__manifest__.py
- ab_promo_program/changelog.d
- ab_promo_program/models/__init__.py
- ab_promo_program/models/ab_promo_program.py
- ab_promo_program/models/ab_promo_program_wiz.py
- ab_promo_program/security/ir.model.access.csv
- ab_promo_program/tests/__init__.py
- ab_promo_program/tests/test_promo_program_wizard_attachments.py
- ab_promo_program/views/ab_promo_program.xml
- ab_promo_program/views/ab_promo_program_wizard.xml
