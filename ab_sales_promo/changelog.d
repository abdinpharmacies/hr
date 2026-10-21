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

Commit: a53e7fe853f924ead3a25c4f299f7fe69eee01ba
Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-08-23T11:57:30+03:00
Subject: ab_sales_promo/FIX(#2168): remove promo compensation model

User-facing changes:
- Move promotion compensation metadata ownership out of the sales extension.

Files changed:
- ab_sales_promo/__manifest__.py
- ab_sales_promo/changelog.d
- ab_sales_promo/i18n/ar.po
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/__init__.py
- ab_sales_promo/models/ab_promo_program_compensation.py
- ab_sales_promo/views/ab_promo_program_compensation.xml

Commit: 5a1781ba92a9519d347def4ab2cf3ad23110eb08
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:34:01+03:00
Subject: ab_sales_promo/feat: update promotion eligibility and freeze totals on callcenter submission

User-facing changes:
- Port customer/contract promotion eligibility and freeze submitted promotion totals.

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
- Display the promotion hint as a rounded red tag with white text.
- Reuse the submission quantity rule in POS previews, including product scope and unit conversion; return structured inline validation errors.
- Validate new submissions before creating a locked attempt; support changing or removing a promotion during rejected-bill correction.
- Record corrected promotion totals when a new revision is frozen; preserve manual contract promotion selection.
- Add the quantity-limit explanation to both Arabic catalogs.

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
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:34:01+03:00
Subject: ab_sales_promo/feat: update promotion eligibility and freeze totals on callcenter submission

User-facing changes:
- Add promotion eligibility checks and freeze financial totals on callcenter submission.

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
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.
- Translate dynamic screen labels, component properties and notifications at runtime, including interpolated values where applicable.
- Retain the current rejected-bill correction and promotion validation changes; show the promotion warning once as a rounded red tag.

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
