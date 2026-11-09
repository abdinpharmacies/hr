# Dual-channel preparation

Previous module commit: `18a34b6a239cce80e75a1837a61743eaf981cdd2`
Author: Alhassan Hossny
Date: 2026-11-09T10:41:10+02:00
Original subject: ab_crm_messaging/docs: record location, attachment and edit updates

Changes included in implementation commit `5d7325a2`:

- Protect historical provenance and preserve provider chronology.
- Permit disabled accounts to reference inactive scoped service identities; active accounts still require active service users.

Verification: see `docs/omnichannel-callcenter-validation.md` in the checkout. Live deployment is gated separately.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/messaging.py`
- `changelog.d/2026-11-09-dual-channel-preparation.md`
