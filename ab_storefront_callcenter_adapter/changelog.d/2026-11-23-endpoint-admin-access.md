# Endpoint administrator access

## d83774a1e8e80247ee974c7f5b0fdf3f70235d97

Author: Mohamed Fawzy
Date: 2026-11-23
Original commit subject: ab_storefront_callcenter_adapter/FIX: restore translation module metadata

- Restore module metadata for the existing Arabic translations after merge repair.

## Current changes before commit:

- Allow Settings administrators to read endpoints in their selected companies even when another role implies Callcenter Exchange Service.
- Retain ordinary exchange-user ownership, company isolation and write restrictions.
- Cover direct reads, selected-company changes and denied writes in focused ORM access tests.

Files changed:
- security/security.xml
- tests/__init__.py
- tests/test_endpoint_access.py
- changelog.d/2026-11-23-endpoint-admin-access.md
