# Force categorization

## Recent relevant commit

Commit: `083e324f3b56f0cf60f0064b3645d25e3743b3f0`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_website_sale_product/docs: record website sync commits`

- Record the existing synchronization implementation history.

Files changed:

- `changelog.d/2026-09-29-website-sync-local-commits.md`

## Current changes before commit:

- Add a suggestion preview with current categories, evidence scores and editable category overrides; apply selected rows in bulk.
- Add automatic assignment of all non-ignored review products, using suggestions and a user-selected fallback for otherwise unresolved rows.
- Process force and undo operations in background batches of 100, with progress, audit records, stale-job protection and preserved existing manual decisions.
- Keep explicit force assignments during later classification and synchronization; restore previous categories through undo while retaining later edits.
- Restrict the workflow to administrators and allowed companies, and prevent overlapping classification/taxonomy operations.
- Maintain both Arabic catalogs and install the controls through a targeted module upgrade.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/product_classification.py`
- `models/classification_force.py`
- `security/ir.model.access.csv`
- `security/classification_rules.xml`
- `data/classification_queue.xml`
- `views/product_classification_views.xml`
- `views/classification_force_views.xml`
- `static/src/js/product_classification.js`
- `static/src/xml/product_classification.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `docs/classification.md`
- `changelog.d/2026-10-01-product-classification.md`
- `changelog.d/2026-10-04-force-categorization.md`

Validation:

- Existing suite: 78 tests passed, zero failures/errors (`/tmp/ab-force-regression.log`).
- Temporary browser check: suggestion table, fallback dialog and selected-apply action passed (`/tmp/ab-force-ui-test.log`). The probe addon is outside the production package.
- Transactional checks passed for selected/all application, overrides, fallback, undo, protected decisions, later edits, non-superuser administration, public access, bounded batches, stale jobs and idempotence (`/tmp/ab-force-checks.log`).
- Both PO files passed format checks; live Arabic field, dialog and filter translations and job registration were verified.
- Live run 2 retained 11,584 review products with force state idle and zero force changes. A read-only 100-row sample had 69 suggestions and 31 requiring fallback/override.
