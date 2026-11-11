# Module update commit record

- Commit: `17051b0c69180a578b64ff012b5d5243469f54d8`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:48:51+02:00`
- Original subject: `ab_crm_messaging/feat: extend inbound evidence and receipt previews`

## Changes

- Extend validated inbound evidence, identity handling and read-only receipt previews for the channel companions.
- Detailed feature entries in this directory describe the constituent updates.

## Validation

Implementation and runtime evidence is recorded in [the retirement report](../../docs/messaging-legacy-retirement.md) and the feature-specific rollout reports in `docs/`. Commit preparation checked changed Python syntax, XML parsing, JavaScript syntax, Arabic catalog formats and whitespace. No additional runtime or database changes were made while preparing commits.

Files changed:

- `__manifest__.py`
- `controllers/gateway.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/media.py`
- `models/messaging.py`
