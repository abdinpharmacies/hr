# WhatsApp authentication transport

Baseline: `b2184730`, Alhassan Hossny, 2026-11-15, `crm_messaging_gateway/feat: add website exchange, read receipts and animation handling`.

Current changes before commit:

- Add an isolated OTP worker reusing the existing Meta provider sender.
- Add a signed webhook receiver wrapper separating OTP status receipts from staff queues.
- Add private source/template allowlists, disabled deployment examples and mocked regressions.
- Preserve all existing source files and active services.
- Author: Alhassan Hossny
- Date: 2026-11-15

Files changed:

- `AUTHENTICATION.md`
- `app/auth_config.py`
- `app/auth_receiver.py`
- `app/auth_worker.py`
- `deploy/auth-config.example.json`
- `deploy/crm-messaging-callcenter-auth-worker.service`
- `tests/test_authentication.py`
- `changelog.d/2026-11-15-whatsapp-authentication.md`
