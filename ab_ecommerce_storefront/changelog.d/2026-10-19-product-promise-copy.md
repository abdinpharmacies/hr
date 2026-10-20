# Product promise wording

Current changes before commit:
- Replace the product-page authenticity card with “With you for better health” and “All your essentials from Abdin Pharmacies.”
- Add the approved Arabic wording to both catalogs: “معاك لصحة أفضل” and “كل احتياجاتك من صيدليات عابدين”.
- Preserve existing translation entries and unrelated pending changes.

Validation:
- Parsed XML and extracted the new term using the installed Odoo 19 XML translation extractor.
- Both Arabic catalogs passed `msgfmt --check-format`; `git diff --check` passed.
- Database POT export, module upgrade, and runtime language verification were not performed.

Files changed:
- `views/product.xml`
- `i18n/ab_ecommerce_storefront.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-10-19-product-promise-copy.md`

Relevant commit:
- Commit: `949aaccee3ff14efc5a4411419f2e6ecec678d01`
- Author: Mohamed Fawzy
- Date: 2026-10-15
- Original subject: `ab_ecommerce_storefront/IMP: refine product offers and remove duplicate total`
- Refined product-page offers and removed the duplicate total.
- Files changed (relevant): `views/product.xml`
