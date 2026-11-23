# Reliable website conversations

Current changes before commit:
- Re-probe unsupported website capabilities every minute and fetch orders and chat independently.
- Recover website-only expired leases and uncertain sends with eight attempts and exponential delay capped at five minutes.
- Preserve per-destination ordering and evidence when an explicit same-token retry supersedes an older review attempt.
- Quarantine malformed/conflicting events individually and expose website queue age, attempts and failure category.

Files changed:
- app/website.py
- app/storage.py
- app/sqlite_storage.py
- app/odoo.py
- app/ops.py
- app/health.py
- tests/test_website.py
- README.md
- changelog.d/2026-11-18-reliable-conversations.md
