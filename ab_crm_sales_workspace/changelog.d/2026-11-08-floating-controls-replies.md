# Floating Chatter controls and pharmacy/cosmetics saved replies

Current changes before commit:
- Version 19.0.1.10.1 centers an accessible search icon between contact details and channels. Search overlays the timeline without resizing it, supports focus/dismissal and pauses read acknowledgement while covering messages.
- Places the circular latest-message arrow at the timeline's bottom center with a transparent, click-through surrounding container and unread badge.
- Adds a reusable 44-reply EN/AR pharmacy/cosmetics content catalog. At the user's request, the matching replies were created through ORM only in the configured callcenter branch, preserving existing replies and sending no messages.
- Verifies existing browser regressions, English/Arabic desktop/mobile geometry and authorized staff read access. No protected-addon change or live Odoo upgrade/restart.

Files changed:
- `__manifest__.py`
- `static/src/workspace.js`, `static/src/workspace.xml`, `static/src/workspace.scss`
- `resources/pharmacy_cosmetics_saved_replies.csv`
- `README.md`, `VALIDATION.md`
- `changelog.d/2026-11-08-floating-controls-replies.md`
