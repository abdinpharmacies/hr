# Two-server QA follow-up

## b0095b6521105f026f3de12e4283d402255f28c3

Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints

- Allow website selection on new integration endpoints.

Files changed:
- README.md
- __manifest__.py
- changelog.d/2026-11-17-endpoint-website-selector.md
- tests/test_adapter.py
- views/views.xml

## Current changes before commit:

This entry describes the QA follow-up; earlier uncommitted integration implementation remains recorded in the preceding changelog entries.

- Exercise the inherited portal controller body without requiring generated HTTP routing metadata in an ORM test.
- Set an explicit English context for the test that asserts the English queued acknowledgement.
- Preserve a customer's Send click during an active history poll, keep its UUID stable, and retain a newer draft after acknowledgement.
- Add a browser regression for the overlapping history poll and submission; bump the adapter to `19.0.1.5.1`.
- Validate the existing integration with fresh synthetic databases, strict HTTPS, browser/identity/media/race checks and the reusable runner under `qa/two_server`.
- Add no runtime source strings or translation changes in this follow-up.

Files changed:
- __manifest__.py
- static/src/chat.js
- tests/test_adapter.py
- changelog.d/2026-11-23-two-server-qa.md
