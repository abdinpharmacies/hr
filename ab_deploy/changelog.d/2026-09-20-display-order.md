# Match deployment lists to report order

Recent relevant commit: c0039f977ed4a44a465577b36fcd0567ce984b13
Author: emadco88
Date: 2026-09-17
Original commit subject: ab_deploy/ Stable
- Established Target Servers and Execution Jobs views.

## Current changes before commit:

Author: emadco88
Date: 2026-09-20 (UTC)
Commit: uncommitted

- Add stored computed display keys for status, numeric/text Serial, and case-folded server name, with record ID as the final tie-breaker.
- Default both Target Servers form lists, the request Execution Jobs tab and standalone Execution Jobs list to Failed, Unfinished, Cancelled, Delayed, Succeeded ordering.
- Keep existing model/execution order, statuses, selection logic and 80-row target pages unchanged; users can override list sorting.
- Refresh keys when execution/request status or server Serial/name changes, including pre-existing records through normal module upgrade.
- Add Arabic labels for hidden sorting fields and version 19.0.4.1.2. Earlier uncommitted selected-SSH-retry changes are documented separately in 2026-09-20-selected-ssh-retries.md.

Validation: targeted upgrade passed without ERROR/CRITICAL/traceback. Compared paginated SQL ordering for 176 targets and 60 jobs with the Markdown-style Python order, checked numeric/text/blank/Unicode-digit Serial cases, verified all four list architectures and Arabic view translations. No deployments or messages were sent. msgfmt is unavailable on this host.

Files changed for display ordering:

- `ab_deploy/models/display_order.py`
- `ab_deploy/models/__init__.py`
- `ab_deploy/views/display_order_views.xml`
- `ab_deploy/__manifest__.py`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-20-display-order.md`
