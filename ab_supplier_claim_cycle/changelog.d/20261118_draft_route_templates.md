# Draft route templates and translated names

- Added 12 draft workflows and 84 sequential stages for Medicine/Cosmetics,
  tax/non-tax routing, bank transfers and northern/southern cheque delivery.
- English workflow/stage names use standard Odoo Arabic record translations in
  both `ar.po` and `ar_001.po`.
- Approvers and editable fields are intentionally unassigned. Administrators must
  configure approvers before publication; drafts never match submitted claims.
- XML records use `noupdate="1"` to preserve administrator configuration and
  publication states across module upgrades. Existing workflows are unchanged.
- Advance Payments, Cash, Check and Transfer, and Other purchases are excluded.
- Local isolated validation: 29 selected tests passed, including five new
  template tests. No live database upgrade or remote deployment was performed.
