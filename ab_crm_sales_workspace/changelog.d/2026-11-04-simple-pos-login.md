# Match POS login and simplify Telegram configuration

- Match the existing POS login layout with one searchable Employee field, PIN and Employee Login button. Keep a separate Chatter component and session; use the same employee selection widget with server-validated Call Center filtering.
- Remove Telegram configuration from the Chatter workspace.
- Keep connection preparation under Sales → Configurations, preserving action/menu XML IDs. Remove the token field and Intake selector; read the token exclusively from its administrator-managed system parameter.
- Preserve account authorization, existing company mappings and disabled-by-default messaging.
- Update both Arabic catalogs, regression checks and manual token instructions.

Changed: manifest, login/workspace assets, session/bootstrap, Telegram connection model/view, tests, translations and operating documentation. POS and WhatsApp sources are unchanged.
