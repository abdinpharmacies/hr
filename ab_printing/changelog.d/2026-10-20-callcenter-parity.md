Commit: 715b9fd0e510cfe958492610cb1bcb7fbf4b70e0
Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-09-20T11:52:40+03:00
Subject: ab_printing/FEAT(#17310): add shared printing service

User-facing changes:
- Introduce the shared printing service on pos19.

Files changed:
- ab_printing/__init__.py
- ab_printing/__manifest__.py
- ab_printing/changelog.d/2026-09-20-shared-printing.md
- ab_printing/i18n/ar.po
- ab_printing/i18n/ar_001.po
- ab_printing/models/__init__.py
- ab_printing/models/printing_service.py

Current changes before commit:
- Port the optional shared CUPS printing service from pos19 without test fixtures.
- Retain authenticated record/report access, PDF generation and printer validation; maintain both Arabic catalogs.

Files changed:
- ab_printing/__init__.py
- ab_printing/__manifest__.py
- ab_printing/changelog.d/2026-10-20-callcenter-parity.md
- ab_printing/i18n/ar.po
- ab_printing/i18n/ar_001.po
- ab_printing/models/__init__.py
- ab_printing/models/printing_service.py
