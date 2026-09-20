# Shared CUPS printing

Current changes before commit:
- Author: hagerYasser; date: 2026-09-20; commit: uncommitted.
- Add a reusable abstract printing service with no printing-specific roles or business tables.
- Render QWeb reports or trusted server receipt HTML and submit PDFs to CUPS with job IDs.
- Validate destinations, copies, report access, raw queues, failures and timeouts.
- Configure the server with ab_printing.server (default localhost:631); callers provide the queue.
- Support A4 or paginated 80mm x 297mm receipt PDFs. Thermal cutting/raw ESC/POS is not provided.
- Keep HTML/file submission helpers private to Python callers; no arbitrary HTML RPC endpoint.

Python usage from a business button:

```python
result = self.env['ab_printing_service'].print_report(
    report_xmlid='your_module.report_action',
    records=self,
    printer='your_cups_queue',
    copies=1,
)
# result contains ok, printer_name and job_id; return an Odoo notification
# action from an object button, or consume this dictionary in a JS handler.
```

Files changed:
- __init__.py
- __manifest__.py
- models/__init__.py
- models/printing_service.py
- i18n/ar.po
- i18n/ar_001.po
- changelog.d/2026-09-20-shared-printing.md

Validation:
- Installed on abdin_replica(POS); POS process reloaded.
- Rollback-only checks passed for generic report routing, A4/80mm sales and return PDFs, access-denial propagation, queue/copy validation, failures/timeouts, job parsing and temporary-file cleanup.
- Arabic runtime translation, msgfmt, Python/JS syntax and git diff checks passed.
- Physical submission pending: configured SLK queue is absent from CUPS; awaiting printer choice.
- Test scripts and generated PDFs remain outside the runtime addon in /tmp.

Printer selector follow-up (current changes before commit):
- Add read-only list_printers() using lpstat against ab_printing.server; include disabled queues.
- Add lpstat to binary dependencies and reuse CUPS server validation.
- POS users can now select any configured CUPS queue without an ab_printer record.
