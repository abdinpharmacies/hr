# Expose receipt preview to the authenticated gateway

## Committed baseline

- Commit: `efee2ce6389ec70c47d67d0d4ef7057c5f3e06ae`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_messaging/docs: record historical provenance update and validation`

## Changes included in implementation commit `17051b0c`

- Allow the optional companion preview_status endpoint through the existing bearer-authenticated controller; preserve receive_status signature and boolean response.
- Preserve preceding CRM, contact and POS-handoff work included in this update.

Files changed:
- `__manifest__.py`
- `controllers/gateway.py`
