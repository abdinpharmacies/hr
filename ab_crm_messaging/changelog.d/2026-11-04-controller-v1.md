# Versioned messaging controller

Current changes before commit:

- Expose a bearer-only, bounded JSON envelope at `/crm/messaging/v1/<operation>`.
- Whitelist the existing messaging operations and reject caller-supplied context/scope.
- Delegate business authorization and mutation to existing model methods in one transaction, rolling back rejected operations.
- Retain original provider timestamps in protected incoming-event evidence and translate the field in both Arabic catalogs.
- Echo correlation IDs and sanitize business-error responses; retain JSON-2 compatibility.
- Verify actual HTTP bearer authentication, account isolation, staff/service separation and invalid envelopes.

Files changed:

- `__init__.py`, `__manifest__.py`
- `controllers/__init__.py`, `controllers/gateway.py`
- `models/messaging.py`, `i18n/ar.po`, `i18n/ar_001.po`
- `tests/__init__.py`, `tests/test_controller.py`
- `changelog.d/2026-11-04-controller-v1.md`
