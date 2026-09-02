## Rule number 1
These models must never be cloned into passive mirror tables.
They are report-owned reference/master models and should be referenced from
transaction/reporting mirrors. Configure uploads for these models with
`business_model` apply profiles, not `mirror_sync`. If a referenced record is
not in the report server yet, the sync apply flow should force/reserve the same
ID as a placeholder, then the later report/master-data update should fill the
remaining fields.

- ab_costcenter
- ab_store
- ab_replica_db
- ab_hr_region
- ab_hr_job
- ab_hr_department
- ab_hr_employee
- ab_hr_job_occupied
- ab_customer
- ab_uom_type
- ab_uom
- ab_product_uom_category
- ab_product_uom
- ab_product_card
- ab_product
- ab_product_barcode
- ab_contract
- ab_promo_program
- ab_employee_access_sales_role
- ab_employee_access
- ab_doctor
- ab_product_metadata
- ab_product_company
- ab_product_origin
- ab_product_group
- ab_usage_causes
- ab_usage_manner
- ab_sales_channel

Example of force ID mechanism:

A branch uploads a sale operation with a product that the report server does not have yet.
The sync apply flow should force/reserve the same product ID as a placeholder.
The branch should send and map only the product ID in the JSON payload, not the
full product data. Later, after the report server updates the product list, it should fill
the remaining fields of the reserved product record.

## Rule number 2

This rule applies only to mirrored models that depend on `res.users`.

When a source model has a stored `Many2one` field to `res.users`, the
corresponding passive mirror model must not point to `res.users` directly. It
must define that relation as a `Many2one` to `ab_users`.

The branch payload for that user relation must carry the source user ID only.
Do not serialize or map user names, logins, emails, groups, passwords, partner
fields, or any other `res.users` data into the transaction/reporting JSON
payload.

Report apply must resolve that ID through the Rule 1 force-ID pattern:

- if `ab_users(id=<source_user_id>)` exists, link to it;
- if it does not exist, force/reserve the same ID in `ab_users` as a placeholder;
- later report/master-data user synchronization fills the remaining `ab_users`
  fields.

Example:

A branch uploads `ab_sales_pos_settings` with `user_id = 17`. The mirror model
must define `user_id = fields.Many2one("ab_users", ...)`, and the upload/mapping
must resolve only ID `17` into `ab_users`. It must not create or mirror a
`res.users` row and must not send full user data in the JSON payload.

## Rule number 3

Every passive mirror model must be schema-permissive.

No field on a passive mirror model may be declared with `required=True`, including
technical identity fields such as `db_serial`, `rec_id`, `event_uuid`, and
payload fields. The report server must be able to accept partial branch data,
force-create placeholder rows, and preserve raw payloads without being blocked
by ORM or database required-field validation.

If a field is required for a specific apply flow, enforce that requirement in
the relevant `ab_odoo_sync_apply_profile` field mapping by enabling the mapping
`required` flag. Requiredness belongs to the apply profile, not the mirror table
schema.

This keeps raw/report storage tolerant while still allowing strict validation
for selected fields when the report server later applies or validates the data.
