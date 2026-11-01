Supplier claim form and Chatter — 19.0.5.1.0

- Move document revisions into one Documents tab, including file downloads,
  revision, upload/change reason, author, and timestamp.
- Remove the standalone document metadata, Notes display, and Workflow History
  tab. Keep the company field visible once and retain all underlying fields.
- Restore native Chatter and activities. Mirror immutable workflow history into
  internal Chatter messages while preserving its original author and timestamp.
- Backfill existing history in batches during the targeted module upgrade.
  Repeating the backfill does not duplicate messages or change audit records.
  Audit mirroring does not notify followers or send emails.
  Older secretarial notes without an audit entry are retained and copied once
  into a clearly labeled legacy note, without inventing an original author/date.
- Remove unauthorized department review groups from the server-generated form.
  Existing server-computed stage permissions control which remaining reviews
  apply to each claim. Workflow actions and record rules are unchanged.
- Keep mirrored audit entries immutable; ordinary Chatter communication retains
  standard Odoo permissions.

Apply with a targeted upgrade of `ab_supplier_claim_cycle` and restart Odoo to
load the Python changes. No production upgrade is performed by these changes.
