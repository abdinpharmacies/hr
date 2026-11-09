# 19.0.1.1.2 — Template text direction

Current changes before commit:

- Apply automatic text direction to approved-template names and parameter values, and keep language codes LTR inside the Arabic interface.
- Preserve template authorization, required parameters and explicit Queue action.

Files changed:
- __manifest__.py
- static/src/templates.xml
- changelog.d/2026-11-08-template-text-direction.md

Validation: shared Chatter browser regressions in the isolated database; wider English/ar/ar_001 UI review recorded in the Sales Chatter VALIDATION.md. No live upgrade or restart.
