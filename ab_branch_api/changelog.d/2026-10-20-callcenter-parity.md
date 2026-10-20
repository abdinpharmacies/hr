Commit: 7a6818b0e2ff41fa537e49ff66dbf1d17e2a90b8
Author: emadco88 <emadco88@gmail.com>
Date: 2026-10-18T15:52:32+03:00
Subject: ab_branch_api/ FIX empty allowed stores

User-facing changes:
- Handle an empty allowed-sales-store configuration.

Files changed:
- ab_branch_api/changelog.d/2026-10-18-empty-sales-store-access.md
- ab_branch_api/models/branch_api.py

Current changes before commit:
- Advertise optional delivery notification capability when the branch request model is installed.
- Accept delivery consent and instructions without changing submission identity, replay or recovery rules.
- Document the paired callcenter rollout; validate with mocked backend regression checks.

Files changed:
- ab_branch_api/README.md
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-20-callcenter-parity.md
- ab_branch_api/models/branch_api.py
