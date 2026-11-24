# Portable FastRAG installer

This folder installs the standalone FastRAG pgvector server. It is **not an
Odoo addon**. Copy the entire folder to any location outside `/opt/fastrag`.
The script finds its app files relative to itself; the original FastRAG
checkout and `/opt/odoo19/replica_addons` are not required on the target host.

On Ubuntu 24.04 with a running local PostgreSQL 16 server and systemd:

```bash
sudo apt-get install python3-venv postgresql-client-16 postgresql-16-pgvector curl
sudo bash /path/to/fastrag_installer/install_fastrag_system.sh --check
sudo bash /path/to/fastrag_installer/install_fastrag_system.sh
```

The installer downloads Python dependencies, prompts for the Gemini API key
on first install, and starts `fastrag.service` on `127.0.0.1:8111`. The install
target remains `/opt/fastrag`. App files, configuration examples and the guide
are included here; live config, credentials, virtual environments and database
data are not. Existing install resources are handled interactively. The
installer preserves existing private config and the Odoo key.

```bash
sudo systemctl status fastrag.service
curl -fsS http://127.0.0.1:8111/healthz
```

Use `/opt/fastrag/keys/odoo.key` to configure the separately installed
`fastrag_connector` in Odoo. See [the pgvector guide](docs/PGVECTOR.md) for
connection settings, cURL tests and troubleshooting.

To refresh this generated bundle, run `python3 deploy/build_installer_bundle.py
/path/to/new/fastrag_installer` from the canonical FastRAG source project
(`/opt/odoo19/fast_rag` on the development host). Build into a new directory,
verify it, then deliberately replace the old copy. Do not edit generated
copies in place.
