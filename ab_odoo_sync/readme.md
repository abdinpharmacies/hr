# AB Odoo Sync Setup

This module is the shared base for branch-to-report synchronization. The current
flow is:

```text
Branch operational DB
  -> ab_odoo_sync_upload outbox
  -> HTTP POST /ab_odoo_sync/upload
  -> Report DB raw upload records
  -> ab_odoo_sync_mapping apply profiles
  -> passive/report tables
```

The sync process is intentionally selected-model and selected-field based. It
does not try to copy every installed model.

## Required Modules

Branch servers:

- `queue_job`
- `ab_odoo_sync`
- `ab_odoo_sync_upload`
- The operational modules that own the selected source models, for example
  `ab_sales` on a sales branch.

Report server:

- `queue_job`
- `ab_odoo_sync`
- `ab_odoo_sync_mapping`
- Passive/report modules that provide the target tables, for example `ab_sales`.
- Connector profile modules for selected datasets, for example `ab_sales_sync`.

Known `ab_sales_sync` profile models in the current codebase:

- `ab_sales_header`
- `ab_sales_line`
- `ab_sales_return_header`
- `ab_sales_return_line`
- `ab_product_priced`
- `ab_product_metadata`
- `ab_sales_inventory`
- `ab_sales_per_day`
- `ab_sales_per_day_sync_state`
- `ab_product_rank`
- `ab_sales_pos_settings`
- `ab_sales_pos_draft_cache`
- `ab_sales_pos_replication_turn`
- `ab_printer`

## Odoo Config

All servers need queue job loaded server-wide:

```ini
server_wide_modules = base,web,rpc,queue_job
queue_job_channels = root:2
```

Each branch server must have a stable positive database serial in `odoo.conf`:

```ini
db_serial = 101
```

The report server must route sync requests to the report database. For the
current report environment, keep the database selection compatible with
`abdin_report` and verify the health endpoint returns that database.

## Runtime Settings

Branch database parameters:

- `ab_odoo_sync.main_url`: base URL of the report server, for example
  `http://report-server:4090`
- `ab_odoo_sync.main_database`: report database name, for example `abdin_report`
- `ab_odoo_sync.api_key`: shared sync API key
- `ab_odoo_sync.batch_size`: optional, defaults to `1000`, maximum `10000`

Report database parameters:

- `ab_odoo_sync.api_key`: the same shared sync API key used by the branches
- `ab_odoo_sync.batch_size`: optional apply feeder batch size

Current code uses one report-side API key for the upload endpoints. Branch
authorization after that is by registered `db_serial` in
`ab_odoo_sync_branch_registry`.

## Data To Collect

Collect this before enabling sync for a branch:

- Branch database name.
- Branch `db_serial` from `odoo.conf`.
- Branch display name.
- Report server URL reachable from the branch.
- Report database name.
- Shared API key.
- Selected source model list.
- Optional aggregate parent field per source model.
- Target passive/report model for each source model.
- Selected field mappings for each apply profile.
- Mapping type for relation fields: `sync_many2one`, `sync_many2many`,
  `stable_many2one`, `stable_many2many`, `direct`, or `ignore`.
- Which mapped fields are required by apply profile validation.
- Whether branch upload cron and report apply cron should be active.

For relation fields that must preserve branch IDs, use the sync relation mapping
types and keep `allow_placeholder_creation` enabled on the apply profile. The
report server can then force-create placeholder rows with the same source ID and
fill them later when the relevant master data is synced.

## Setup Script

Use `scripts/configure_sync.py` through Odoo shell. The script only creates or
updates sync configuration records and `ir.config_parameter` values. It does not
delete business data and does not run direct SQL.

Dry-run any command by adding:

```bash
SYNC_DRY_RUN=1
```

### Configure A Branch

```bash
SYNC_ROLE=branch \
SYNC_DB_SERIAL=101 \
SYNC_MAIN_URL=http://report-server:4090 \
SYNC_MAIN_DATABASE=abdin_report \
SYNC_API_KEY='replace-with-secret' \
SYNC_SOURCE_MODELS=ab_sales_header,ab_sales_line,ab_sales_return_header,ab_sales_return_line \
SYNC_ACTIVATE_CRONS=1 \
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
  -c /opt/odoo19/odoo19.conf \
  -d branch_db \
  < ab_odoo_sync/scripts/configure_sync.py
```

For aggregate sources, use JSON instead of `SYNC_SOURCE_MODELS`:

```bash
SYNC_SOURCE_SPECS_JSON='[
  {"model_name":"ab_sales_line","active":true,"aggregate_parent_field":"header_id"}
]'
```

The branch cron XML ID is:

```text
ab_odoo_sync_upload.ir_cron_ab_odoo_sync_branch_upload
```

### Configure The Report Server

```bash
SYNC_ROLE=report \
SYNC_API_KEY='replace-with-secret' \
SYNC_BRANCH_NAME='Branch 101' \
SYNC_BRANCH_DB_SERIAL=101 \
SYNC_PROFILE_MODELS=ab_sales_header,ab_sales_line,ab_sales_return_header,ab_sales_return_line \
SYNC_AUTO_APPLY=1 \
SYNC_ACTIVATE_CRONS=1 \
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell \
  -c /opt/odoo19/odoo19.conf \
  -d abdin_report \
  < ab_odoo_sync/scripts/configure_sync.py
```

For multiple branches:

```bash
SYNC_BRANCHES_JSON='[
  {"name":"Branch 101","db_serial":101,"active":true},
  {"name":"Branch 102","db_serial":102,"active":true}
]'
```

For explicit source-to-target profiles:

```bash
SYNC_PROFILE_SPECS_JSON='[
  {
    "name":"Sales Headers",
    "source_model_name":"ab_sales_header",
    "target_model_name":"ab_sales_header",
    "apply_mode":"mirror_sync",
    "auto_apply":true,
    "allow_placeholder_creation":true,
    "active":true
  }
]'
```

For explicit field mappings:

```bash
SYNC_MAPPING_SPECS_JSON='[
  {
    "profile_source_model_name":"ab_sales_header",
    "source_field_name":"store_id",
    "target_field_name":"store_id",
    "mapping_type":"sync_many2one",
    "required":true,
    "sync_enabled":true
  }
]'
```

The report apply cron XML ID is:

```text
ab_odoo_sync_mapping.ir_cron_ab_odoo_sync_queue_upload_apply
```

## Verification

From a branch Odoo shell:

```python
env["ab_odoo_sync_service"].sudo().test_upload_connection()
```

Expected result:

- `status` is `ok`
- `main_database` is `abdin_report`
- `db_serial` matches the branch

From the report server, verify:

- The branch exists and is active in `ab_odoo_sync_branch_registry`.
- `/ab_odoo_sync/health` returns `ok: true` for that `db_serial`.
- New payloads appear in `ab_odoo_sync_upload_record`.
- Apply profiles point to passive/report target models.
- Field mappings are enabled only for selected fields.
- Queue jobs run without stale `integration_queue_job` channels.

## Important Limits

- `db_serial` is read from `odoo.conf` on the branch. The script validates it
  when `SYNC_DB_SERIAL` is provided, but it cannot store it in the database.
- Source models are validated against `sync-rules.md`; protected master models
  should not be mirrored as raw branch upload sources.
- Requiredness belongs in `ab_odoo_sync_field_mapping.required`, not on passive
  sync table fields.
- If the report server needs a different API key per branch, the current module
  needs a small extension because the branch registry does not currently store
  an API key field.
