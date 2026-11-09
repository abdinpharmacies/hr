# Compact Chatter and message reactions

Current changes before commit:
- Version 19.0.1.9.0 places a compact, user-timezone update time beside the contact: today's time, weekday within the last seven calendar days, otherwise month/day.
- Moves icon-only channel switches into the contact header, with dimmed inactive icons, an active indicator, accessible names and account tooltips.
- Removes the latest-outgoing summary, empty-composer helper line, visible failure paragraphs and synthetic attachment captions from message presentation.
- Keeps reactions as auditable records while displaying only the latest reaction per direction on its target; removals clear the badge. Reactions do not become timeline replies, sidebar previews or unread message counts.
- Uses an inline warning that changes to a retry icon on hover/focus for authorized retryable failures. Retrying updates the existing operation/message, including older loaded messages. Uncertain outcomes and invalid media remain nonretryable under the existing safeguards.
- Adds channel-colored media previews, download controls, compact attachment cards and responsive header styling.
- Adds English/Arabic terms and backend/browser regressions. No protected addon, gateway, order or live-runtime changes.

Files changed:
- `__manifest__.py`, `models/workspace.py`
- `static/src/workspace.js`, `static/src/workspace.xml`, `static/src/workspace.scss`
- `static/src/message.js`, `static/src/message.xml`
- `tests/test_workspace.py`, `static/tests/message.test.js`
- `i18n/ar.po`, `i18n/ar_001.po`
- `README.md`, `VALIDATION.md`, `changelog.d/2026-11-08-compact-chatter.md`
