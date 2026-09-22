# Report status order and Arabic labels

Recent relevant commit: 309fa2627c83e2ecfc1e5dd57520add83e0387c5
Author: emadco88
Date: 2026-09-17
Original commit subject: ab_deploy_telegram/ NEW for linking ab_deploy with ab_telegram_bot
- Introduced deployment notifications and shared manual/automatic reports.

## Current changes before commit:

Author: emadco88
Date: 2026-09-20 (UTC)
Commit: uncommitted

- Order summary counts and table rows by Failed, Unfinished, Cancelled, Delayed, Succeeded.
- Display queued/running/unknown as Unfinished in reports without changing deployment states.
- Use exact Arabic labels: فشل، غير مكتمل، ملغي، مؤجل، تم.
- Preserve Serial/name sorting within each status group; update documentation and version 19.0.1.1.1.
- Targeted deploy19 module upgrade passed without errors. In-memory mixed-status validation confirmed row order, labels and totals; Arabic view validation passed in a rolled-back transaction. No notifications sent. Restarted idle queue runner; both services active. msgfmt is not installed.

Files changed:

- `ab_deploy_telegram/models/deployment.py`
- `ab_deploy_telegram/i18n/ar.po`
- `ab_deploy_telegram/i18n/ar_001.po`
- `ab_deploy_telegram/__manifest__.py`
- `ab_deploy_telegram/README.md`
- `ab_deploy_telegram/changelog.d/2026-09-20-report-statuses.md`
