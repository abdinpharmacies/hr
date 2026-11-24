# Independent chats

Commit: `afad4e25ec38cd3ae1903f85a3b4669b2a564a19`
Author: Alhassan Hossny
Date: 2026-11-23
Original commit subject: ab_crm_website/fix: retry competing preference creation

- Preserve the existing provider transport and employee preference behavior.

Files changed in that commit:
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/changelog.d/2026-11-23-preference-concurrency.md`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/tests/test_chat_ux.py`

Current changes before commit:
- Show independent chat entries, messages, drafts, read positions and exact notification targets.
- Disable chat joining without changing customer ownership evidence or delivery envelopes.
- Preserve lifecycle closure, retryable delivery and branch/company/customer checks.
- Maintain English/Arabic text, release versions, focused regressions and manual rollback instructions.

Files changed by this task:
- `ab_crm_website/README.md`
- `ab_crm_website/RELEASE.md`
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/i18n/ar.po`
- `ab_crm_website/i18n/ar_001.po`
- `ab_crm_website/models/adapter.py`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/tests/__init__.py`
- `ab_crm_website/tests/test_chat_ux.py`
- `ab_crm_website/tests/test_independent_chats.py`
