# FastRAG installer bundle

- This is a generated deployment bundle, not an Odoo addon. Start with
  [README.md](README.md) for operator instructions.
- Make development changes in the canonical FastRAG source project
  (`/opt/odoo19/fast_rag` on the development host), then regenerate this bundle.
  Do not patch the generated `app/` or installer as the source of truth.
- Keep the bundle portable. Source paths are relative to the installer; the
  system install target is `/opt/fastrag`. Do not add an Odoo manifest.
- Do not bundle live config, credentials, environments, logs, or data. Do not
  run the privileged installer, restart services, or modify Odoo or PostgreSQL
  to verify a bundle. Use `bash -n install_fastrag_system.sh` and
  `bash install_fastrag_system.sh --help` for unprivileged smoke checks.
