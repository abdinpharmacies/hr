# Backup Policy

These are project production recommendations, not a command to change retention automatically. Before an authorized mass operation, create and verify a dedicated backup using the actual database/user/destination; do not assume the example database is the target. Keep credentials out of commands/logs.

### PostgreSQL Backup Rules

Recommended pharmacy production backup retention:

- Hourly: 72 backups
- Daily: 60 backups
- Weekly: 24 backups
- Monthly: 24 backups

Inventory and pricing mistakes may only be discovered several weeks later.

Create a dedicated PostgreSQL backup before:

- Mass Price Update
- Mass Product Import
- Mass Barcode Update
- Inventory Adjustment Import
- Stock Recycling Batch
- Supplier Synchronization

Example:

```bash
pg_dump \
  -U odoo19 \
  -F c \
  -d abdin_prod \
  -f before_mass_import_$(date +%F_%H-%M).backup
```

