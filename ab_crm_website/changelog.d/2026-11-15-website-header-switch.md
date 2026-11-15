# Website header channel switching

Current changes before commit:

- Declare Website order conversations as members of a shared timeline in authorized navigation results from every provider.
- Let the shared header open that timeline in one click while keeping order-specific destination selection available on the active Website icon.
- Verify header clicks through Telegram, WhatsApp and Website, separate invoices, original destinations and per-conversation drafts.

Files changed:

- `models/adapter.py`
- `tests/test_contact_groups.py`
- `__manifest__.py`
- `changelog.d/2026-11-15-website-header-switch.md`
