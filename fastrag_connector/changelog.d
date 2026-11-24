Commit: e9df6a1c3
Author: emadco88 <emadco88@gmail.com>
Date: 2026-11-24T03:59:15+02:00
Subject: fastrag_connector/ UPD remove the installer
- Remove the system installer from the Odoo connector.
Files changed:
- install_fastrag_system.sh

Current changes before commit:
- Let each Odoo instance configure a FastRAG CA bundle or explicitly skip TLS verification in isolated development. Verification stays on by default.
- Document both settings and translate TLS configuration errors.
Files changed:
- README.md
- changelog.d
- i18n/ar.po
- i18n/ar_001.po
- models/client.py
