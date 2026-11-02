Current changes before commit:

- Remove the Kind, Upload / Change Reason, File Name and Revision columns from
  the supplier claim document table. Keep the filename hidden for downloads.
- Center document column labels and contents and add cell padding on both sides, supporting
  English and Arabic layouts without changing other tables.
- Preserve document records, classification, downloads and permissions.

Files changed:
- views/parallel_workflow.xml
- static/src/scss/claim_design.scss
- changelog.d/20261102_document_columns.md
