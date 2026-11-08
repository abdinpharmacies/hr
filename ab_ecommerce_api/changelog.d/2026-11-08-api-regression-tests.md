# API regression coverage

Commit: 3ad02a45916217a813a9535b058a95b6681439c0
Author: Mohamed Fawzy
Date: 2026-10-22
Original subject: ab_ecommerce_api/ADD: introduce customer ecommerce API

- Introduce customer authentication, scoped sessions, and ecommerce operations.

Files changed relevant to this coverage:

- `controllers/`
- `models/`
- `static/`
- `views/`

## Current changes before commit:

- Retain API authentication, session, customer isolation, checkout, and documentation regression tests in the development repository.
- Retain API workspace access, embedded documentation, and browser interaction tests.
- Python syntax checks passed during commit preparation; runtime tests were not rerun.
- Exclude development tests from production runtime packages.

Files changed:

- `tests/__init__.py`
- `tests/test_api.py`
- `tests/test_workspace.py`
- `changelog.d/2026-11-08-api-regression-tests.md`
