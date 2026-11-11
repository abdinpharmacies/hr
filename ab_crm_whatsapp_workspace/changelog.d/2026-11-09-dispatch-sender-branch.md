# WhatsApp dispatch checks the original sender's branch access

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:05:37+02:00
- Original subject: ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates

## Changes included in implementation commit `fc6257ab`

- Check the WhatsApp conversation branch in the original sender's environment during queued dispatch. The gateway service retains its restricted permissions.
- Cover CRM text dispatch and successive reaction changes with strict authorization assertions. Strengthen template and permission-revocation tests so a rejection dictionary cannot pass as a successful boolean result.
- Preserve Telegram behavior, company and branch restrictions, session validation, and the WhatsApp reply window.

Validation: both new regression methods failed before the correction (three failed assertions, including both reaction variants). After the correction, the isolated `callcenter_whatsapp_dispatch_test_20261109` database passed all 27 WhatsApp bridge test methods with zero failures or errors. The copied database reports missing existing filestore images; these did not affect the tested dispatch paths. Python syntax and `git diff --check` passed. No external messages were sent by these tests.

Runtime activation completed after the user-managed callcenter Odoo restart; no schema or asset upgrade was needed. The original failed CRM operations passed authorization when replayed in rolled-back transactions, without resending them. Live validation used the queued administrator API and only the user's approved recipient: one text reached Read, and successive thumbs-up and heart reactions were accepted. Each operation had exactly one send attempt. The incoming WhatsApp queue drained; Telegram configuration, global sending configuration, and its active polling receiver were unchanged. The browser session was unavailable for a direct UI test.

Files changed:
- `models/gateway.py`
- `tests/test_bridge.py`
- `changelog.d/2026-11-09-dispatch-sender-branch.md`
