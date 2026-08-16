Current changes before commit:

- Fix sales promotion invoice and line markers so incentive programs do not write `§§§`.
- Use promotion marker products as the shared source for sales header notice and sales detail marker eligibility.
- Add UI-only required promotion ownership, compensation timing, and compensation type fields to the promotion compensation details form.
- Add Arabic translations for the new promotion ownership field and options.
- Add focused marker scope tests for specific products, normal promotions, incentives, and header marker behavior.
- Rename the compensation timing field label to `Compensation Way`.
- Replace compensation timing choices `Advance` and `Subsequent` with `Before` and `Later`.
- Replace compensation type choice `Goods` with `Products`, keeping `Cash` unchanged.
- Add Arabic translations for the changed compensation field label and selection options.

Files changed:

- ab_sales_promo/changelog.d
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
