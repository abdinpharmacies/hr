# Match uncoded products in JSON exports

Commit: `b14363ffd8e852f2498dab0ac6fd19c3a45ff134`
Author: Mohamed Fawzy
Date: 2026-11-09
Original subject: `ab_website_sale_product/IMP: match legacy website publication from CSV`

- Added the administrator review and apply workflow for legacy publication exports.

Files changed relevant to this update:

- `models/legacy_publication_import.py`
- `views/legacy_publication_import_views.xml`
- `tests/test_legacy_publication_import.py`

## Current changes before commit:

- Match JSON export rows without codes by their unique normalized names, as the CSV workflow does.
- Add regression coverage and Arabic translations for the shared validation message.

Files changed:

- `models/legacy_publication_import.py`
- `tests/test_legacy_publication_import.py`
- `i18n/ab_website_sale_product.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-09-json-uncoded-export.md`

Validation:

- The focused JSON uncoded-name regression test passed on local `ecom19` after a targeted module upgrade.
- Both Arabic catalogs passed `msgfmt --check-format`.
