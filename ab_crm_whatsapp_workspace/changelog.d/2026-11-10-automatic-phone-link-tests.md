# Automatic same-phone association tests

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates`

## Changes included in implementation commit `fc6257ab`

- Update the Telegram secondary-phone regression for automatic matching to the unique saved customer.
- Verify WhatsApp and Telegram with equivalent phone formats join one customer during notification polling, with independent conversations, stable message IDs, history projection and idempotent audits.
- Runtime behavior for this increment belongs to Sales Chatter 19.0.1.19.0. This module's increment changes tests and documentation only; preserve prior gateway, reception and dispatch work.

Files changed for this increment:
- `changelog.d/2026-11-10-automatic-phone-link-tests.md`
- `tests/test_bridge.py`
