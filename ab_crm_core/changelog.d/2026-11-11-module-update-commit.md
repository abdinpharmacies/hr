# Module update commit record

- Commit: `dcb9c51e5ef119af0fa1dc1446de67ae775c3ce6`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:48:41+02:00`
- Original subject: `ab_crm_core/feat: rename conversation navigation to inbox`

## Changes

- Rename conversation navigation to Inbox while preserving existing action identifiers and Arabic labels.
- Detailed feature entries in this directory describe the constituent updates.

## Validation

Implementation and runtime evidence is recorded in [the retirement report](../../docs/messaging-legacy-retirement.md) and the feature-specific rollout reports in `docs/`. Commit preparation checked changed Python syntax, XML parsing, JavaScript syntax, Arabic catalog formats and whitespace. No additional runtime or database changes were made while preparing commits.

Files changed:

- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `views/menus.xml`
- `views/views.xml`
