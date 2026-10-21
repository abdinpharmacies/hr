Recent relevant commits: none; this standalone directory is new on Callcenter.

Current changes before commit:

Author: hagerYasser
Date: 2026-10-21
Subject: Add standalone Callcenter Playwright sales tooling

- Implement the 15 reference sales scenarios and 21 actions directly on Callcenter, without transferring commits from POS.
- Add explicit local connection configuration, selected QA record validation, one employee login per run, and ownership-aware draft cleanup.
- Keep preview as the default and require an explicit scenario submit action plus --allow-submit for posting.
- Verify saved local invoices, Branch identifiers, request revisions, employee identity, lines, expected totals, and frozen promotion snapshots without automatic resubmission.
- Add ORM fixture previews and opt-in preparation with original-value backups; leave passwords unchanged unless an explicit reset is requested, and preserve PINs, prices, inventory, identifiers, and permissions.
- Add private Callcenter reports, a separate login verifier, usage documentation, and isolated CLI/browser simulations.
- Add terminal questions for connection settings, browser mode, login, and searchable QA record selection without editing JSON.
- Resolve related IDs and reference metadata read-only; request passwords and PINs at hidden prompts without saving them.
- Share interactive record selection with preparation helpers and preserve explicit fixture-application and submission opt-ins.
- Permit preview with an unlabelled authorized user and branch; retain labelled QA fixture checks and require labelled user/branch for posting.
- Validate employee, profile, service user, and active session at login; allow the initial default branch and verify the requested session/draft branch after UI selection.
- Report page/resource failures separately from employee identity errors, including HTTP paths and expected/actual identity IDs without session tokens.
- Redirect login directly to Sales and avoid redundant navigation, preventing announcement response-body reads from being interrupted by the runner.
- Restore every ordered POS scenario step and intermediate/final expected value, including manual promotion, contract switching/clearing, and quantity checkpoints.
- Capture the POS scenario/fixture reference and add a standalone parity audit, including missing-check detection and comparison against the live POS checkout without changing it.
- Reuse only saved record selections from report snapshots so old report commands run the current bundled scenarios; preserve explicit custom suite cases outside reports.
- Match POS quote/promotion selection checks, full business-RPC settling, filter reset, shortage/promotion checkpoints, quotes/submitted-invoice reports, empty-slot cleanup, and repeat-submit refusal.
- Add explicit opt-in test-password reset with private hash backups and Odoo hashing, custom backup/password-environment options, and POS-equivalent login verification.

Validation:

- Nine CLI checks passed.
- Four POS parity checks passed against both the captured reference and the current POS source: all 15 scenario step sequences, 21 actions, intermediate/final expectations, contract terms, promotion settings, prices, and shortage policy match after record-alias conversion.
- Eight terminal setup checks passed, covering selection, defaults, correction, cancellation, unattended requirements, and hidden credentials.
- Twenty-six submission/draft/connection/session/navigation/pricing simulation groups passed, including eight checks using actual headless Chromium and intercepted local browser content.
- Python/JavaScript syntax, scenario registration, helper CLI entrypoints, and whitespace checked.
- Blank-template interactive selection and read-only fixture checks passed against abdin_replica_callcenter.
- The latest user CASH preview passed both logins, branch selection, UI totals, quote and dialog checks, but failed on the Branch inventory refresh. The expanded parity suite has not been run live after these changes; the user will test it next.
- No fixture application, password reset, real sale, delivery notification, or printer job was performed.

Files changed:

- ab_test_playwright/.gitignore
- ab_test_playwright/README.md
- ab_test_playwright/actions.json
- ab_test_playwright/changelog.d/2026-10-21-callcenter-tooling.md
- ab_test_playwright/common.py
- ab_test_playwright/connection.mjs
- ab_test_playwright/draft_workspace.mjs
- ab_test_playwright/prepare_sales_scenarios.py
- ab_test_playwright/prepare_test_data.py
- ab_test_playwright/parity.py
- ab_test_playwright/pos_reference.json
- ab_test_playwright/pricing.mjs
- ab_test_playwright/qa_orm.py
- ab_test_playwright/run_sales_ui.py
- ab_test_playwright/sales_ui_cases.json
- ab_test_playwright/sales_ui_runner.mjs
- ab_test_playwright/selftest_cli.py
- ab_test_playwright/selftest_parity.py
- ab_test_playwright/selftest_terminal.py
- ab_test_playwright/session_identity.mjs
- ab_test_playwright/selftest_submission.mjs
- ab_test_playwright/submission.mjs
- ab_test_playwright/startup_navigation.mjs
- ab_test_playwright/terminal_setup.py
- ab_test_playwright/validation_results.json
- ab_test_playwright/verify_login.mjs
