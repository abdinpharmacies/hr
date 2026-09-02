# AB Odoo Sync Global Upload Test Guide

This guide validates the branch-to-reporting upload flow provided by the three
AB Odoo Sync modules. The reporting database receives loose mirror data tagged
with the branch `db_serial`.

## Scope

- Branch chooses which models to upload from `Branch Upload Sources`.
- The reporting server accepts every uploaded payload into `Received Uploads`.
- Report apply profiles decide whether each source model is raw-only, ignored,
  applied into a same-name passive mirror, or applied into a real business model.
- If a same-name passive report model exists and no profile exists yet, the
  report server can create a `mirror_sync` profile and same-name field mappings
  automatically.
- For `business_model` profiles, the report server creates or updates the real target record
  using the same primary key as the source record ID.
- Unknown or unmapped source models remain raw and do not fail the upload.

## Prerequisites

1. Install `ab_odoo_sync_upload` on the branch database.
2. Install `ab_odoo_sync_mapping` on the reporting database.
3. Configure branch connection parameters:
   - `ab_odoo_sync.report_url`
   - `ab_odoo_sync.report_database`
   - `ab_odoo_sync.api_key`
4. Set a positive `db_serial` in the Odoo config file for each branch.
5. On the reporting server, create an active `Registered Branch` with the same
   `db_serial`.

## Test 1: Same-Name Passive Model Auto-Creates A Profile

1. On BRANCH, open `Odoo Sync > Branch Upload Sources`.
2. Click `Load Installed Models`.
3. Activate a source model that exists on the branch, for example `ab_sales_header`.
4. Create or update one record in that source model.
5. Send the outbox row from `Odoo Sync > Upload Outbox`, or wait for the upload cron.
6. On the reporting server, open `Odoo Sync > Apply Profiles` and `Odoo Sync > Received Uploads`.

Expected result:

- An active apply profile exists for the source model.
- `Source Model` and `Target Model` are the same technical model name.
- `Apply Mode` is `Mirror Sync Model`.
- Matching safe stored fields are loaded as enabled mappings.
- The upload is `Pending`, `Queued`, or `Applied` depending on queue timing.
- No new target name with a `__sync` suffix is generated.

## Test 2: Missing Report Model Is Accepted As Pending Mapping

1. On BRANCH, activate a source model that is not installed as a passive model
   on the reporting server.
2. Create or update one record in that source model.
3. Send the outbox row from `Odoo Sync > Upload Outbox`, or wait for the upload cron.
4. On the reporting server, open `Odoo Sync > Received Uploads`.

Expected result:

- The row exists on the reporting server.
- `Status` is `Pending Mapping` when no active apply profile exists.
- The full JSON payload is visible.
- `Target Model` is the source model name.
- The error message explains that the report model is missing or is not a valid
  passive sync model.
- The upload endpoint response does not fail because the target model is not configured yet.

## Test 3: Raw-Only Profile Keeps Payload Without Applying

1. On the report server, open `Odoo Sync > Apply Profiles`.
2. Create a profile:
   - `Source Model`: the uploaded model name.
   - `Apply Mode`: `Raw Only`.
   - `Auto Apply`: disabled or enabled.
3. Run `Queue Pending Uploads` from the profile.

Expected result:

- Matching upload records move to `Raw Only` after the queued feeder runs.
- No target business record or mirror record is created.
- The original payload remains available in `Received Uploads`.

## Test 4: Business Model Upload Forces Report Primary Key

Use a model whose IDs are globally assigned upstream, such as `ab_product`,
`ab_customer`, or `ab_store`.

1. On BRANCH, configure `ab_product` as a `Branch Upload Source`.
2. On the report server, create an apply profile:
   - `Source Model`: `ab_product`
   - `Apply Mode`: `Business Model`
   - `Target Model`: `ab_product`
   - `Allow Placeholder Creation`: enabled
   - `Auto Apply`: enabled or disabled
3. Add field mappings for safe reporting fields, for example:
   - `name -> name`, `Direct Value`
   - `code -> code`, `Direct Value`
   - `barcode -> barcode`, `Direct Value`
   - `active -> active`, `Direct Value`
4. On BRANCH, create or update `ab_product` with a known ID, for example `10025`.
5. Send the branch upload.
6. On the report server, apply the upload if auto-apply is disabled.

Expected result:

- The report server has `ab_product` with `id = 10025`.
- `Odoo Sync > Sync Identities` has a resolved identity row:
  - `DB Serial`: branch serial
  - `Source Model`: `ab_product`
  - `Source Record ID`: `10025`
  - `Target Model`: `ab_product`
  - `Target Record ID`: `10025`
  - `State`: `Resolved`

## Test 5: Relation Arrives Before Product Payload

This validates out-of-order reporting uploads.

1. Ensure the report server does not currently have `ab_product(id=10026)`.
2. Configure a transaction/reporting source model on BRANCH, for example a sales
   line model with a `product_id` Many2one.
3. On the report server, configure the sales line apply profile with:
   - `Apply Mode`: `Mirror Sync Model` for a same-name passive target, or
     `Business Model` for a report-owned model.
   - `product_id` mapping type: `Sync Many2one by Source ID`.
   - `Required`: enabled if the line must not apply without a product identity.
4. On BRANCH, create a sales line referencing `ab_product(id=10026)`.
5. Send and apply the sales line upload before sending the product upload.

Expected result:

- The report server creates a placeholder `ab_product` with `id = 10026`.
- The sales line target links to `product_id = 10026`.
- `Sync Identities` shows `ab_product / 10026` as `Placeholder`.

## Test 6: Later Product Payload Patches The Placeholder

Continue from Test 4.

1. On BRANCH, send the real `ab_product(id=10026)` payload.
2. On the report server, apply the product upload.

Expected result:

- The report server updates the existing `ab_product(id=10026)`.
- No duplicate product is created.
- The identity row changes from `Placeholder` to `Resolved`.
- Sales/reporting rows that already referenced `product_id = 10026` keep the same link.

## Test 7: Ignore Profile Accepts But Skips

1. On the report server, create or change an apply profile:
   - `Apply Mode`: `Ignore`
2. Upload a branch record for that source model.

Expected result:

- The report server accepts the upload.
- Upload record status becomes `Not Sync`.
- No target record is created or updated.

## Validation Queries

Run from Odoo shell on the report server when needed:

```python
env["ab_odoo_sync_upload_record"].search([
    ("model_name", "=", "ab_product"),
    ("rec_id", "=", 10026),
]).mapped(lambda r: (r.status, r.target_model_name, r.apply_profile_id.name))
```

```python
env["ab_odoo_sync_identity"].search([
    ("source_model_name", "=", "ab_product"),
    ("source_rec_id", "=", 10026),
]).mapped(lambda r: (r.db_serial, r.target_model_name, r.target_res_id, r.state))
```

```python
env["ab_product"].browse(10026).exists()
```

## Safety Notes

- Do not use this business-model mode for models whose IDs can differ between
  branches.
- Do not map inventory quantity fields such as `qty_available`,
  `virtual_available`, `free_qty`, `incoming_qty`, or `outgoing_qty`.
- Product, customer, store, and pricing fields should be mapped with a strict
  whitelist for reporting requirements.
- Unknown models should stay `Pending Mapping` or `Raw Only` until the report server has an
  explicit profile.
- Report-owned reference/master models from `sync-rules.md`, such as products,
  customers, stores, HR employees, and sales channels, should use
  `business_model` apply profiles and should not be auto-mirrored.
