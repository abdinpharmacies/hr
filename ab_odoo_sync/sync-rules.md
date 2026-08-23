## Rule number 1
These models must never be cloned into `__sync` mirror tables.
They are MAIN-owned reference/master models and should be referenced from
transaction/reporting mirrors. If a referenced record is not in MAIN yet, the
sync apply flow should force/reserve the same ID as a placeholder, then the
later MAIN/master-data update should fill the remaining fields.

- ab_product
- ab_product_card
- ab_product_uom
- ab_product_uom_category
- ab_uom
- ab_uom_type
- ab_product_company
- ab_product_origin
- ab_product_group
- ab_usage_causes
- ab_usage_manner
- ab_scientific_group
- ab_product_barcode
- ab_doctor
- ab_customer
- ab_store
- ab_supplier
- ab_contract
- ab_costcenter
- ab_hr_employee

Example of force ID mechanism:

A branch uploads a sale operation with a product that MAIN does not have yet.
The sync apply flow should force/reserve the same product ID as a placeholder.
The branch should send and map only the product ID in the JSON payload, not the
full product data. Later, after MAIN updates the product list, it should fill
the remaining fields of the reserved product record.

## Rule number 2

This rule applies only to mirrored models that depend on `res.users`.

When a source model has a stored `Many2one` field to `res.users`, the
corresponding `__sync` mirror model must not point to `res.users` directly. It
must define that relation as a `Many2one` to `ab_users`.

The branch payload for that user relation must carry the source user ID only.
Do not serialize or map user names, logins, emails, groups, passwords, partner
fields, or any other `res.users` data into the transaction/reporting JSON
payload.

MAIN apply must resolve that ID through the Rule 1 force-ID pattern:

- if `ab_users(id=<source_user_id>)` exists, link to it;
- if it does not exist, force/reserve the same ID in `ab_users` as a placeholder;
- later MAIN/master-data user synchronization fills the remaining `ab_users`
  fields.

Example:

A branch uploads `ab_sales_pos_settings` with `user_id = 17`. The mirror model
must define `user_id = fields.Many2one("ab_users", ...)`, and the upload/mapping
must resolve only ID `17` into `ab_users`. It must not create or mirror a
`res.users` row and must not send full user data in the JSON payload.
