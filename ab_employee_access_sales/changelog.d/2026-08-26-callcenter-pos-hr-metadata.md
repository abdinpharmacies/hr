Commit: 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date: 2026-07-28 15:21:42 +0300
Subject: INIT commit pos19

User-facing changes:
- Existing POS HR access tracks employee sessions, shifts, roles, and sale operation logs.

Files changed:
- ab_employee_access_sales

Current changes before commit:
- Include remote-safe POS HR employee/device metadata in the sales header payload before POS submit, so call-center XML-RPC creates the branch invoice with the correct employee reference.
- Skip local-only POS HR relation IDs for call-center remote submits because branch databases do not share session/profile/role/shift records.
- Centralize POS HR header metadata building so local branch POS keeps full session metadata and call-center remote POS gets only safe values.
- Skip the old local header metadata write when POS submit returns a remote branch result, while still logging the successful sale submit operation.

Files changed:
- ab_employee_access_sales/changelog.d/2026-08-26-callcenter-pos-hr-metadata.md
- ab_employee_access_sales/models/ab_sales_pos_api.py
