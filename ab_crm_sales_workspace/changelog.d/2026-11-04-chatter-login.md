# Separate Chatter employee login and Telegram setup

- Add a dedicated employee/PIN popup and hashed, expiring Chatter sessions; reuse employee permissions and PIN validation without using POS sessions or components.
- Permit staff administrators carrying the legacy integration role, while keeping dedicated messaging service identities excluded from staff decisions.
- Notify active Chatter sessions of authorized channel messages throughout the Odoo web client.
- Add administrator Telegram Setup with a masked token input and an account-bound system parameter retrieval endpoint for the gateway.
- Translate new UI and errors in both Arabic catalogs.

Affected files: manifest, model imports, `models/session.py`, `models/workspace.py`, `models/telegram_setup.py`, security ACL/rules, `views/telegram_setup.xml`, workspace and login frontend assets, session notification service, Arabic catalogs, workspace tests, README and validation evidence. Gateway transport/configuration/setup changes and operating instructions are tracked alongside the gateway.
