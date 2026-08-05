
Full Implementation Plan

  1. Locate the transfer line model:
      - Model: ab_transfer_smart_line
      - This is where duplicate validation should live.

  2. Add/use duplicate-checking fields:
      - from_store_id
      - to_store_id
      - product_id
      - source_type
      - create_day
      - exclusion_reason

  3. Define source_type:
      - wizard: any explicit product in smart_product_line_ids, whether pasted, uploaded, or manually entered.
      - domain: products selected only through the domain/automatic path.
      - source_type must be assigned to the generated smart line before splitting and preserved when its header_id changes.
      - Use a stored controlled Selection field:
          - wizard
          - domain


  4. Define create_day:
      - Date only, not datetime.
      - Derived from create_date.
      - Example:
          - 03/08/2026
          - not 03/08/2026 14:31:22

      - Make it stored so duplicate checks are fast and stable.
      - Calculate it using the correct egypt timezone, not blindly UTC, because Odoo stores create_date in UTC.

  5. Exclude purchase_preparation:
      - If the related header is in purchase_preparation, no duplicate validation runs.
      - Duplicates may exist freely while the header is in purchase_preparation.

  6. Exclude lines with exclusion reason:
      - If the current line has exclusion_reason, do not check duplication for it.
      - Also ignore existing matching lines that have exclusion_reason.
      - This means excluded lines neither fail validation nor block other lines.

  7. Duplicate key:

  from_store + to_store + product + source_type + create_day

  8. Run duplicate validation when:
      - Creating an ab_transfer_smart_line outside purchase_preparation.
      - Writing/changing:
          - product_id
          - from_store_id
          - to_store_id
          - source_type
          - header_id
          - exclusion_reason

      - Moving an ab_transfer_header from purchase_preparation into:
          - store_preparation
          - store_revision
          - pre_submit
          - submit

  9. Centralize duplicate logic:
      - Add one helper method on ab_transfer_smart_line, for example:
          - _check_duplicate_transfer_lines()

      - Use this same helper from:
          - @api.constrains
          - create
          - write
          - header source_type transition logic

      - This keeps behavior consistent.

  10. Duplicate detection domain should effectively be:

  same from_store_id
  same to_store_id
  same product_id
  same source_type
  same create_day
  header_id.smart_stage != purchase_preparation
  current line has no exclusion_reason
  matched line has no exclusion_reason
  different line id

  11. Error message should be actionable:

  - Show duplicated product code.
  - Show product full name.
  - Show quantity.
  - Show source_type.
  - Show create day.
  - Ideally show the related transfer/header reference too.
  - If multiple duplicates exist, show them together in one validation error.

  Example message shape:

  Duplicated transfer products found:

  Code: A001
  Product: Product A
  Qty: 10
  Source: domain
  Create Day: 03/08/2026
  Existing Transfer: TR/00015

  12. Sample data behavior:


   from store    to store    product    source_type       create_day    result                                                                               
  ━━━━━━━━━━━━  ━━━━━━━━━━  ━━━━━━━━━  ━━━━━━━━  ━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━
   63            gom         a          wizard    03/08/2026    allowed
  ────────────  ──────────  ─────────  ────────  ────────────  ───────────────────
   63            gom         a          domain    03/08/2026    allowed
  ────────────  ──────────  ─────────  ────────  ────────────  ───────────────────
   63            gom         a          domain    03/08/2026    blocked duplicate
  ────────────  ──────────  ─────────  ────────  ────────────  ───────────────────
   63            gom         a          wizard    04/08/2026    allowed
  ────────────  ──────────  ─────────  ────────  ────────────  ───────────────────
   63            gom         a          domain    04/08/2026    allowed
  ────────────  ──────────  ─────────  ────────  ────────────  ───────────────────
   63            gom         a          domain    04/08/2026    blocked duplicate

  13. Important behavior:

  Not duplicates because source_type differs:

  63, gom, a, wizard, 03/08/2026
  63, gom, a, domain, 03/08/2026

  Not duplicates because create day differs:

  63, gom, a, domain, 03/08/2026
  63, gom, a, domain, 04/08/2026

  Duplicates:

  63, gom, a, domain, 03/08/2026
  63, gom, a, domain, 03/08/2026

  14. Constraint type:

  - Use Python validation, not SQL constraint.
  - Reason: the rule depends on related header source_type and exclusion reason.
  - Use @api.constrains plus explicit validation during header source_type transition.


