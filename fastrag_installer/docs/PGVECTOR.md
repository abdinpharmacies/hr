# Start FastRAG with its own pgvector database

This mode runs independently of Odoo. Use a dedicated database, not an Odoo
database. It does not migrate existing knowledge.

## System-wide install with systemd

On Ubuntu 24.04 with a running local PostgreSQL 16 cluster and systemd,
install the prerequisites, then run from the source tree:

```bash
sudo apt-get install python3-venv postgresql-client-16 postgresql-16-pgvector curl
sudo bash install_fastrag_system.sh --check
sudo bash install_fastrag_system.sh
```

You can also generate a portable bundle from the source project with
`python3 deploy/build_installer_bundle.py /path/to/new/fastrag_installer`.
Copy that entire directory to the target host and invoke the included script
by its path. The source directory can be anywhere outside the installed
`/opt/fastrag` tree.

The installer provisions the `fastrag` system account with `/opt/fastrag` as
its home, a PostgreSQL login role and database both named `fastrag`, the
pgvector extension, `/opt/fastrag/venv-fast`, and `fastrag.service`. It prompts
for the Gemini key with input hidden on first install, then enables and starts
the service at `http://127.0.0.1:8111`. App files are root-owned; private config
is readable only by root and the FastRAG service group.

For existing goals, choose **skip**, **overwrite**, or **abort**. Decisions are
collected before provisioning. Overwrite reconciles accounts and database
settings in place; it does not delete database records, credentials, or other
files in the home directory. Replaced project files, the venv, and the local
unit file are backed up under `/var/backups/fastrag-system.*`. Live config is
preserved. If you already run an Odoo-backed `fastrag.service`, overwriting
the unit switches that service to the new pgvector deployment, not its data.
Incompatible resources are rejected rather than silently repurposed.

The installer verifies that the database login uses peer authentication.
If it fails, review the first matching local rule in PostgreSQL's `pg_hba.conf`
(for example `local fastrag fastrag peer`). The installer does not edit
authentication rules or reload PostgreSQL.

The installer creates an API key for the `odoo` collection at
`/opt/fastrag/keys/odoo.key` before starting the service. It prints only the file
path and keeps an existing key unchanged on reruns. Use this key as
`fastrag.api_key` in Odoo. For the cURL examples below, load it with
`FASTRAG_API_KEY=$(sudo cat /opt/fastrag/keys/odoo.key)` instead of reading
`config/odoo-test.key`.

Check the service after installation:

```bash
sudo systemctl status fastrag.service
curl -fsS http://127.0.0.1:8111/healthz
```

## 1. Manual foreground install: prepare a database and configuration

On Ubuntu with PostgreSQL 16, install the matching pgvector package if it is
not already present. For a local development setup using PostgreSQL peer
authentication, create a non-superuser role matching the Linux user running
FastRAG (skip `createuser` if that role already exists):

```bash
sudo apt-get install postgresql-16-pgvector
sudo -u postgres createuser "$USER"
sudo -u postgres createdb --owner="$USER" fastrag_db
sudo -u postgres psql -d fastrag_db -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

For production, use a dedicated non-superuser service account and role with
access only to the FastRAG database. If connecting to remote PostgreSQL, use
verified TLS. The example local DSN uses a Unix socket with no password.

```bash
cd /opt/odoo19/fast_rag
python3 -m venv pgvenv
pgvenv/bin/python -m pip install -r app/requirements-pgvector.txt
umask 077
cp -n config/config.pgvector.example.yaml config/config.pgvector.yaml
```

Edit `config/config.pgvector.yaml`: set `database.dsn` to the dedicated database
and role (replace `user=fastrag` with your role), and set `gemini.api_key`. An
explicit `FASTRAG_DATABASE_DSN` or `FASTRAG_GEMINI_API_KEY` environment variable
overrides the corresponding setting. Client keys are created separately; the
legacy `server.api_key` setting is not used in pgvector mode.

## 2. Initialize and start

```bash
pgvenv/bin/python -m app init-db --config config/config.pgvector.yaml
pgvenv/bin/python -m app create-key --config config/config.pgvector.yaml \
  --collection odoo-test --key-file config/odoo-test.key
