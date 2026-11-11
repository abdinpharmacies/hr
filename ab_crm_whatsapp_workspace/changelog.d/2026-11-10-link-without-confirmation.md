# Existing-contact linking without extra confirmation

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates`

## Changes included in implementation commit `fc6257ab`

- Verify ordinary agents link Telegram and WhatsApp to one customer without a reason or extra confirmation, while shared orders and conflict ownership protections remain intact. Runtime changes belong to Sales Chatter 19.0.1.23.0.

Files changed for this increment:
- `tests/test_bridge.py`
- `changelog.d/2026-11-10-link-without-confirmation.md`
