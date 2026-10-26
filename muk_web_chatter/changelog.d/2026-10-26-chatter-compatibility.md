# Chatter attachment preview compatibility

Current changes before commit:
- Fix form rendering on Odoo 19 revisions that use `showsAttachmentPopout` for attachment preview visibility.
- Locate the attachment popout button by its click handler and preserve Odoo's original visibility condition while requiring the aside chatter layout.

Files changed:
- `muk_web_chatter/static/src/chatter/chatter.xml`
- `muk_web_chatter/changelog.d/2026-10-26-chatter-compatibility.md`

Recent relevant commit:
- Commit: `19733c65ef11148e4b9aee789e49721d0df5586a`
- Author: Alhassan Hossny
- Date: 2026-04-14
- Original subject: Chore: Update module icon
- Updated module artwork and file modes; no chatter behavior changed.
- Files changed: module artwork and file modes across `muk_web_chatter` (32 files).
