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

## fecdc568 - hager yasser - 2026-10-13

Original commit subject: ab_sales_promo/FEAT(#20897): Contract-controlled promotions with a single payer (part2)

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

Current changes before commit:

- Enforce Allowed Customers during promotion discovery, application, discount evaluation, and sale validation; an empty list remains unrestricted.
- Reject restricted promotions for other, absent, and unsaved customers, including direct assignment and changes to an existing sale's customer.
- Send the selected customer through the optional POS promotion API argument and refresh promotions after customer selection, clearing, or switching to new-customer mode.
- Remove unauthorized promotions from POS responses and ignore responses evaluated for a previous customer.
- Preserve source-promotion return repricing through force_program_effective and add the validation message in both Arabic translation files.

Files changed:

- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/ab_sales_header_promo_inherit.py
- ab_sales_promo/models/ab_sales_pos_api_promo.py
- ab_sales_promo/static/src/pos/pos_action_promo_net_patch.js

Verification:

- Targeted ab_sales_promo upgrade passed in isolated database codex_promo_customers_20261015.
- Nine grouped rollback-only Odoo checks cover unrestricted and allowed customers, unauthorized and unsaved customers, computed-field invalidation, ORM writes, final validation, return repricing, existing eligibility gates, and runtime Arabic translations; E-Plus connections were blocked.
- Eight POS checks using the existing customer handlers and module patch cover requests, selection, clearing, new-customer mode, stale responses, bill switching, and read-only bills.
- Both Arabic PO files pass msgfmt --check-format; development check scripts remain outside the addon package.
