# Customer import review guidance

Commit: 47990e2025713ff0dd0191be2ef8e41912491356
Author: Mohamed Fawzy
Date: 2026-11-08
Original subject: ab_website_sale_product/IMP: add reviewed legacy customer imports and activation codes

- Add customer CSV review, safe normalization, eligibility checks, and activation code generation.

Files changed relevant to this follow-up:

- `models/legacy_activation_batch.py`
- `services/legacy_csv.py`
- `views/legacy_customer_views.xml`
- `docs/legacy-customers.md`

## Current changes before commit:

- Explain review CSV downloads, eligibility counts, quarantined malformed records, and rechecking existing previews.
- Announce the import warning as a status message for assistive technology.
- XML parsing passed; browser and database checks were not rerun for this follow-up. No source UI strings changed.

Files changed:

- `docs/legacy-customers.md`
- `views/legacy_customer_views.xml`
- `changelog.d/2026-11-08-review-guidance.md`
