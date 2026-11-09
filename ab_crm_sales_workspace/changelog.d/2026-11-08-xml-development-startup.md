# XML development-mode startup fix — 19.0.1.13.1

Current changes before commit:
- Preserve whitespace before each of the seven branch view architectures so Odoo 19's filesystem view loader works with `--dev=xml`.
- Fix the upgrade failure reported while validating `conversation_identity_review`; the actual failing child is the branch share inherited view loaded from its source file.
- Preserve XML IDs, view content, permissions, business behavior and both Arabic catalogs.
- Add regression coverage using Odoo's filesystem loader and combined inherited architectures. Validate the targeted upgrade with the same XML development mode as the Callcenter runtime.

Files changed:
- `__manifest__.py`
- `views/branch_location.xml`
- `tests/test_workspace.py`
- `changelog.d/2026-11-08-xml-development-startup.md`
