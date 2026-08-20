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



example of force id mechanism
branch upload a sale opt, there's a product that MAIN doesn't have yet, it
should force ID and reserve the place. Then after MAIN updates product list, it
should fill the rest of the fields of the reserved record which we forced ID
into.
