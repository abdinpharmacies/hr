# Sales Chatter conversation UX

Commit: `b0095b6521105f026f3de12e4283d402255f28c3`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints

- Allow selecting the intended website when configuring a new endpoint.

Files changed:
- `ab_storefront_callcenter_adapter/README.md`
- `ab_storefront_callcenter_adapter/__manifest__.py`
- `ab_storefront_callcenter_adapter/changelog.d/2026-11-17-endpoint-website-selector.md`
- `ab_storefront_callcenter_adapter/tests/test_adapter.py`
- `ab_storefront_callcenter_adapter/views/views.xml`

Current changes before commit:
- Capture optional trusted browser/account ownership on checkout submissions before asynchronous confirmation.
- Preserve immutable guest/account origin and share the opaque browser identity with new Support sessions.
- Keep the optional producer setting disabled until receiver support has been upgraded; preserve existing evidence and both Arabic catalogs.

Files changed:
- `ab_storefront_callcenter_adapter/README.md`
- `ab_storefront_callcenter_adapter/__manifest__.py`
- `ab_storefront_callcenter_adapter/i18n/ar.po`
- `ab_storefront_callcenter_adapter/i18n/ar_001.po`
- `ab_storefront_callcenter_adapter/models/__init__.py`
- `ab_storefront_callcenter_adapter/models/adapter.py`
- `ab_storefront_callcenter_adapter/models/chat.py`
- `ab_storefront_callcenter_adapter/models/checkout_identity.py`
- `ab_storefront_callcenter_adapter/tests/__init__.py`
- `ab_storefront_callcenter_adapter/tests/test_checkout_identity.py`
- `ab_storefront_callcenter_adapter/views/views.xml`
