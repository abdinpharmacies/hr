# Independent deployment roles

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-16 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Split deployment access into six independent role selectors on the user form, allowing combinations such as Developer and Executor.
- Reuse the existing privilege for Viewer and add separate privileges for the other roles under Deployment Manager.
- Preserve group XML IDs, user membership assignments and inherited access. Runner remains independently assigned; self-approval rules are unchanged.
- Reuse the existing English role labels and Arabic translations, adding privilege references in both Arabic catalogs without removing existing message IDs.

## Validation

- Static checks passed for XML syntax, definition order, six distinct privileges, unchanged group IDs/names/inheritance, and translation coverage/references.
- Both Arabic catalogs passed `msgfmt --check-format`; `git diff --check` passed.
- A read-only POT export was attempted, but the previous disposable validation database no longer exists. Translation references were checked against the XML definitions instead.
- No services restarted or databases upgraded. User-form persistence and runtime Arabic verification remain for the user's manual upgrade.

Files changed:

- `ab_deploy/security/security_groups.xml`
- `ab_deploy/i18n/ar.po`
- `ab_deploy/i18n/ar_001.po`
- `ab_deploy/changelog.d/2026-09-16-independent-roles.md`
