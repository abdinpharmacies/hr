Current changes before commit:

- Enable multiple selection in the existing stage-specific Upload/Edit controls;
  do not add a separate upload button to Documents.
- Preserve each selected file in immutable document history with the existing
  document kind, uploader, timestamp and Chatter download link.
- Update the existing stage binary/filename through normal write permissions so
  required-document checks and revision rules remain effective. A supplier batch
  changes the revision once, with all selected files assigned that revision.
- Validate the entire batch before mutation and reject invalidated payment files
  even when they are not the last selected file.
- Keep existing readonly/visibility rules and English/Arabic native upload labels.
- Keep a hidden Reason anchor in the parent view until the child removes it,
  allowing existing installations to upgrade after the document-column removal.

Files changed:
- __manifest__.py
- models/ab_supplier_claim_cycle.py
- models/payment_preparation.py
- views/parallel_workflow.xml
- static/src/js/document_upload.js
- static/src/xml/document_upload.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_claim_cycle.py
- tests/test_claim_http.py
- changelog.d/20261102_multiple_attachments.md

Validation:
- Fresh installation and targeted upgrade on supplier_claim_stage_upload_20261102.
- All 47 ORM cases passed in /tmp/claim_stage_multi_final.log; that combined run's
  two browser failures were corrected and superseded by the final browser run.
- English/Arabic native-control uploads: 2 tests, zero failures/errors in
  /tmp/claim_stage_multi_browser_verified.log, using HTTP port 5369.
- Final stage-widget and role-view checks: 2 tests, zero failures/errors in
  /tmp/claim_stage_multi_views.log.
- Both gettext format checks, JavaScript syntax and git diff checks passed.
- The earlier test database retains the discarded experimental button view;
  no compatibility code or migration was added for that disposable state.
- No production database upgrade or service restart was performed.