pgvenv/bin/python -m app check --config config/config.pgvector.yaml
pgvenv/bin/python -m app serve --config config/config.pgvector.yaml
```

`create-key` never overwrites a file. Store or transfer the generated key securely.
To rotate it, create a second key for the same collection, switch Odoo to the
new key, test it, then run `revoke-key` with the old `--key-file`. Revocations
take effect within five seconds for new requests on a running process. For
public-only clients, create a separate key with `--permissions query --public-only`.
Use HTTPS via a reverse proxy if Odoo runs on another machine. Keep the HTTP
listener on loopback and configure request size and rate limits at the proxy.

## 3. Test with cURL

In a second Bash terminal, from the project root:

```bash
FASTRAG_URL=http://127.0.0.1:8111
read -r FASTRAG_API_KEY < config/odoo-test.key

rag() {
  printf 'Authorization: Bearer %s\n' "$FASTRAG_API_KEY" |
    curl --fail-with-body --silent --show-error --header @- "$@"
}

curl -fsS "$FASTRAG_URL/healthz"
rag "$FASTRAG_URL/v1/connection"

rag -H 'Content-Type: application/json' \
  --data '{"title":"Support desk hours","text":"The demo support desk opens at 9 AM."}' \
  "$FASTRAG_URL/v1/records"
```

Copy the returned record ID. Optionally add a supporting file before indexing:

```bash
RECORD_ID='<record UUID>'
rag -F 'file=@notes.txt' --form-string 'caption=Support notes' \
  "$FASTRAG_URL/v1/records/$RECORD_ID/attachments"
rag -X POST "$FASTRAG_URL/v1/records/$RECORD_ID/index"
```

Copy the returned job ID and wait for `succeeded`:

```bash
JOB_ID='<job UUID>'
rag "$FASTRAG_URL/v1/jobs/$JOB_ID"
rag -H 'Content-Type: application/json' \
  --data '{"question":"When does the demo support desk open?"}' \
  "$FASTRAG_URL/v1/answers"
```

The connection and record API calls do not contact Gemini. Indexing, search,
and answers use Gemini and may incur charges. `/docs` on the server documents
the full API. Uploads and indexing can accept a UUID `Idempotency-Key` header;
create also accepts it. Reuse the same key only when retrying the same request.

## 4. Connect Odoo

1. Make `/opt/odoo19/addons_rag` available on the Odoo `addons_path`. Update the
   Apps list and install **FastRAG API Connector** (`fastrag_connector`). This
   does not require `fastrag_backend` or pgvector in the Odoo database.
2. As a system administrator, open **Settings → FastRAG API Tester**. Enter the
   base URL and the generated key, then click **Save Connection**. The connector
   stores `fastrag.base_url` and `fastrag.api_key` as system parameters. The
   form never returns the saved key. Protect the Odoo database and backups.
3. Run **Test connection**, then try **Create record → Queue indexing → Get job
   status → Ask a question**. The tester keeps returned IDs and includes a copyable
   cURL command with a `$FASTRAG_API_KEY` placeholder. Archive the test record
   when finished.

Other Odoo modules can call `self.env["fastrag.api.client"]` from trusted
server-side Python. Connector methods are not exposed through Odoo RPC.
The connector doesn't hook into existing business models or automatically
sync them; add model-specific background sync separately.

## Operational notes

- One application process and one embedded worker. PostgreSQL durably stores
  the queue; leases allow recovery after a crash. On a change to indexable
  content or attachments, the old revision becomes unsearchable until the
  new revision is indexed. Archive and public visibility changes are immediate.
- Exact cosine search in pgvector. Changing the embedding model, dimensions
  or chunking profile requires reindexing. Images are stored and their captions
  can be indexed; there is no image OCR.
- API key lookups and embeddings have bounded process-local caches. Search
  results and answers are not cached. The API has per-key and concurrent
  request limits; use shared limits before scaling to multiple instances.
- Back up `fastrag_db` and the private configuration. To switch an existing
  Odoo-backed deployment, plan an explicit record and attachment export and
  reindex before cutover. Nothing is imported automatically.
