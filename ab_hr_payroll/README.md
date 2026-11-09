# Odoo 15 HR/payroll split

`ab_hr` now contains core HR records and can be installed without accounting.
`ab_hr_payroll` contains payroll and the HR/accounting integration. Existing
technical model names and PostgreSQL tables remain unchanged.

## Existing databases

Upgrade `ab_hr` and install `ab_hr_payroll` in **the same Odoo run**. For an
installation that also uses `ab_eplus`, update it in that run as well:

```sh
/opt/odoo15/venv15/bin/python3 /opt/odoo15/server/odoo-bin \
  --config=/opt/odoo15/config/abdin15.conf \
  --database=DATABASE_NAME \
  --update=ab_hr,ab_eplus \
  --init=ab_hr_payroll \
  --stop-after-init --no-http
```

Stop application workers and confirm a restorable database backup before a
live update. The `ab_hr` pre-migration script rejects an HR-only upgrade on
an old database with payroll data. The payroll pre-init hook transfers moved
XML IDs to `ab_hr_payroll` and leaves `ab_hr.*` aliases, so existing references
and records keep their IDs.

The migration was tested on small synthetic Odoo 15 databases. It does not
copy or alter `abdinpharmacies` during testing.
