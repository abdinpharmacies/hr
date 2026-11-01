3db5d596 — emadco88 — 2026-07-28
INIT commit pos19

- Added the chatter template and behavior in the initial module import.

Files changed (chatter integration):

- muk_web_chatter/static/src/chatter/chatter.xml
- muk_web_chatter/static/src/chatter/chatter.js

5bac93aa — yahyazakaria22 — 2026-11-02
fix: align MuK chatter template with Odoo 19

- Remove the attachment preview XPath that no longer exists in Odoo 19 mail.Chatter and breaks form rendering.
- Match Odoo 19's message posting permission for the Message and Note buttons.

Files changed:

- muk_web_chatter/static/src/chatter/chatter.xml
