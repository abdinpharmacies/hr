# Public branch directory — 19.0.1.13.2

Current changes before commit:
- Show reviewed public branch locations throughout the conversation's company, including locations outside the staff member's fulfillment-store list, as explicitly requested by the user.
- Keep employee-session validation, conversation ownership, company isolation, active-store checks and profile review requirements. Order routing and inventory permissions remain unchanged.
- Cover all 42 storefront locations in English and both Arabic locales, search, cross-company denial, archived-store exclusion and sharing without changing order routing or delivery details.
- Document the separate reviewed Callcenter import and its source/store mapping evidence. No automatic seed, hook, sending activation or provider test send is introduced.

Files changed:
- `__manifest__.py`
- `models/branch_location.py`
- `resources/branch_locations.md`
- `tests/test_workspace.py`
- `changelog.d/2026-11-08-public-branch-directory.md`
