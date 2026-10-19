Current changes before commit:

- Add module-owned replication exceptions for the three stock unit mapping fields.
- Preserve underlying product ACLs and restrictions on prices and other master fields.
- Keep remote synchronization activation outside this permission bridge.

Validation: Targeted installation succeeded on rip_bconnect. Four rollback-only access tests passed, including denied price edits and retained product ACL restrictions. The exported translation template contains no module-specific UI strings.

Files changed:

- ab_stock_replication/README.md
- ab_stock_replication/__init__.py
- ab_stock_replication/__manifest__.py
- ab_stock_replication/changelog.d
- ab_stock_replication/i18n/ar.po
- ab_stock_replication/i18n/ar_001.po
- ab_stock_replication/security/mapping_permissions.xml
