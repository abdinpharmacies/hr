Current changes before commit:

- Publish fractional reference-unit stock snapshots and source prices through canonical product UoM factors.
- Document the inventory flow after retiring the legacy unit models.

Files changed:

- ab_central_sync/changelog.d/2026-11-05-canonical-product-uom.md
- ab_central_sync/models/inventory_units.py
- ab_central_sync/workflow.md

commit 71560c29ec2c91725e0f363d923c461743adaffd
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date:   2026-11-05T16:32:04+02:00

    feat(ab_central_sync): authenticate inventory sync with user API keys and post product-UoM stock

- Authenticate inventory synchronization with inventory-writer API keys and post product-unit stock on central.

Files changed:

- ab_central_sync/models/inventory_units.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/product.py
- ab_central_sync/workflow.md
