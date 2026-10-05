# Classification queue activation

## Recent relevant commit

Commit: `083e324f3b56f0cf60f0064b3645d25e3743b3f0`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_website_sale_product/docs: record website sync commits`

- Record the module’s existing synchronization history.

Files changed:

- `changelog.d/2026-09-29-website-sync-local-commits.md`

## Current changes before commit:

- Document the local queue runner startup configuration required to execute classification jobs.
- Activate the local ecom19 queue runner with one worker and HTTP destination 127.0.0.1:4092, retaining its existing startup modules. The secret-bearing local config is intentionally ignored by Git.
- Save the prior local config and current product category assignments before activation, then gracefully restart Odoo.
- Verify that the existing user-started run is picked up without creating a duplicate run.

Files changed:

- `docs/classification.md`
- `changelog.d/2026-10-01-product-classification.md`
- `changelog.d/2026-10-04-classification-runner.md`

Validation:

- Odoo login remains available with HTTP 200 after the graceful restart.
- The runner reports ready for ecom19 and executes the previously pending job with HTTP 200.
- Snapshot completed for 31,255 products. At 2026-10-04 12:26:18 UTC, 4,250 were processed: 3,494 classified, 756 needing review, zero failures; the run remained active.
