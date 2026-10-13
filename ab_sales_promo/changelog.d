commit f9ebc42
Author: hager yasser
Date:   Sun Aug 16 2026

    ab_sales_promo/fix: update promo compensation terminology for #1860

- Rename the compensation timing field label to `Compensation Way`.
- Replace compensation timing choices `Advance` and `Subsequent` with `Before` and `Later`.
- Replace compensation type choice `Goods` with `Products`, keeping `Cash` unchanged.
- Add Arabic translations for the changed compensation field label and selection options.

Files changed:

- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/ab_promo_program_compensation.py


commit c69ddae
Author: hagerYasser
Date:   Sun Aug 16 2026

    ab_sales_promo/feat: exclude incentives from markers and add promotion ownership

- Fix sales promotion invoice and line markers so incentive programs do not write marker text.
- Use promotion marker products as the shared source for sales header notice and sales detail marker eligibility.
- Add promotion ownership metadata to the promotion compensation form.
- Add focused marker scope tests for specific products, normal promotions, incentives, and header marker behavior.

Files changed:

- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/ab_promo_program_compensation.py
- ab_sales_promo/models/ab_sales_header_promo_inherit.py
- ab_sales_promo/tests/__init__.py
- ab_sales_promo/tests/test_ab_sales_promo_marker.py
- ab_sales_promo/views/ab_promo_program_compensation.xml


commit affa283
Author: ahmedzenhom2610
Date:   Mon Aug 3 2026

    ab_sales_promo/ FIX translation and required to false

- Kept promotion compensation fields compatible with existing records by removing backend-required flags.
- Adjusted compensation field translations.

Files changed:

- ab_sales_promo/models/ab_promo_program_compensation.py


commit 4c05fdd
Author: ahmedzenhom2610
Date:   Mon Aug 3 2026

    ab_sales_promo/ UPDs add new fields

- Added promotion compensation metadata fields and form section.
- Added Arabic translations for the compensation metadata.
- Updated focused specific promotion tests for compensation metadata compatibility.

Files changed:

- ab_sales_promo/__manifest__.py
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/__init__.py
- ab_sales_promo/models/ab_promo_program_compensation.py
- ab_sales_promo/tests/test_ab_sales_specific_promo.py
- ab_sales_promo/views/ab_promo_program_compensation.xml

## a53e7fe - hager yasser - 2026-08-23

Original commit subject: ab_sales_promo/FIX(#2168): remove promo compensation model

- Remove compensation configuration from this addon after moving ownership to Promotion Programs.
- Remove obsolete compensation view registration and translations.

Files changed:

- ab_sales_promo/__manifest__.py
- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/__init__.py
- ab_sales_promo/models/ab_promo_program_compensation.py
- ab_sales_promo/views/ab_promo_program_compensation.xml

Current changes before commit:

- Support normal promotion selection and pricing for eligible contracts while preserving contract priority when the option is disabled.
- Allocate promotion savings once, preserve zero totals, and validate promotion availability again before submission.
- Resolve Odoo virtual-record promotion references correctly and share authoritative contract-aware API totals with the POS.
- Reuse remaining-basket promotion return pricing for contract-promotion invoices, preserving zero customer liability.
- Add Arabic validation translations and translated POS error messages for both language codes.

Files changed:

- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/ab_sales_header_promo_inherit.py
- ab_sales_promo/models/ab_sales_pos_api_promo.py
- ab_sales_promo/models/ab_sales_return_promo.py
- ab_sales_promo/static/src/pos/pos_action_promo_net_patch.js

Verification:

- Isolated Odoo install and targeted upgrade; 13 rollback-only feature checks with external connections blocked and posting cursors mocked.
- POS checks in both asset orders cover payers, selection/removal, cache reload, stale responses, and promotion-only invoices.
- Both Arabic PO files pass msgfmt --check-format; runtime Arabic contract action and Allow Promotions label checked.
- No migrations, lifecycle hooks, historical repricing, or live E-Plus writes. Development checks are kept outside the addon packages.
