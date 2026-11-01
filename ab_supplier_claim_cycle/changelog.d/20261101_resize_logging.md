Supplier claim table containment and logging — 19.0.5.2.0

- Keep claim list renderers and embedded tables within their containers while
  allowing horizontal scrolling after native Odoo column resizing.
- Record document revisions in Chatter with the original uploader, timestamp,
  document type, revision, and a download link. File contents are not copied.
- Backfill existing document records once during the targeted upgrade. Preserve
  every document record and its content, author, timestamp, and revision.
- Preserve native Odoo field tracking. Add audit entries for previously untracked
  claim inputs, department notes, follow-up dates, and general attachments.
- Retain explicit field-change logs when mail tracking is disabled by context.
  Keep actor attribution and existing record permissions for all claim roles.
- Keep document audit messages immutable, matching document-history protection.

The prior gap was in event creation: uploads produced document-history records
without Chatter messages, and some fields had no tracking. Existing workflow
decisions already generated audit messages independently of the user's role.
No workflow sequence, approval condition, or security rule is changed.
