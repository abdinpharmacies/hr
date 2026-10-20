# Product image synchronization memory usage

## Recent relevant commit

Commit: `acbea2c9eccd4be9263942215a8adeb2952c9a5e`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_website_sale_product/fix: preserve manually edited website images`

- Preserve manually edited website images by comparing the source and applied image checksums.

Files changed:

- `models/product_image_sync.py`
- `models/product_template.py`
- `tests/test_website_category_mapping.py`

## Current changes before commit:

- Calculate existing website image checksums from attachment storage without loading Base64 images into the product record cache.
- Stream filestore images in bounded chunks and release database-backed image data after each checksum.
- Preserve source, resized-image and manual-edit checksum behavior during preview and synchronization.
- Cover the attachment checksum path with a regression test that rejects reads of the Base64 image field.
- Use the current checksum to detect an existing image when deciding whether replacement confirmation is required, removing the remaining full image read in planning.
- Exercise the Preview and Synchronize Images buttons with uncached product images, and verify empty, placeholder and unchanged image classifications without loading product image payloads.

Files changed:

- `models/product_image_sync.py`
- `models/product_template.py`
- `tests/test_website_category_mapping.py`
- `changelog.d/2026-10-20-image-sync-memory.md`

Validation:

- The initial checksum-only fix passed 16 test methods but missed the remaining image-presence read in replacement planning.
- The new button regression reproduced that remaining read at `product_image_sync.py:277` before the follow-up fix.
- After the follow-up fix, the targeted Odoo 19 module upgrade and `TestWebsiteCategoryMapping` suite passed on `ab_classification_test_20260930`: 18 test methods, 0 failures and 0 errors. Validation used `--no-http`, workers/cron disabled, and alternate ports configured as 5069/5072.
- Regression checks now cover both checksum calculation and the wizard's preview/replacement-confirmation path without fetching `product.template.image_1920`. Fixtures are flushed before the request to complete image resizing independently of planning.
- Python compilation, `git diff --check`, and both Arabic catalog format checks passed.
- The isolated test database has pre-existing missing filestore files and view accessibility warnings; they did not fail or affect the image synchronization tests.
- No live storefront restart or live image synchronization was performed; the running Python workers must load the updated code before retrying.
