# Optional WhatsApp composition extension points

Current changes before commit:
- Version 19.0.1.8.1 adds narrow attachment and reaction validation extension points for the optional WhatsApp bridge. Telegram retains its existing validators.
- Preserves the pre-existing uncommitted message-navigation work and its separate change record. This entry describes only the WhatsApp additions.
- No source UI strings change; both existing Arabic catalogs are preserved.

Files changed by this task:
- `__manifest__.py`
- `models/workspace.py`
- `changelog.d/2026-11-08-whatsapp-extension-points.md`
