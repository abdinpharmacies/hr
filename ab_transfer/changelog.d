Current changes before commit:

- Serialize each transfer submission and reject concurrent requests before any B-Connect write.
- Add a stable branch-scoped idempotency marker and recover one matching committed E-Plus transfer without repeating stock, replication, or accounting writes.
- Reject ambiguous, mismatched, or invalid-status E-Plus matches for manual inventory reconciliation.
- Store the exact E-Plus transfer serial on the base transfer model and preserve both supported Arabic translations.

Files changed:

- ab_transfer/changelog.d
- ab_transfer/i18n/ar.po
- ab_transfer/i18n/ar_001.po
- ab_transfer/models/ab_transfer_header.py
- ab_transfer/tests/test_transfer_type_notes.py


commit c8ffc50f468b3ed244d14e81e2e39fa9397e10e9
Author: Mohamed Fawzy <mohamed.fawzy.dev87@gmail.com>
Date:   Sun Aug 9 15:36:03 2026 +0300

    ab_transfer/fix:   Store_Trans_h.stnh_notes = 4
      Odoo Transfer: Transfer 123
    to be in same line

- Keep numeric transfer-type notes and the Odoo transfer reference on the same E-Plus notes line.

Files changed:

- ab_transfer/models/ab_transfer_header.py
- ab_transfer/tests/test_transfer_type_notes.py


commit b20559328d2bc928b9e02f765f51dd7f0b58140c
Author: hager yasser <hageryasser2002@gmail.com>
Date:   Sun Aug 9 12:45:56 2026 +0300

    ab_transfer/feat: append Odoo reference to Store_Trans_h notes

- Add the Odoo transfer reference to E-Plus transfer-header notes for traceability.

Files changed:

- ab_transfer/models/ab_transfer_header.py
