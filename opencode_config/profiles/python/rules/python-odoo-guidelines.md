---
description: Python (with Odoo) project guidelines. PEP 8 conventions, typing, virtual environments, dependency hygiene, and Odoo module patterns. Authoritative for Python and Odoo projects in this profile.
alwaysApply: true
---
# PYTHON & ODOO GUIDELINES

## Python Style & Typing

- Follow PEP 8. Prefer type hints on public functions and module-level API.
- Use modern Python (match the project's declared interpreter version); avoid deprecated constructs.
- Prefer dataclasses and simple structures over unnecessary abstractions.

## Environments & Dependencies

- Keep dependencies in a lockfile or `requirements.txt` with pinned versions.
- Never guess package versions. Before advising a package, perform a live web search to retrieve the absolute latest stable version.
- Prefer the standard library or venv-scoped installs; avoid global pip installs.

## Odoo-Specific (when inside an Odoo codebase)

- Follow Odoo module conventions: `__manifest__.py`, `__init__.py`, model, view (XML), security, and data directories as appropriate.
- Use Odoo's ORM idioms (fields, computed fields, `onchange`, constraints, recordset operations) idiomatic to the installed Odoo major version.
- Model name prefixes follow the module naming conventions; security access rules and ir.views mirror the model/state.
- Prefer `record`/`env` style over raw SQL unless performance requires otherwise; use SQL deliberately and safely.

## Code Quality

- Clean code: single responsibility principle and DRY.
- Use clear, descriptive, accurate naming.

## Comments Rule

- Do NOT add comments to code unless the user explicitly asks.
