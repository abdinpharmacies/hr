# Classification header button

## Recent relevant commit

Commit: `bd92de2a90422a41e543fab782b550ac80df0dab`
Author: Mohamed Fawzy
Date: 2026-10-05
Original commit subject: `ab_website_sale_product/feat: add queued product categorization and review workflow`

- Add the product classification dashboard and header navigation.

Files changed (relevant to this change):

- `static/src/xml/product_classification.xml`

## Current changes before commit:

- Remove the Category Descriptions button from the product classification page header in every language.
- Preserve Run History, Taxonomy Bindings, classification behavior, and concurrent dashboard changes.

Files changed:

- `static/src/xml/product_classification.xml` (header button removal only)
- `changelog.d/2026-10-06-classification-description-button.md`

Validation:

- XML parsing and whitespace checks passed.
- No new or revised user-facing strings; existing Arabic catalog entries remain intact.
- No database upgrade or synchronization operation was run for this template-only change.
