# Accounting (Odoo 19)

Functional baseline: `389c000`, the first committed module copy. Original account
hierarchy, journal fields, authorization groups, allowed-field permissions,
confirmation, reversal, salary deduction controls and statement reports are retained.
No accounting schema fields have been added.

The module depends only on base/mail, stores, cost centers, extra tools and XLSX
reports. Purchase, inventory and tax integrations remain in external adapters.
Legacy views and ORM APIs are adapted to Odoo 19. The tab-separated Excel workflow
uses the original line fields without requiring the unavailable legacy import addon.

Post with `btn_post_je()`. Freeze/unfreeze and line confirmation require the
responsible reviewer. Posted edits use the original allowed-field authorization
records and must leave the journal valid and balanced. Posted entries cannot be
deleted; the original line reversal workflow remains available.

Document types in the first copy have no `active` field. This refactor does not add
one. Inactive document types are rejected when an installed extension supplies it;
otherwise document-type access is controlled by the original authorization group.
Accounts and document types also have no company field in this baseline. Adapter
configuration retains its company scope without inventing account-level schema.

See `POSTING_CONTRACT.md` for the automated interface and `VALIDATION.md` for checks.
