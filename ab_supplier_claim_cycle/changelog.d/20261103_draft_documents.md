Current changes before commit:

- Remove Company from the supplier claim form while retaining the model field and company isolation.
- Show Review Details during Draft and returned-for-correction for authorized secretarial users, with editable notes and initial attachments.
- Keep Documents limited to immutable file history, without the duplicate latest-attachment field.
- Show payment preparation fields only when payment preparation is permitted.
- Preserve existing upload permissions and later-stage upload controls.
- Extend form, upload persistence, and English/Arabic browser coverage for draft notes and attachments in Review Details.
- Add a new-record Form regression test covering secretary/admin entry fields and notes through saving a draft.

Files changed:
- views/parallel_workflow.xml
- tests/test_claim_cycle.py
- tests/test_claim_http.py
- changelog.d/20261103_draft_documents.md

Validation:
- Targeted upgrade on idle isolated database supplier_claim_stage_upload_20261102 with this checkout's addons path; 47 ORM tests passed with zero failures/errors in /tmp/claim_draft_reviews_verified.log.
- Validation used no HTTP, workers=0, cron=0, and alternate ports 5069/5072; the user's running server was not restarted or upgraded.
- English/Arabic draft browser tests were skipped because websocket-client is missing from the configured interpreter; interactive uploads remain unverified.
- Python/XML syntax, git diff whitespace checks, and both Arabic gettext format checks passed. ar_001.po retains its existing missing Language header warning.
- Existing test-database filestore entries produced missing-file diagnostics; they did not fail the ORM suite.
- New-record Form regression passed separately (1 test, zero failures/errors) in /tmp/claim_new_form_reproduce.log. A rollback-only check under the affected user's permissions also returned active=True, state=draft, and editable entry/correction fields; the reported browser lock is not yet reproduced.
