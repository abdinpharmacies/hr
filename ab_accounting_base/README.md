# Odoo 15 accounting catalog split

`ab_accounting_base` owns the account guide, document types, and the three
account-level models. It keeps their existing model and table names. The
customer collections module depends on this catalog; journal entries,
account authorization, and accounting reports remain in `ab_accounting`.

On an existing Odoo 15 database, install the base module and upgrade both
existing modules in **one** stopped-service upgrade, after confirming a
restorable backup:

Do not restart the application against the old database state before this
upgrade; the module code now expects `ab_accounting_base` to be installed.

```bash
/opt/odoo15/venv15/bin/python3 /opt/odoo15/server/odoo-bin \
  -c /opt/odoo15/config/abdin15.conf -d DATABASE_NAME \
  -i ab_accounting_base -u ab_accounting,abdin_cust \
  --stop-after-init --no-http
```

The base pre-install hook transfers the catalog XML IDs from `ab_accounting`
to `ab_accounting_base` and retains legacy aliases for other modules. It does
not copy or delete catalog records. `ab_accounting` must be upgraded in the
same run so its old data file and model definitions are retired safely.

For a new database, installing `abdin_cust` installs `ab_accounting_base`
without installing `ab_accounting`. Full accounting can be installed later.
