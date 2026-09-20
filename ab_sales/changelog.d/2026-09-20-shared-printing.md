# Bill wizard CUPS printing

Recent relevant commit:
- 2c8d7db948632c523bed8b1c793d6c6c88857352
- Author: hager yasser; date: 2026-09-13.
- Original subject: ab_sales/FEAT(#19780): Add an immediate “Remove All” button to the ab_sales POS sidebar

Current changes before commit:
- Author: hagerYasser; date: 2026-09-20.
- Connect the bill wizard Print Receipt confirmation to ab_printing while retaining the dialog, preview and duplicate-click guard.
- Resolve the selected connected printer queue on the server and show the CUPS job ID.
- Preserve receipt access checks and optional sales prevention guards; do not change other printing endpoints.
- Add private PDF rendering spacing for the existing fixed-width RTL receipt.
- Maintain Arabic translations of the new messages.

Files changed:
- __manifest__.py
- models/ab_sales_ui_api_bill_wizard_inherit.py
- static/src/bill_wizard/bill_wizard_action.js
- i18n/ar.po
- i18n/ar_001.po
- changelog.d/2026-09-20-shared-printing.md

Printer selector follow-up (current changes before commit):
- Load all configured CUPS queues on open and Refresh without creating Odoo printer records.
- Submit the queue name, preserving selection across refreshes and rejecting removed queues.
- Restore System dialog browser printing for local-computer printers.
- Use a receipt-only dialog subclass; preserve other consumers of the existing dialog.
- Keep queue preference in browser storage scoped by database and user.
- Add translated help text and failure messages.
Additional files changed:
- static/src/bill_wizard/cups_print_dialog.js
- static/src/bill_wizard/cups_print_dialog.xml
Validation: mocked JavaScript checks cover direct/browser printing, failure handling, refresh reorder/removal and preference isolation.
