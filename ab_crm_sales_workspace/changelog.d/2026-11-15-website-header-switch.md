# Direct navigation to shared channel timelines

Current changes before commit:

- Open adapter-declared shared timelines directly when switching channel icons, instead of leaving the previous channel behind an order chooser.
- Remember the selected authorized destination and its draft, including the initially loaded conversation; retain choosers for active shared timelines and independent accounts.
- Add focused JavaScript navigation coverage and an isolated browser runner.

Files changed:

- `static/src/workspace.js`
- `static/tests/navigation.test.js`
- `tests/test_branch_browser.py`
- `__manifest__.py`
- `changelog.d/2026-11-15-website-header-switch.md`
