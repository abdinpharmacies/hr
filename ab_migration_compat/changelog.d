No previous commits: new addon (git log and git diff inspected; files are untracked).

Current changes before commit:
Author: emadco88
Date: 2026-11-10
- Preserve private contacts, confidentiality rules, and historical Contract Deduction classification.
- Preserve metadata for unavailable attachments; downloads explain the missing original file.
- Flag unresolved inventory and audit references, preserve original IDs and prevent normal edits.
- Restore the legacy HR history role with its original three read-only ACLs and no implied privileges.
- Provide English source strings and Arabic translations for both language codes.

Files changed:
- __init__.py
- __manifest__.py
- i18n/ar.po
- i18n/ar_001.po
- models/__init__.py
- models/account_guide.py
- models/res_partner.py
- models/ir_attachment.py
- models/legacy_references.py
- security/private_contacts.xml
- security/legacy_hr.xml
- views/ir_attachment.xml
- views/legacy_references.xml
